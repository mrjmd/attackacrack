"""
Simple test for BaseRepository to verify it works
"""

from repositories.base_repository import (
    BaseRepository,
    PaginationParams,
    PaginatedResult,
    SortOrder
)
from sqlalchemy.orm import Session


class TestModel:
    """Test model"""
    id = None
    name = None


class ConcreteRepository(BaseRepository[TestModel]):
    """Concrete implementation for testing"""
    def search(self, query, fields=None):
        return []


def test_pagination_params():
    """Test PaginationParams"""
    params = PaginationParams(page=2, per_page=10)
    assert params.offset == 10
    assert params.limit == 10


def test_paginated_result():
    """Test PaginatedResult"""
    result = PaginatedResult(
        items=['a', 'b'],
        total=25,
        page=2,
        per_page=10
    )
    assert result.pages == 3
    assert result.has_prev is True
    assert result.has_next is True
    assert result.prev_page == 1
    assert result.next_page == 3


def test_repository_creation():
    """Test that repository can be created"""
    from unittest.mock import MagicMock
    session = MagicMock(spec=Session)
    repo = ConcreteRepository(session, TestModel)
    assert repo.session == session
    assert repo.model_class == TestModel