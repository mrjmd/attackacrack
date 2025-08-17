"""
Unit tests for BaseRepository abstract class
Tests the common functionality using a concrete implementation
"""

import sys
import os
# Add the app directory to the path
sys.path.insert(0, '/app')

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from repositories.base_repository import (
    BaseRepository,
    PaginationParams,
    PaginatedResult,
    SortOrder
)


# Concrete implementation for testing
class TestModel:
    """Mock model class for testing"""
    id = None
    name = None
    value = None
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestRepository(BaseRepository[TestModel]):
    """Concrete repository for testing"""
    
    def search(self, query: str, fields=None):
        """Implement abstract search method"""
        # Simple implementation for testing
        return self.find_by(name=query)


class TestBaseRepository:
    """Test suite for BaseRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        session = MagicMock(spec=Session)
        session.query.return_value = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create test repository instance"""
        return TestRepository(mock_session, TestModel)
    
    # CREATE Operations Tests
    
    def test_create_success(self, repository, mock_session):
        """Test successful entity creation"""
        # Arrange
        mock_entity = TestModel(id=1, name="test", value=42)
        
        # Mock the model class to return our entity
        with patch.object(TestModel, '__init__', return_value=None) as mock_init:
            mock_init.return_value = None
            
            # Act
            result = repository.create(name="test", value=42)
            
            # Assert
            mock_session.add.assert_called_once()
            mock_session.flush.assert_called_once()
            assert result is not None
    
    def test_create_database_error(self, repository, mock_session):
        """Test create with database error"""
        # Arrange
        mock_session.flush.side_effect = SQLAlchemyError("Database error")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.create(name="test")
        
        mock_session.rollback.assert_called_once()
    
    def test_create_many_success(self, repository, mock_session):
        """Test creating multiple entities"""
        # Arrange
        entities_data = [
            {"name": "test1", "value": 1},
            {"name": "test2", "value": 2}
        ]
        
        # Act
        result = repository.create_many(entities_data)
        
        # Assert
        mock_session.add_all.assert_called_once()
        mock_session.flush.assert_called_once()
        assert len(result) == 2
    
    def test_create_many_database_error(self, repository, mock_session):
        """Test create_many with database error"""
        # Arrange
        mock_session.flush.side_effect = SQLAlchemyError("Database error")
        entities_data = [{"name": "test1"}]
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.create_many(entities_data)
        
        mock_session.rollback.assert_called_once()
    
    # READ Operations Tests
    
    def test_get_by_id_found(self, repository, mock_session):
        """Test getting entity by ID when found"""
        # Arrange
        mock_entity = TestModel(id=1, name="test")
        mock_session.get.return_value = mock_entity
        
        # Act
        result = repository.get_by_id(1)
        
        # Assert
        mock_session.get.assert_called_once_with(TestModel, 1)
        assert result == mock_entity
    
    def test_get_by_id_not_found(self, repository, mock_session):
        """Test getting entity by ID when not found"""
        # Arrange
        mock_session.get.return_value = None
        
        # Act
        result = repository.get_by_id(999)
        
        # Assert
        assert result is None
    
    def test_get_by_id_database_error(self, repository, mock_session):
        """Test get_by_id with database error"""
        # Arrange
        mock_session.get.side_effect = SQLAlchemyError("Database error")
        
        # Act
        result = repository.get_by_id(1)
        
        # Assert
        assert result is None
    
    def test_get_all_no_ordering(self, repository, mock_session):
        """Test getting all entities without ordering"""
        # Arrange
        mock_entities = [TestModel(id=1), TestModel(id=2)]
        mock_query = mock_session.query.return_value
        mock_query.all.return_value = mock_entities
        
        # Act
        result = repository.get_all()
        
        # Assert
        mock_session.query.assert_called_once_with(TestModel)
        assert result == mock_entities
    
    def test_get_all_with_ordering(self, repository, mock_session):
        """Test getting all entities with ordering"""
        # Arrange
        mock_entities = [TestModel(id=2), TestModel(id=1)]
        mock_query = mock_session.query.return_value
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_entities
        
        # Mock the model attribute
        with patch.object(TestModel, 'name', create=True):
            # Act
            result = repository.get_all(order_by='name', order=SortOrder.DESC)
            
            # Assert
            assert result == mock_entities
            mock_query.order_by.assert_called_once()
    
    def test_get_paginated(self, repository, mock_session):
        """Test paginated query"""
        # Arrange
        mock_entities = [TestModel(id=1), TestModel(id=2)]
        mock_query = mock_session.query.return_value
        mock_query.count.return_value = 10
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entities
        
        pagination = PaginationParams(page=2, per_page=2)
        
        # Act
        result = repository.get_paginated(pagination)
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert result.items == mock_entities
        assert result.total == 10
        assert result.page == 2
        assert result.per_page == 2
        assert result.pages == 5
        assert result.has_prev is True
        assert result.has_next is True
        mock_query.offset.assert_called_once_with(2)  # (page-1) * per_page
        mock_query.limit.assert_called_once_with(2)
    
    def test_find_by(self, repository, mock_session):
        """Test finding entities by filters"""
        # Arrange
        mock_entities = [TestModel(id=1, name="test")]
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_entities
        
        # Mock the model attribute
        with patch.object(TestModel, 'name', create=True):
            # Act
            result = repository.find_by(name="test")
            
            # Assert
            assert result == mock_entities
            mock_query.filter.assert_called()
    
    def test_find_one_by(self, repository, mock_session):
        """Test finding single entity by filters"""
        # Arrange
        mock_entity = TestModel(id=1, name="test")
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_entity]
        
        with patch.object(TestModel, 'name', create=True):
            # Act
            result = repository.find_one_by(name="test")
            
            # Assert
            assert result == mock_entity
    
    def test_exists_true(self, repository, mock_session):
        """Test exists when entity exists"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = TestModel(id=1)
        
        with patch.object(TestModel, 'name', create=True):
            # Act
            result = repository.exists(name="test")
            
            # Assert
            assert result is True
    
    def test_exists_false(self, repository, mock_session):
        """Test exists when entity doesn't exist"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        with patch.object(TestModel, 'name', create=True):
            # Act
            result = repository.exists(name="nonexistent")
            
            # Assert
            assert result is False
    
    def test_count(self, repository, mock_session):
        """Test counting entities"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        
        with patch.object(TestModel, 'value', create=True):
            # Act
            result = repository.count(value=42)
            
            # Assert
            assert result == 5
    
    # UPDATE Operations Tests
    
    def test_update_success(self, repository, mock_session):
        """Test successful entity update"""
        # Arrange
        entity = TestModel(id=1, name="old", value=1)
        
        # Act
        result = repository.update(entity, name="new", value=2)
        
        # Assert
        assert entity.name == "new"
        assert entity.value == 2
        mock_session.flush.assert_called_once()
        assert result == entity
    
    def test_update_database_error(self, repository, mock_session):
        """Test update with database error"""
        # Arrange
        entity = TestModel(id=1, name="test")
        mock_session.flush.side_effect = SQLAlchemyError("Database error")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.update(entity, name="new")
        
        mock_session.rollback.assert_called_once()
    
    def test_update_by_id_found(self, repository, mock_session):
        """Test updating entity by ID when found"""
        # Arrange
        entity = TestModel(id=1, name="old")
        mock_session.get.return_value = entity
        
        # Act
        result = repository.update_by_id(1, name="new")
        
        # Assert
        assert result == entity
        assert entity.name == "new"
    
    def test_update_by_id_not_found(self, repository, mock_session):
        """Test updating entity by ID when not found"""
        # Arrange
        mock_session.get.return_value = None
        
        # Act
        result = repository.update_by_id(999, name="new")
        
        # Assert
        assert result is None
    
    def test_update_many(self, repository, mock_session):
        """Test updating multiple entities"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3
        
        with patch.object(TestModel, 'value', create=True):
            # Act
            result = repository.update_many(
                filters={"value": 1},
                updates={"value": 2}
            )
            
            # Assert
            assert result == 3
            mock_query.update.assert_called_once_with(
                {"value": 2},
                synchronize_session=False
            )
    
    # DELETE Operations Tests
    
    def test_delete_success(self, repository, mock_session):
        """Test successful entity deletion"""
        # Arrange
        entity = TestModel(id=1, name="test")
        
        # Act
        result = repository.delete(entity)
        
        # Assert
        mock_session.delete.assert_called_once_with(entity)
        mock_session.flush.assert_called_once()
        assert result is True
    
    def test_delete_database_error(self, repository, mock_session):
        """Test delete with database error"""
        # Arrange
        entity = TestModel(id=1)
        mock_session.flush.side_effect = SQLAlchemyError("Database error")
        
        # Act
        result = repository.delete(entity)
        
        # Assert
        mock_session.rollback.assert_called_once()
        assert result is False
    
    def test_delete_by_id_found(self, repository, mock_session):
        """Test deleting entity by ID when found"""
        # Arrange
        entity = TestModel(id=1)
        mock_session.get.return_value = entity
        
        # Act
        result = repository.delete_by_id(1)
        
        # Assert
        mock_session.delete.assert_called_once_with(entity)
        assert result is True
    
    def test_delete_by_id_not_found(self, repository, mock_session):
        """Test deleting entity by ID when not found"""
        # Arrange
        mock_session.get.return_value = None
        
        # Act
        result = repository.delete_by_id(999)
        
        # Assert
        assert result is False
    
    def test_delete_many(self, repository, mock_session):
        """Test deleting multiple entities"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5
        
        with patch.object(TestModel, 'value', create=True):
            # Act
            result = repository.delete_many({"value": 1})
            
            # Assert
            assert result == 5
            mock_query.delete.assert_called_once_with(synchronize_session=False)
    
    # Transaction Management Tests
    
    def test_commit_success(self, repository, mock_session):
        """Test successful commit"""
        # Act
        repository.commit()
        
        # Assert
        mock_session.commit.assert_called_once()
    
    def test_commit_error(self, repository, mock_session):
        """Test commit with error"""
        # Arrange
        mock_session.commit.side_effect = SQLAlchemyError("Commit failed")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.commit()
        
        mock_session.rollback.assert_called_once()
    
    def test_rollback(self, repository, mock_session):
        """Test rollback"""
        # Act
        repository.rollback()
        
        # Assert
        mock_session.rollback.assert_called_once()
    
    def test_flush(self, repository, mock_session):
        """Test flush"""
        # Act
        repository.flush()
        
        # Assert
        mock_session.flush.assert_called_once()


class TestPaginationParams:
    """Test PaginationParams dataclass"""
    
    def test_default_values(self):
        """Test default pagination values"""
        params = PaginationParams()
        assert params.page == 1
        assert params.per_page == 20
        assert params.offset == 0
        assert params.limit == 20
    
    def test_custom_values(self):
        """Test custom pagination values"""
        params = PaginationParams(page=3, per_page=10)
        assert params.page == 3
        assert params.per_page == 10
        assert params.offset == 20  # (3-1) * 10
        assert params.limit == 10


class TestPaginatedResult:
    """Test PaginatedResult dataclass"""
    
    def test_pagination_calculations(self):
        """Test pagination metadata calculations"""
        result = PaginatedResult(
            items=["item1", "item2"],
            total=25,
            page=2,
            per_page=10
        )
        
        assert result.pages == 3  # 25 items / 10 per page = 3 pages
        assert result.has_prev is True
        assert result.has_next is True
        assert result.prev_page == 1
        assert result.next_page == 3
    
    def test_first_page(self):
        """Test first page metadata"""
        result = PaginatedResult(
            items=["item1"],
            total=10,
            page=1,
            per_page=5
        )
        
        assert result.has_prev is False
        assert result.has_next is True
        assert result.prev_page is None
        assert result.next_page == 2
    
    def test_last_page(self):
        """Test last page metadata"""
        result = PaginatedResult(
            items=["item1"],
            total=10,
            page=2,
            per_page=5
        )
        
        assert result.has_prev is True
        assert result.has_next is False
        assert result.prev_page == 1
        assert result.next_page is None
    
    def test_single_page(self):
        """Test single page metadata"""
        result = PaginatedResult(
            items=["item1", "item2"],
            total=2,
            page=1,
            per_page=10
        )
        
        assert result.pages == 1
        assert result.has_prev is False
        assert result.has_next is False