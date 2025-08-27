# tests/integration/routes/test_contact_list_filtered_count.py
"""
TEST-DRIVEN DEVELOPMENT - RED PHASE
Tests for displaying filtered count instead of total count on contact list page.
These tests MUST FAIL initially before implementation.
"""

import pytest
from crm_database import Contact, CampaignList, CampaignListMember


class TestContactListFilteredCount:
    """Test that contact list displays filtered count, not total count"""
    
    def test_displays_filtered_count_when_searching(self, authenticated_client_with_clean_db, clean_db):
        """Test filtered count is shown when search query is applied"""
        # Arrange - Create test contacts with different names
        contact1 = Contact(
            first_name='John',
            last_name='Smith',
            phone='+15551111111',
            email='john@example.com'
        )
        contact2 = Contact(
            first_name='Jane',
            last_name='Doe',
            phone='+15552222222',
            email='jane@example.com'
        )
        contact3 = Contact(
            first_name='Bob',
            last_name='Johnson',
            phone='+15553333333',
            email='bob@example.com'
        )
        clean_db.add_all([contact1, contact2, contact3])
        clean_db.commit()
        
        # Act - Search for 'John' (should match 2: John Smith and Bob Johnson)
        response = authenticated_client_with_clean_db.get('/contacts/?search=john')
        
        # Assert - Should show "2 total contacts" not "3 total contacts"
        assert response.status_code == 200
        assert b'2 total contacts' in response.data
        assert b'3 total contacts' not in response.data
        
        # Should show both matching contacts
        assert b'John Smith' in response.data
        assert b'Bob Johnson' in response.data
        assert b'Jane Doe' not in response.data
    
    def test_displays_filtered_count_with_filter_type(self, authenticated_client_with_clean_db, clean_db):
        """Test filtered count is shown when filter type is applied"""
        # Arrange - Create contacts with and without phone numbers
        contact_with_phone = Contact(
            first_name='HasPhone',
            last_name='User',
            phone='+15551111111',
            email='hasphone@example.com'
        )
        contact_without_phone = Contact(
            first_name='NoPhone',
            last_name='User',
            phone=None,  # No phone number
            email='nophone@example.com'
        )
        clean_db.add_all([contact_with_phone, contact_without_phone])
        clean_db.commit()
        
        # Act - Filter by 'has_phone'
        response = authenticated_client_with_clean_db.get('/contacts/?filter=has_phone')
        
        # Assert - Should show "1 total contacts" not "2 total contacts"
        assert response.status_code == 200
        assert b'1 total contacts' in response.data
        assert b'2 total contacts' not in response.data
        
        # Should only show contact with phone
        assert b'HasPhone User' in response.data
        assert b'NoPhone User' not in response.data
    
    def test_displays_full_count_when_no_filters_applied(self, authenticated_client_with_clean_db, clean_db):
        """Test full count is shown when no filters are applied"""
        # Arrange - Create multiple contacts
        contacts = [Contact(first_name=f'Contact{i}', last_name='Test') for i in range(5)]
        for contact in contacts:
            clean_db.add(contact)
        clean_db.commit()
        
        # Act - Visit contacts page with no filters
        response = authenticated_client_with_clean_db.get('/contacts/')
        
        # Assert - Should show all contacts count (5 + any seeded contacts)
        assert response.status_code == 200
        # Note: There might be seeded contacts from fixtures, so check for at least 5
        response_text = response.data.decode('utf-8')
        
        # Extract the count from the response
        import re
        count_match = re.search(r'(\d+) total contacts', response_text)
        assert count_match, "Should display total contacts count"
        displayed_count = int(count_match.group(1))
        assert displayed_count >= 5, f"Should show at least 5 contacts, got {displayed_count}"
    
    def test_displays_filtered_count_with_combined_filters(self, authenticated_client_with_clean_db, clean_db):
        """Test filtered count with both search and filter type applied"""
        # Arrange - Create contacts with different combinations
        contact1 = Contact(
            first_name='John',
            last_name='Smith',
            phone='+15551111111',  # Has phone
            email='john@example.com'
        )
        contact2 = Contact(
            first_name='John',
            last_name='Doe',
            phone=None,  # No phone
            email='john.doe@example.com'
        )
        contact3 = Contact(
            first_name='Jane',
            last_name='Smith',
            phone='+15553333333',  # Has phone
            email='jane@example.com'
        )
        clean_db.add_all([contact1, contact2, contact3])
        clean_db.commit()
        
        # Act - Search for 'John' AND filter by 'has_phone'
        response = authenticated_client_with_clean_db.get('/contacts/?search=john&filter=has_phone')
        
        # Assert - Should show "1 total contacts" (only John Smith matches both)
        assert response.status_code == 200
        assert b'1 total contacts' in response.data
        
        # Should only show John Smith
        assert b'John Smith' in response.data
        assert b'John Doe' not in response.data
        assert b'Jane Smith' not in response.data
    
    def test_template_shows_filtered_vs_total_distinction(self, authenticated_client_with_clean_db, clean_db):
        """Test that template clearly shows this is a filtered count when filters are applied"""
        # Arrange - Create test data
        contacts_with_phone = [Contact(first_name=f'WithPhone{i}', last_name='Test', phone=f'+1555111111{i}') for i in range(10)]
        contacts_without_phone = [Contact(first_name=f'WithoutPhone{i}', last_name='Test', phone=None) for i in range(3)]
        clean_db.add_all(contacts_with_phone + contacts_without_phone)
        clean_db.commit()
        
        # Act - Apply filter
        response = authenticated_client_with_clean_db.get('/contacts/?filter=has_phone')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should show count reflects current filter
        assert response.status_code == 200
        
        # Extract count and verify it's the filtered count (10), not total (13)
        import re
        count_match = re.search(r'(\d+) total contacts', response_text)
        assert count_match
        filtered_count = int(count_match.group(1))
        
        # Should show around 10 (contacts with phone) not 13 (all contacts)
        assert 8 <= filtered_count <= 12, f"Expected filtered count ~10, got {filtered_count}"
