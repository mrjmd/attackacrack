# tests/integration/routes/test_contact_list_filter_by_list.py
"""
TEST-DRIVEN DEVELOPMENT - RED PHASE
Tests for filtering contacts by their associated campaign lists.
These tests MUST FAIL initially before implementation.
"""

import pytest
from crm_database import Contact, CampaignList, CampaignListMember
from datetime import datetime


class TestContactListFilterByList:
    """Test filtering contacts by their associated campaign lists"""
    
    def test_displays_list_filter_dropdown(self, authenticated_client, db_session):
        """Test that list filter dropdown is present on contact list page"""
        # Arrange - Create some campaign lists
        list1 = CampaignList(
            name='VIP Customers',
            description='High value customers',
            created_at=datetime.utcnow()
        )
        list2 = CampaignList(
            name='New Leads',
            description='Recently acquired leads',
            created_at=datetime.utcnow()
        )
        db_session.add_all([list1, list2])
        db_session.commit()
        
        # Act - Visit contacts page
        response = authenticated_client.get('/contacts/')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should have list filter dropdown
        assert response.status_code == 200
        
        # Should have a select element for list filtering
        assert '<select name="list_filter"' in response_text
        
        # Should have options for each list
        assert 'VIP Customers' in response_text
        assert 'New Leads' in response_text
        
        # Should have "All Lists" default option
        assert 'All Lists' in response_text
    
    def test_filters_contacts_by_selected_list(self, authenticated_client_with_clean_db, clean_db):
        """Test filtering contacts by a specific list"""
        # Arrange - Create lists and contacts
        vip_list = CampaignList(
            name='VIP Customers',
            description='High value customers',
            created_at=datetime.utcnow()
        )
        leads_list = CampaignList(
            name='New Leads', 
            description='Recently acquired leads',
            created_at=datetime.utcnow()
        )
        clean_db.add_all([vip_list, leads_list])
        clean_db.flush()  # Get IDs
        
        # Create contacts
        vip_contact = Contact(
            first_name='VIP',
            last_name='Customer',
            phone='+15551111111'
        )
        lead_contact = Contact(
            first_name='New',
            last_name='Lead', 
            phone='+15552222222'
        )
        no_list_contact = Contact(
            first_name='No',
            last_name='List',
            phone='+15553333333'
        )
        clean_db.add_all([vip_contact, lead_contact, no_list_contact])
        clean_db.flush()  # Get IDs
        
        # Add contacts to lists
        vip_member = CampaignListMember(
            list_id=vip_list.id,
            contact_id=vip_contact.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        lead_member = CampaignListMember(
            list_id=leads_list.id,
            contact_id=lead_contact.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        clean_db.add_all([vip_member, lead_member])
        clean_db.commit()
        
        # Act - Filter by VIP list
        response = authenticated_client_with_clean_db.get(f'/contacts/?list_filter={vip_list.id}')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should only show VIP contact
        assert response.status_code == 200
        
        # Extract the contact list section from HTML to avoid dropdown text
        import re
        # Find the contacts list div
        contacts_section_match = re.search(r'<!-- Contact Items -->(.*?)<!-- Pagination -->', response_text, re.DOTALL)
        if contacts_section_match:
            contacts_html = contacts_section_match.group(1)
        else:
            # Fallback - look for the contacts section
            contacts_section_match = re.search(r'<div class="divide-y divide-gray-600">(.*?)</div>', response_text, re.DOTALL)
            contacts_html = contacts_section_match.group(1) if contacts_section_match else response_text
        
        # Should show VIP contact name in contact results
        assert 'VIP Customer' in contacts_html
        # Should NOT show other contact names in contact results
        assert 'New Lead' not in contacts_html
        assert 'No List' not in contacts_html
        
        # Should show filtered count (1 contact)
        assert '1 total contacts' in response_text
    
    def test_filters_contacts_by_different_list(self, authenticated_client_with_clean_db, clean_db):
        """Test filtering by a different list shows different results"""
        # Arrange - Same setup as previous test
        vip_list = CampaignList(
            name='VIP Customers',
            description='High value customers', 
            created_at=datetime.utcnow()
        )
        leads_list = CampaignList(
            name='New Leads',
            description='Recently acquired leads',
            created_at=datetime.utcnow()
        )
        clean_db.add_all([vip_list, leads_list])
        clean_db.flush()
        
        vip_contact = Contact(
            first_name='VIP',
            last_name='Customer',
            phone='+15551111111'
        )
        lead_contact1 = Contact(
            first_name='Lead',
            last_name='One',
            phone='+15552222222'
        )
        lead_contact2 = Contact(
            first_name='Lead', 
            last_name='Two',
            phone='+15553333333'
        )
        clean_db.add_all([vip_contact, lead_contact1, lead_contact2])
        clean_db.flush()
        
        # Add to lists
        vip_member = CampaignListMember(
            list_id=vip_list.id,
            contact_id=vip_contact.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        lead_member1 = CampaignListMember(
            list_id=leads_list.id,
            contact_id=lead_contact1.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        lead_member2 = CampaignListMember(
            list_id=leads_list.id,
            contact_id=lead_contact2.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        clean_db.add_all([vip_member, lead_member1, lead_member2])
        clean_db.commit()
        
        # Act - Filter by New Leads list 
        response = authenticated_client_with_clean_db.get(f'/contacts/?list_filter={leads_list.id}')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should show both lead contacts
        assert response.status_code == 200
        
        # Extract contact list section from HTML 
        import re
        contacts_section_match = re.search(r'<div class="divide-y divide-gray-600">(.*?)</div>', response_text, re.DOTALL)
        contacts_html = contacts_section_match.group(1) if contacts_section_match else response_text
        
        
        # Check that both lead contacts are shown but VIP contact is not in the actual contact list
        assert 'Lead One' in response_text
        assert 'Lead Two' in response_text
        
        # Extract contact list section to verify VIP Customer is not in the actual results
        import re
        contacts_section_match = re.search(r'<div class="divide-y divide-gray-600">(.*?)</div>', response_text, re.DOTALL)
        if contacts_section_match:
            contacts_html = contacts_section_match.group(1)
            assert 'VIP Customer' not in contacts_html  # Should not be in the filtered results
        
        # Should show filtered count (2 contacts)
        assert '2 total contacts' in response_text
    
    def test_shows_all_contacts_when_no_list_filter(self, authenticated_client, db_session):
        """Test that all contacts are shown when no list filter is applied"""
        # Arrange - Create contacts with and without list memberships
        list_contact = Contact(
            first_name='In',
            last_name='List',
            phone='+15551111111'
        )
        no_list_contact = Contact(
            first_name='No',
            last_name='List',
            phone='+15552222222'
        )
        
        campaign_list = CampaignList(
            name='Test List',
            description='Test',
            created_at=datetime.utcnow()
        )
        db_session.add_all([list_contact, no_list_contact, campaign_list])
        db_session.flush()
        
        member = CampaignListMember(
            list_id=campaign_list.id,
            contact_id=list_contact.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        db_session.add(member)
        db_session.commit()
        
        # Act - Visit contacts page with no list filter
        response = authenticated_client.get('/contacts/')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should show both contacts
        assert response.status_code == 200
        assert 'In List' in response_text
        assert 'No List' in response_text
    
    def test_list_filter_combines_with_search(self, authenticated_client, db_session):
        """Test that list filter works in combination with search"""
        # Arrange - Create list and contacts
        campaign_list = CampaignList(
            name='Test List',
            description='Test',
            created_at=datetime.utcnow()
        )
        db_session.add(campaign_list)
        db_session.flush()
        
        # Create contacts in the list
        john_contact = Contact(
            first_name='John',
            last_name='Smith',
            phone='+15551111111'
        )
        jane_contact = Contact(
            first_name='Jane',
            last_name='Doe',
            phone='+15552222222'
        )
        # Contact not in list
        john_outside = Contact(
            first_name='John',
            last_name='Outside',
            phone='+15553333333'
        )
        db_session.add_all([john_contact, jane_contact, john_outside])
        db_session.flush()
        
        # Add to list
        member1 = CampaignListMember(
            list_id=campaign_list.id,
            contact_id=john_contact.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        member2 = CampaignListMember(
            list_id=campaign_list.id,
            contact_id=jane_contact.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        db_session.add_all([member1, member2])
        db_session.commit()
        
        # Act - Search for 'John' within the list
        response = authenticated_client.get(f'/contacts/?search=john&list_filter={campaign_list.id}')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should only show John Smith (in list), not John Outside
        assert response.status_code == 200
        
        # Extract contact list section from HTML 
        import re
        contacts_section_match = re.search(r'<div class="divide-y divide-gray-600">(.*?)</div>', response_text, re.DOTALL)
        contacts_html = contacts_section_match.group(1) if contacts_section_match else response_text
        
        assert 'John Smith' in contacts_html
        assert 'John Outside' not in contacts_html  
        assert 'Jane Doe' not in contacts_html
        
        # Should show filtered count (1 contact)
        assert '1 total contacts' in response_text
    
    def test_list_filter_combines_with_other_filters(self, authenticated_client, db_session):
        """Test that list filter works with other filter types"""
        # Arrange - Create list and contacts
        campaign_list = CampaignList(
            name='Test List',
            description='Test',
            created_at=datetime.utcnow()
        )
        db_session.add(campaign_list)
        db_session.flush()
        
        # Contact in list with phone
        with_phone = Contact(
            first_name='HasPhone',
            last_name='InList',
            phone='+15551111111'
        )
        # Contact in list without phone
        without_phone = Contact(
            first_name='NoPhone',
            last_name='InList',
            phone=None
        )
        db_session.add_all([with_phone, without_phone])
        db_session.flush()
        
        # Add both to list
        member1 = CampaignListMember(
            list_id=campaign_list.id,
            contact_id=with_phone.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        member2 = CampaignListMember(
            list_id=campaign_list.id,
            contact_id=without_phone.id,
            added_at=datetime.utcnow(),
            status='active'
        )
        db_session.add_all([member1, member2])
        db_session.commit()
        
        # Act - Filter by list AND has_phone
        response = authenticated_client.get(f'/contacts/?list_filter={campaign_list.id}&filter=has_phone')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should only show contact with phone in the list
        assert response.status_code == 200
        
        # Extract contact list section from HTML 
        import re
        contacts_section_match = re.search(r'<div class="divide-y divide-gray-600">(.*?)</div>', response_text, re.DOTALL)
        contacts_html = contacts_section_match.group(1) if contacts_section_match else response_text
        
        assert 'HasPhone InList' in contacts_html
        assert 'NoPhone InList' not in contacts_html
        
        # Should show filtered count (1 contact)
        assert '1 total contacts' in response_text
    
    def test_invalid_list_filter_shows_all_contacts(self, authenticated_client_with_clean_db, clean_db):
        """Test that invalid list filter ID defaults to showing all contacts"""
        # Arrange - Create some contacts
        contact1 = Contact(
            first_name='Contact',
            last_name='One',
            phone='+15551111111'
        )
        contact2 = Contact(
            first_name='Contact', 
            last_name='Two',
            phone='+15552222222'
        )
        clean_db.add_all([contact1, contact2])
        clean_db.commit()
        
        # Act - Use invalid list filter ID
        response = authenticated_client_with_clean_db.get('/contacts/?list_filter=99999')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should show all contacts (graceful degradation)
        assert response.status_code == 200
        assert 'Contact One' in response_text
        assert 'Contact Two' in response_text
    
    def test_empty_list_shows_no_contacts(self, authenticated_client, db_session):
        """Test that filtering by an empty list shows no contacts"""
        # Arrange - Create empty list and contacts not in any list
        empty_list = CampaignList(
            name='Empty List',
            description='No members',
            created_at=datetime.utcnow()
        )
        
        contact = Contact(
            first_name='Not',
            last_name='InList', 
            phone='+15551111111'
        )
        db_session.add_all([empty_list, contact])
        db_session.commit()
        
        # Act - Filter by empty list
        response = authenticated_client.get(f'/contacts/?list_filter={empty_list.id}')
        response_text = response.data.decode('utf-8')
        
        # Assert - Should show no contacts
        assert response.status_code == 200
        assert 'Not InList' not in response_text
        
        # Should show 0 count
        assert '0 total contacts' in response_text
        
        # Should show "no contacts found" message
        assert 'No contacts found' in response_text
