"""Unit tests for PropertyRepository - TDD RED PHASE

Test the PropertyRepository implementation following strict TDD methodology.
These tests MUST fail initially to verify proper TDD workflow.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from crm_database import Property
from repositories.property_repository import PropertyRepository
from repositories.base_repository import PaginationParams, PaginatedResult
from tests.fixtures.factories.property_factory import PropertyFactory
from tests.fixtures.factories.contact_factory import ContactFactory


class TestPropertyRepository:
    """Test suite for PropertyRepository database operations"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session for testing"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create PropertyRepository instance with mocked session"""
        return PropertyRepository(session=mock_session, model_class=Property)
    
    @pytest.fixture
    def sample_property_data(self):
        """Sample property data for testing"""
        return {
            'address': '123 Main St',
            'contact_id': 1,  # Use a simple ID for testing
            'property_type': 'residential'
        }
    
    @pytest.fixture
    def sample_property(self, sample_property_data):
        """Sample Property instance for testing"""
        return PropertyFactory.build(**sample_property_data)

    # ============================================
    # CREATE OPERATIONS
    # ============================================
    
    def test_create_property_success(self, repository, mock_session, sample_property_data):
        """Test successful property creation"""
        # Arrange
        expected_property = Property(**sample_property_data)
        expected_property.id = 1
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        
        with patch.object(Property, '__init__', return_value=None) as mock_init:
            with patch('repositories.property_repository.Property', return_value=expected_property):
                # Act
                result = repository.create(**sample_property_data)
                
                # Assert
                assert result == expected_property
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
                mock_session.refresh.assert_called_once_with(expected_property)
    
    def test_create_property_with_database_error(self, repository, mock_session, sample_property_data):
        """Test property creation with database error"""
        # Arrange
        mock_session.commit.side_effect = SQLAlchemyError("Database error")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.create(**sample_property_data)
        
        mock_session.rollback.assert_called_once()
    
    def test_create_property_missing_required_fields(self, repository):
        """Test property creation with missing required fields"""
        # Arrange
        invalid_data = {'address': '123 Main St'}  # Missing contact_id
        
        # Act & Assert
        with pytest.raises(ValueError, match="contact_id is required"):
            repository.create(**invalid_data)

    # ============================================
    # READ OPERATIONS
    # ============================================
    
    def test_get_property_by_id_found(self, repository, mock_session, sample_property):
        """Test retrieving property by ID when found"""
        # Arrange
        property_id = 1
        mock_session.get.return_value = sample_property
        
        # Act
        result = repository.get_by_id(property_id)
        
        # Assert
        assert result == sample_property
        mock_session.get.assert_called_once_with(Property, property_id)
    
    def test_get_property_by_id_not_found(self, repository, mock_session):
        """Test retrieving property by ID when not found"""
        # Arrange
        property_id = 999
        mock_session.get.return_value = None
        
        # Act
        result = repository.get_by_id(property_id)
        
        # Assert
        assert result is None
        mock_session.get.assert_called_once_with(Property, property_id)
    
    def test_get_all_properties(self, repository, mock_session):
        """Test retrieving all properties"""
        # Arrange
        expected_properties = [PropertyFactory.build() for _ in range(3)]
        mock_query = Mock()
        mock_query.all.return_value = expected_properties
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_all()
        
        # Assert
        assert result == expected_properties
        mock_session.query.assert_called_once_with(Property)
        mock_query.all.assert_called_once()
    
    def test_find_properties_by_contact_id(self, repository, mock_session):
        """Test finding properties by contact ID"""
        # Arrange
        contact_id = 1
        expected_properties = [PropertyFactory.build(contact_id=contact_id) for _ in range(2)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_properties
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_contact_id(contact_id)
        
        # Assert
        assert result == expected_properties
        mock_session.query.assert_called_once_with(Property)
        mock_query.filter_by.assert_called_once_with(contact_id=contact_id)
    
    def test_find_properties_by_address_partial_match(self, repository, mock_session):
        """Test finding properties by partial address match"""
        # Arrange
        address_part = "Main St"
        expected_properties = [PropertyFactory.build(address="123 Main St")]
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = expected_properties
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_address_contains(address_part)
        
        # Assert
        assert result == expected_properties
        mock_session.query.assert_called_once_with(Property)
        mock_query.filter.assert_called_once()
    
    def test_find_properties_by_type(self, repository, mock_session):
        """Test finding properties by property type"""
        # Arrange
        property_type = "residential"
        expected_properties = [PropertyFactory.build(property_type=property_type)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_properties
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_type(property_type)
        
        # Assert
        assert result == expected_properties
        mock_session.query.assert_called_once_with(Property)
        mock_query.filter_by.assert_called_once_with(property_type=property_type)

    # ============================================
    # UPDATE OPERATIONS
    # ============================================
    
    def test_update_property_success(self, repository, mock_session, sample_property):
        """Test successful property update"""
        # Arrange
        updates = {'address': '456 Oak Ave', 'property_type': 'commercial'}
        mock_session.commit.return_value = None
        
        # Act
        result = repository.update(sample_property, **updates)
        
        # Assert
        assert result == sample_property
        assert sample_property.address == '456 Oak Ave'
        assert sample_property.property_type == 'commercial'
        mock_session.commit.assert_called_once()
    
    def test_update_property_with_database_error(self, repository, mock_session, sample_property):
        """Test property update with database error"""
        # Arrange
        updates = {'address': '456 Oak Ave'}
        mock_session.commit.side_effect = SQLAlchemyError("Update failed")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.update(sample_property, **updates)
        
        mock_session.rollback.assert_called_once()
    
    def test_update_property_by_id_found(self, repository, mock_session, sample_property):
        """Test updating property by ID when found"""
        # Arrange
        property_id = 1
        updates = {'property_type': 'industrial'}
        mock_session.get.return_value = sample_property
        mock_session.commit.return_value = None
        
        # Act
        result = repository.update_by_id(property_id, **updates)
        
        # Assert
        assert result == sample_property
        assert sample_property.property_type == 'industrial'
        mock_session.get.assert_called_once_with(Property, property_id)
        mock_session.commit.assert_called_once()
    
    def test_update_property_by_id_not_found(self, repository, mock_session):
        """Test updating property by ID when not found"""
        # Arrange
        property_id = 999
        updates = {'property_type': 'industrial'}
        mock_session.get.return_value = None
        
        # Act
        result = repository.update_by_id(property_id, **updates)
        
        # Assert
        assert result is None
        mock_session.get.assert_called_once_with(Property, property_id)
        mock_session.commit.assert_not_called()

    # ============================================
    # DELETE OPERATIONS
    # ============================================
    
    def test_delete_property_success(self, repository, mock_session, sample_property):
        """Test successful property deletion"""
        # Arrange
        mock_session.delete.return_value = None
        mock_session.commit.return_value = None
        
        # Act
        result = repository.delete(sample_property)
        
        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(sample_property)
        mock_session.commit.assert_called_once()
    
    def test_delete_property_with_database_error(self, repository, mock_session, sample_property):
        """Test property deletion with database error"""
        # Arrange
        mock_session.commit.side_effect = SQLAlchemyError("Delete failed")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.delete(sample_property)
        
        mock_session.rollback.assert_called_once()
    
    def test_delete_property_by_id_found(self, repository, mock_session, sample_property):
        """Test deleting property by ID when found"""
        # Arrange
        property_id = 1
        mock_session.get.return_value = sample_property
        mock_session.delete.return_value = None
        mock_session.commit.return_value = None
        
        # Act
        result = repository.delete_by_id(property_id)
        
        # Assert
        assert result is True
        mock_session.get.assert_called_once_with(Property, property_id)
        mock_session.delete.assert_called_once_with(sample_property)
        mock_session.commit.assert_called_once()
    
    def test_delete_property_by_id_not_found(self, repository, mock_session):
        """Test deleting property by ID when not found"""
        # Arrange
        property_id = 999
        mock_session.get.return_value = None
        
        # Act
        result = repository.delete_by_id(property_id)
        
        # Assert
        assert result is False
        mock_session.get.assert_called_once_with(Property, property_id)
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()

    # ============================================
    # PAGINATION OPERATIONS
    # ============================================
    
    def test_get_paginated_properties(self, repository, mock_session):
        """Test paginated property retrieval"""
        # Arrange
        pagination = PaginationParams(page=1, per_page=10)
        expected_properties = [PropertyFactory.build() for _ in range(5)]
        
        mock_query = Mock()
        mock_query.offset.return_value.limit.return_value.all.return_value = expected_properties
        mock_query.count.return_value = 5
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_paginated(pagination)
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert result.items == expected_properties
        assert result.total == 5
        assert result.page == 1
        assert result.per_page == 10
        
        mock_session.query.assert_called_with(Property)
        mock_query.offset.assert_called_once_with(0)
        mock_query.offset.return_value.limit.assert_called_once_with(10)

    # ============================================
    # SPECIALIZED BUSINESS LOGIC OPERATIONS
    # ============================================
    
    def test_get_properties_with_jobs(self, repository, mock_session):
        """Test finding properties that have associated jobs"""
        # Arrange
        expected_properties = [PropertyFactory.build()]
        mock_query = Mock()
        mock_query.join.return_value.distinct.return_value.all.return_value = expected_properties
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_properties_with_jobs()
        
        # Assert
        assert result == expected_properties
        mock_session.query.assert_called_once_with(Property)
        mock_query.join.assert_called_once()
        mock_query.join.return_value.distinct.assert_called_once()
    
    def test_count_properties_by_type(self, repository, mock_session):
        """Test counting properties grouped by type"""
        # Arrange
        expected_counts = [('residential', 5), ('commercial', 3), ('industrial', 1)]
        mock_query = Mock()
        mock_group_by = Mock()
        mock_query.group_by.return_value = mock_group_by
        mock_group_by.all.return_value = expected_counts
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.count_by_property_type()
        
        # Assert
        assert result == expected_counts
        mock_session.query.assert_called_once()
    
    def test_search_properties_by_address_and_type(self, repository, mock_session):
        """Test complex search with multiple criteria"""
        # Arrange
        address_query = "Main"
        property_type = "residential"
        expected_properties = [PropertyFactory.build()]
        
        mock_query = Mock()
        mock_query.filter.return_value.filter_by.return_value.all.return_value = expected_properties
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search_properties(address_query=address_query, property_type=property_type)
        
        # Assert
        assert result == expected_properties
        mock_session.query.assert_called_once_with(Property)
        mock_query.filter.assert_called_once()
        mock_query.filter.return_value.filter_by.assert_called_once_with(property_type=property_type)


class TestPropertyRepositoryIntegration:
    """Integration tests for PropertyRepository with real database session"""
    
    def test_repository_integration_with_real_session(self, db_session):
        """Test repository with real database session"""
        # Arrange
        repository = PropertyRepository(session=db_session, model_class=Property)
        contact = ContactFactory.create()
        property_data = {
            'address': '789 Integration Ave',
            'contact_id': contact.id,
            'property_type': 'residential'
        }
        
        # Act
        created_property = repository.create(**property_data)
        db_session.commit()
        
        found_property = repository.get_by_id(created_property.id)
        
        # Assert
        assert found_property is not None
        assert found_property.address == '789 Integration Ave'
        assert found_property.contact_id == contact.id
        assert found_property.property_type == 'residential'
    
    def test_property_relationship_with_contact(self, db_session):
        """Test property-contact relationship through repository"""
        # Arrange
        repository = PropertyRepository(session=db_session, model_class=Property)
        contact = ContactFactory.create(first_name="Test", last_name="Owner")
        
        property_data = {
            'address': '555 Relationship St',
            'contact_id': contact.id,
            'property_type': 'commercial'
        }
        
        # Act
        created_property = repository.create(**property_data)
        db_session.commit()
        
        properties_for_contact = repository.find_by_contact_id(contact.id)
        
        # Assert
        assert len(properties_for_contact) == 1
        assert properties_for_contact[0].id == created_property.id
        assert properties_for_contact[0].contact.first_name == "Test"
        assert properties_for_contact[0].contact.last_name == "Owner"
