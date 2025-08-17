"""
Unit tests for refactored ContactService with ContactRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from services.contact_service_refactored import ContactService
from repositories.contact_repository import ContactRepository
from repositories.base_repository import PaginatedResult
from crm_database import Contact


class TestContactServiceRefactored:
    """Test suite for refactored ContactService"""
    
    @pytest.fixture
    def mock_repository(self):
        """Mock ContactRepository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def service(self, mock_repository, mock_session):
        """Create ContactService with mocked dependencies"""
        return ContactService(repository=mock_repository, session=mock_session)
    
    def test_init_without_repository(self, mock_session):
        """Test initialization without repository creates one"""
        service = ContactService(session=mock_session)
        assert service.repository is not None
        assert isinstance(service.repository, ContactRepository)
    
    def test_init_with_repository(self, mock_repository):
        """Test initialization with repository"""
        service = ContactService(repository=mock_repository)
        assert service.repository == mock_repository
    
    def test_get_contacts_page(self, service, mock_repository):
        """Test getting paginated contacts"""
        # Setup mock return
        mock_contacts = [
            Mock(id=1, first_name="John", last_name="Doe"),
            Mock(id=2, first_name="Jane", last_name="Smith")
        ]
        
        mock_repository.get_contacts_with_filter.return_value = PaginatedResult(
            items=mock_contacts,
            total=2,
            page=1,
            per_page=50
        )
        
        # Call method
        result = service.get_contacts_page(
            search_query="test",
            filter_type="has_phone",
            sort_by="name",
            page=1,
            per_page=50
        )
        
        # Verify
        assert result['total_count'] == 2
        assert result['page'] == 1
        assert len(result['contacts']) == 2
        mock_repository.get_contacts_with_filter.assert_called_once()
    
    def test_get_contact_by_id(self, service, mock_repository):
        """Test getting contact by ID"""
        mock_contact = Mock(id=1, first_name="John")
        mock_repository.get_by_id.return_value = mock_contact
        
        result = service.get_contact_by_id(1)
        
        assert result == mock_contact
        mock_repository.get_by_id.assert_called_once_with(1)
    
    def test_create_contact_success(self, service, mock_repository):
        """Test successful contact creation"""
        mock_contact = Mock(id=1, first_name="John")
        mock_repository.create.return_value = mock_contact
        
        success, contact, error = service.create_contact(
            first_name="John",
            last_name="Doe",
            phone="+15551234567"
        )
        
        assert success is True
        assert contact == mock_contact
        assert error is None
        mock_repository.create.assert_called_once()
        mock_repository.commit.assert_called_once()
    
    def test_create_contact_integrity_error(self, service, mock_repository):
        """Test contact creation with integrity error"""
        from sqlalchemy.exc import IntegrityError
        mock_repository.create.side_effect = IntegrityError("", "", "unique constraint")
        
        success, contact, error = service.create_contact(
            phone="+15551234567"
        )
        
        assert success is False
        assert contact is None
        assert "already exists" in error
        mock_repository.rollback.assert_called_once()
    
    def test_update_contact_success(self, service, mock_repository):
        """Test successful contact update"""
        mock_contact = Mock(id=1, first_name="John")
        mock_repository.update_by_id.return_value = mock_contact
        
        success, contact, error = service.update_contact(
            1,
            first_name="Jane"
        )
        
        assert success is True
        assert contact == mock_contact
        assert error is None
        mock_repository.update_by_id.assert_called_once_with(1, first_name="Jane")
        mock_repository.commit.assert_called_once()
    
    def test_update_contact_not_found(self, service, mock_repository):
        """Test updating non-existent contact"""
        mock_repository.update_by_id.return_value = None
        
        success, contact, error = service.update_contact(999, first_name="Jane")
        
        assert success is False
        assert contact is None
        assert error == "Contact not found"
    
    def test_delete_contact_success(self, service, mock_repository):
        """Test successful contact deletion"""
        mock_repository.delete_by_id.return_value = True
        
        success, error = service.delete_contact(1)
        
        assert success is True
        assert error is None
        mock_repository.delete_by_id.assert_called_once_with(1)
        mock_repository.commit.assert_called_once()
    
    def test_delete_contact_not_found(self, service, mock_repository):
        """Test deleting non-existent contact"""
        mock_repository.delete_by_id.return_value = False
        
        success, error = service.delete_contact(999)
        
        assert success is False
        assert error == "Contact not found"
    
    def test_search_contacts(self, service, mock_repository):
        """Test searching contacts"""
        mock_contacts = [Mock(), Mock()]
        mock_repository.search.return_value = mock_contacts
        
        results = service.search_contacts("john")
        
        assert results == mock_contacts
        mock_repository.search.assert_called_once_with("john")
    
    def test_find_or_create_contact_existing(self, service, mock_repository):
        """Test find_or_create with existing contact"""
        mock_contact = Mock(id=1, phone="+15551234567", email=None)
        mock_repository.find_by_phone.return_value = mock_contact
        
        result = service.find_or_create_contact(
            phone="+15551234567",
            email="john@example.com"
        )
        
        assert result == mock_contact
        # Should update with new email
        mock_repository.update.assert_called_once()
        mock_repository.commit.assert_called_once()
    
    def test_find_or_create_contact_new(self, service, mock_repository):
        """Test find_or_create with new contact"""
        mock_repository.find_by_phone.return_value = None
        mock_contact = Mock(id=1)
        mock_repository.create.return_value = mock_contact
        
        result = service.find_or_create_contact(
            phone="+15551234567",
            first_name="John"
        )
        
        assert result == mock_contact
        mock_repository.create.assert_called_once_with(
            phone="+15551234567",
            first_name="John"
        )
        mock_repository.commit.assert_called_once()
    
    def test_bulk_update_tags(self, service, mock_repository):
        """Test bulk updating tags"""
        mock_repository.bulk_update_tags.return_value = 5
        
        count = service.bulk_update_tags(
            contact_ids=[1, 2, 3, 4, 5],
            tags=["customer", "vip"],
            operation="add"
        )
        
        assert count == 5
        mock_repository.bulk_update_tags.assert_called_once_with(
            [1, 2, 3, 4, 5],
            ["customer", "vip"],
            "add"
        )
        mock_repository.commit.assert_called_once()
    
    def test_merge_duplicate_contacts_success(self, service, mock_repository):
        """Test successful contact merge"""
        mock_merged = Mock(id=1)
        mock_repository.merge_contacts.return_value = mock_merged
        
        success, contact, error = service.merge_duplicate_contacts(1, 2)
        
        assert success is True
        assert contact == mock_merged
        assert error is None
        mock_repository.merge_contacts.assert_called_once_with(1, 2)
        mock_repository.commit.assert_called_once()
    
    def test_find_duplicates(self, service, mock_repository):
        """Test finding duplicate contacts"""
        mock_duplicates = [
            ("+15551234567", 2),
            ("+15559876543", 3)
        ]
        mock_repository.find_duplicates.return_value = mock_duplicates
        
        results = service.find_duplicates("phone")
        
        assert results == mock_duplicates
        mock_repository.find_duplicates.assert_called_once_with("phone")
    
    def test_get_contact_stats(self, service, mock_repository):
        """Test getting contact statistics"""
        mock_stats = {
            'total': 1000,
            'with_phone': 950,
            'with_email': 600,
            'opted_out': 50
        }
        mock_repository.get_contact_stats.return_value = mock_stats
        
        stats = service.get_contact_stats()
        
        assert stats == mock_stats
        mock_repository.get_contact_stats.assert_called_once()
    
    def test_export_contacts_to_csv(self, service, mock_repository):
        """Test exporting contacts to CSV"""
        mock_contacts = [
            Mock(
                id=1, first_name="John", last_name="Doe",
                phone="+15551234567", email="john@example.com",
                company="Acme", address="123 Main St",
                city="Boston", state="MA", zip_code="02101",
                tags=["customer"], created_at=None, updated_at=None
            )
        ]
        mock_repository.get_all.return_value = mock_contacts
        
        csv_content = service.export_contacts_to_csv()
        
        assert "John" in csv_content
        assert "Doe" in csv_content
        assert "+15551234567" in csv_content
        assert "john@example.com" in csv_content
        mock_repository.get_all.assert_called_once()
    
    def test_import_contacts_from_csv(self, service, mock_repository):
        """Test importing contacts from CSV"""
        csv_content = """phone,first_name,last_name,email
+15551234567,John,Doe,john@example.com
+15559876543,Jane,Smith,jane@example.com"""
        
        mock_repository.find_by_phone.side_effect = [None, None]  # No existing contacts
        
        created, updated, errors = service.import_contacts_from_csv(csv_content)
        
        assert created == 2
        assert updated == 0
        assert len(errors) == 0
        assert mock_repository.create.call_count == 2
        mock_repository.commit.assert_called_once()