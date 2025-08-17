# tests/unit/services/test_contact_service_pagination.py
"""
Unit tests for ContactService pagination functionality.
Following TDD principles - these tests must fail first.
"""

import pytest
from unittest.mock import Mock, patch
from services.contact_service_refactored import ContactService
from repositories.contact_repository import ContactRepository
from crm_database import Contact
from services.common.result import PagedResult


class TestContactServicePagination:
    """Test ContactService pagination methods"""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository for testing"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def contact_service(self, mock_repository):
        """Create ContactService with mocked repository"""
        return ContactService(contact_repository=mock_repository)
    
    def test_get_contacts_page_happy_path(self, contact_service, mock_repository):
        """Test successful contact pagination"""
        # Arrange
        mock_contacts = [
            Contact(id=1, first_name='John', last_name='Doe', phone='+15551111111'),
            Contact(id=2, first_name='Jane', last_name='Smith', phone='+15552222222')
        ]
        
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': mock_contacts,
            'total_count': 2,
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50
        )
        
        # Assert
        assert 'contacts' in result
        assert 'total_count' in result
        assert result['total_count'] == 2
        assert len(result['contacts']) == 2
        mock_repository.get_paginated_contacts.assert_called_once_with(
            search_query='',
            filter_type='all', 
            sort_by='name',
            page=1,
            per_page=50
        )
    
    def test_get_contacts_page_with_search(self, contact_service, mock_repository):
        """Test contact pagination with search query"""
        # Arrange
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0,
            'has_prev': False,
            'has_next': False
        }
        
        # Act
        result = contact_service.get_contacts_page(
            search_query='John',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=20
        )
        
        # Assert
        mock_repository.get_paginated_contacts.assert_called_once_with(
            search_query='John',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=20
        )
    
    def test_get_contacts_page_with_filters(self, contact_service, mock_repository):
        """Test contact pagination with filters"""
        # Arrange
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0,
            'has_prev': False,
            'has_next': False
        }
        
        # Act
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='has_email',
            sort_by='name',
            page=1,
            per_page=50
        )
        
        # Assert
        mock_repository.get_paginated_contacts.assert_called_once_with(
            search_query='',
            filter_type='has_email',
            sort_by='name',
            page=1,
            per_page=50
        )
    
    def test_get_contacts_page_pagination_parameters(self, contact_service, mock_repository):
        """Test contact pagination with different page parameters"""
        # Arrange
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': [],
            'total_count': 100,
            'page': 2,
            'total_pages': 5,
            'has_prev': True,
            'has_next': True
        }
        
        # Act
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='all',
            sort_by='created_at',
            page=2,
            per_page=20
        )
        
        # Assert
        assert result['page'] == 2
        assert result['total_pages'] == 5
        assert result['has_prev'] is True
        assert result['has_next'] is True
        mock_repository.get_paginated_contacts.assert_called_once_with(
            search_query='',
            filter_type='all',
            sort_by='created_at',
            page=2,
            per_page=20
        )
    
    def test_get_contacts_page_method_exists(self, contact_service):
        """Test that get_contacts_page method exists on ContactService"""
        # This test will fail until we implement the method
        assert hasattr(contact_service, 'get_contacts_page')
        assert callable(getattr(contact_service, 'get_contacts_page'))
