"""
TDD RED Phase: Tests for ContactRepository SMS Metrics Enhancement
These tests MUST FAIL initially - testing new methods needed for SMSMetricsService refactoring
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from repositories.contact_repository import ContactRepository
from crm_database import Contact


class TestContactRepositorySMSMetricsEnhancement:
    """Test SMS metrics-specific methods for ContactRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create ContactRepository instance"""
        return ContactRepository(session=db_session, model_class=Contact)
    
    @pytest.fixture
    def sample_contacts(self, db_session):
        """Create sample contacts with bounce metadata"""
        contacts = []
        
        # Contact with bounce info
        bounce_contact = Contact(
            phone='+11234567890',
            first_name='Bounced',
            last_name='User',
            contact_metadata={
                'bounce_info': {
                    'total_bounces': 3,
                    'last_bounce': '2025-01-15T10:00:00',
                    'last_bounce_type': 'hard',
                    'counts': {
                        'hard': 2,
                        'soft': 1
                    }
                },
                'sms_invalid': True,
                'sms_invalid_reason': 'Multiple hard bounces'
            }
        )
        contacts.append(bounce_contact)
        
        # Contact with some bounces but valid
        valid_contact = Contact(
            phone='+19876543210',
            first_name='Valid',
            last_name='User',
            contact_metadata={
                'bounce_info': {
                    'total_bounces': 1,
                    'last_bounce': '2025-01-10T10:00:00',
                    'last_bounce_type': 'soft',
                    'counts': {
                        'soft': 1
                    }
                }
            }
        )
        contacts.append(valid_contact)
        
        # Contact with no bounce info
        clean_contact = Contact(
            phone='+15555551234',
            first_name='Clean',
            last_name='User'
        )
        contacts.append(clean_contact)
        
        for contact in contacts:
            db_session.add(contact)
        
        db_session.flush()
        return contacts
    
    def test_update_contact_bounce_status(self, repository, sample_contacts):
        """Test updating contact bounce status - MUST FAIL initially"""
        contact = sample_contacts[2]  # Clean contact
        
        # This method should exist to update bounce information
        bounce_info = {
            'bounce_type': 'hard',
            'bounce_details': 'Invalid number',
            'bounced_at': datetime.utcnow().isoformat()
        }
        
        # This method doesn't exist yet - should fail
        result = repository.update_contact_bounce_status(
            contact_id=contact.id,
            bounce_info=bounce_info
        )
        
        # Verify bounce info was updated
        assert result is not None
        assert result.contact_metadata is not None
        assert 'bounce_info' in result.contact_metadata
        
        bounce_data = result.contact_metadata['bounce_info']
        assert bounce_data['last_bounce_type'] == 'hard'
        assert bounce_data['total_bounces'] >= 1
        assert 'counts' in bounce_data
        assert bounce_data['counts']['hard'] >= 1
    
    def test_find_contacts_with_bounce_metadata(self, repository, sample_contacts):
        """Test finding contacts with bounce metadata - MUST FAIL initially"""
        # This method should exist to find contacts with bounce information
        bounced_contacts = repository.find_contacts_with_bounce_metadata(
            bounce_threshold=2
        )
        
        # Should find contacts with >= 2 bounces
        assert len(bounced_contacts) == 1  # Only the first contact has 3 bounces
        
        bounced = bounced_contacts[0]
        assert bounced.contact_metadata is not None
        assert 'bounce_info' in bounced.contact_metadata
        assert bounced.contact_metadata['bounce_info']['total_bounces'] >= 2
    
    def test_find_contacts_by_sms_validity(self, repository, sample_contacts):
        """Test finding contacts by SMS validity status - MUST FAIL initially"""
        # This method should exist to find invalid SMS contacts
        invalid_contacts = repository.find_contacts_by_sms_validity(valid=False)
        
        # Should find contacts marked as SMS invalid
        assert len(invalid_contacts) == 1
        invalid = invalid_contacts[0]
        assert invalid.contact_metadata is not None
        assert invalid.contact_metadata.get('sms_invalid') is True
        
        # Test finding valid contacts
        valid_contacts = repository.find_contacts_by_sms_validity(valid=True)
        
        # Should find contacts not marked as SMS invalid (2 contacts)
        assert len(valid_contacts) == 2
        for contact in valid_contacts:
            sms_invalid = contact.contact_metadata.get('sms_invalid', False) if contact.contact_metadata else False
            assert sms_invalid is False
    
    def test_get_contacts_bounce_summary(self, repository, sample_contacts):
        """Test getting bounce summary for contacts - MUST FAIL initially"""
        # This method should exist to get comprehensive bounce statistics
        summary = repository.get_contacts_bounce_summary()
        
        # Should return summary with bounce statistics
        assert summary is not None
        assert 'total_contacts' in summary
        assert 'contacts_with_bounces' in summary
        assert 'sms_invalid_contacts' in summary
        assert 'bounce_rate_percentage' in summary
        assert 'bounce_type_breakdown' in summary
        
        # Verify counts
        assert summary['total_contacts'] == 3
        assert summary['contacts_with_bounces'] == 2  # 2 contacts have bounce info
        assert summary['sms_invalid_contacts'] == 1   # 1 contact is SMS invalid
        
        # Bounce type breakdown should exist
        breakdown = summary['bounce_type_breakdown']
        assert 'hard' in breakdown
        assert 'soft' in breakdown
        assert breakdown['hard'] >= 2  # Total hard bounces across all contacts
        assert breakdown['soft'] >= 1  # Total soft bounces across all contacts
    
    def test_bulk_update_contacts_metadata(self, repository, sample_contacts):
        """Test bulk updating contact metadata - MUST FAIL initially"""
        contact_ids = [c.id for c in sample_contacts[:2]]
        
        # This method should exist to bulk update metadata
        metadata_update = {
            'last_metrics_check': datetime.utcnow().isoformat(),
            'metrics_source': 'sms_service'
        }
        
        updated_count = repository.bulk_update_contacts_metadata(
            contact_ids=contact_ids,
            metadata_update=metadata_update,
            merge=True
        )
        
        # Should return count of updated contacts
        assert updated_count == 2
        
        # Verify contacts were updated
        for contact_id in contact_ids:
            contact = repository.get_by_id(contact_id)
            assert contact.contact_metadata is not None
            assert 'last_metrics_check' in contact.contact_metadata
            assert contact.contact_metadata['metrics_source'] == 'sms_service'
    
    def test_find_contacts_with_metadata_keys(self, repository, sample_contacts):
        """Test finding contacts with specific metadata keys - MUST FAIL initially"""
        # This method should exist to find contacts with specific metadata keys
        contacts_with_bounce_info = repository.find_contacts_with_metadata_keys([
            'bounce_info'
        ])
        
        # Should find contacts that have bounce_info in metadata
        assert len(contacts_with_bounce_info) == 2  # 2 contacts have bounce info
        
        for contact in contacts_with_bounce_info:
            assert contact.contact_metadata is not None
            assert 'bounce_info' in contact.contact_metadata
    
    def test_get_contact_reliability_score(self, repository, sample_contacts):
        """Test calculating contact reliability score - MUST FAIL initially"""
        # This method should exist to calculate reliability based on bounce history
        bounce_contact = sample_contacts[0]  # Contact with bounces
        
        score = repository.get_contact_reliability_score(contact_id=bounce_contact.id)
        
        # Should return a reliability score based on bounce history
        assert score is not None
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100  # Score should be percentage
        
        # Contact with hard bounces should have lower score
        assert score < 80  # Should be penalized for bounces
    
    def test_find_problematic_numbers(self, repository, sample_contacts):
        """Test finding problematic phone numbers - MUST FAIL initially"""
        # This method should exist to identify contacts with delivery issues
        problematic = repository.find_problematic_numbers(bounce_threshold=2)
        
        # Should return list of problematic contacts with details
        assert len(problematic) == 1  # Only one contact with >= 2 bounces
        
        problem_contact = problematic[0]
        assert 'contact_id' in problem_contact
        assert 'phone' in problem_contact
        assert 'total_bounces' in problem_contact
        assert 'bounce_types' in problem_contact
        assert 'sms_invalid' in problem_contact
        
        assert problem_contact['total_bounces'] >= 2
        assert problem_contact['sms_invalid'] is True
    
    def test_merge_bounce_metadata(self, repository, sample_contacts):
        """Test merging bounce metadata for a contact - MUST FAIL initially"""
        contact = sample_contacts[1]  # Contact with some bounce info
        
        # New bounce information to merge
        new_bounce_info = {
            'bounce_type': 'hard',
            'bounce_details': 'Number disconnected',
            'bounced_at': datetime.utcnow().isoformat()
        }
        
        # This method should exist to merge new bounce info with existing
        result = repository.merge_bounce_metadata(
            contact_id=contact.id,
            new_bounce_info=new_bounce_info
        )
        
        # Verify bounce info was properly merged
        assert result is not None
        assert result.contact_metadata is not None
        
        bounce_data = result.contact_metadata['bounce_info']
        assert bounce_data['total_bounces'] == 2  # Was 1, now 2
        assert bounce_data['last_bounce_type'] == 'hard'
        assert 'counts' in bounce_data
        assert bounce_data['counts']['hard'] == 1  # New hard bounce
        assert bounce_data['counts']['soft'] == 1  # Existing soft bounce
    
    def test_find_contacts_by_bounce_type(self, repository, sample_contacts):
        """Test finding contacts by bounce type - MUST FAIL initially"""
        # This method should exist to find contacts by specific bounce types
        hard_bounce_contacts = repository.find_contacts_by_bounce_type('hard')
        
        # Should find contacts with hard bounces
        assert len(hard_bounce_contacts) == 1  # Only first contact has hard bounces
        
        hard_contact = hard_bounce_contacts[0]
        assert hard_contact.contact_metadata is not None
        bounce_info = hard_contact.contact_metadata['bounce_info']
        assert 'hard' in bounce_info['counts']
        assert bounce_info['counts']['hard'] > 0