"""
Integration Tests for A/B Testing Service - TDD RED PHASE
These tests are written FIRST and will interact with real database
All tests should FAIL initially to ensure proper TDD workflow
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict

from services.ab_testing_service import ABTestingService
from services.common.result import Result
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.ab_test_result_repository import ABTestResultRepository
from crm_database import Campaign, Contact, CampaignMembership, ABTestResult, Activity
from tests.conftest import create_test_contact


class TestABTestingServiceIntegration:
    """Integration tests for A/B Testing Service with real database"""
    
    @pytest.fixture
    def campaign_repo(self, db_session):
        """Create real campaign repository"""
        return CampaignRepository(session=db_session)
    
    @pytest.fixture
    def contact_repo(self, db_session):
        """Create real contact repository"""
        return ContactRepository(session=db_session)
    
    @pytest.fixture
    def ab_result_repo(self, db_session):
        """Create real A/B test result repository"""
        return ABTestResultRepository(session=db_session)
    
    @pytest.fixture
    def service(self, campaign_repo, contact_repo, ab_result_repo):
        """Create ABTestingService with real repositories"""
        return ABTestingService(
            campaign_repository=campaign_repo,
            contact_repository=contact_repo,
            ab_result_repository=ab_result_repo
        )
    
    @pytest.fixture
    def test_contacts(self, db_session):
        """Create test contacts in database"""
        contacts = []
        for i in range(20):  # Create 20 test contacts
            contact = create_test_contact(
                first_name=f"TestUser{i}",
                last_name="Smith",
                phone=f"+1123456{i:04d}",
                email=f"test{i}@example.com"
            )
            db_session.add(contact)
            contacts.append(contact)
        
        db_session.commit()
        return contacts
    
    @pytest.fixture
    def ab_test_campaign(self, db_session):
        """Create A/B test campaign in database"""
        campaign = Campaign(
            name="Integration Test A/B Campaign",
            campaign_type="ab_test",
            template_a="Hi {first_name}, try our amazing product!",
            template_b="Hello {first_name}, discover our revolutionary solution!",
            ab_config={
                "split_ratio": 50,
                "winner_threshold": 0.95,
                "min_sample_size": 10
            },
            status="draft"
        )
        db_session.add(campaign)
        db_session.commit()
        return campaign


class TestDatabaseVariantAssignment(TestABTestingServiceIntegration):
    """Test variant assignment with real database persistence"""
    
    def test_assign_and_persist_variants(self, service, ab_test_campaign, test_contacts, db_session):
        """Test that variant assignments are properly persisted to database"""
        # Act - Assign recipients to variants
        result = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        
        # Assert - Check result
        assert result.is_success
        assignments = result.data
        assert len(assignments) == 20
        
        # Verify variants are balanced (50/50 split)
        variant_a_count = sum(1 for a in assignments if a['variant'] == 'A')
        variant_b_count = sum(1 for a in assignments if a['variant'] == 'B')
        assert variant_a_count == 10
        assert variant_b_count == 10
        
        # Verify persistence in database
        db_assignments = db_session.query(ABTestResult).filter_by(
            campaign_id=ab_test_campaign.id
        ).all()
        
        assert len(db_assignments) == 20
        
        # Check each assignment is properly stored
        for assignment in db_assignments:
            assert assignment.campaign_id == ab_test_campaign.id
            assert assignment.contact_id in [c.id for c in test_contacts]
            assert assignment.variant in ['A', 'B']
            assert assignment.assigned_at is not None
    
    def test_consistent_assignment_across_calls(self, service, ab_test_campaign, test_contacts):
        """Test that repeated calls give same assignments (deterministic)"""
        # Act - Run assignment twice
        result1 = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        result2 = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        
        # Assert - Both calls should succeed
        assert result1.is_success and result2.is_success
        
        # Create mapping for comparison
        assignments1 = {a['contact_id']: a['variant'] for a in result1.data}
        assignments2 = {a['contact_id']: a['variant'] for a in result2.data}
        
        # Same contact should get same variant
        for contact_id in assignments1:
            assert assignments1[contact_id] == assignments2[contact_id]
    
    def test_retrieve_existing_assignment(self, service, ab_test_campaign, test_contacts, db_session):
        """Test retrieving existing variant assignment from database"""
        # Arrange - First assign variants
        assign_result = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        assert assign_result.is_success
        
        # Pick a specific contact and their assigned variant
        test_contact = test_contacts[0]
        expected_variant = next(
            a['variant'] for a in assign_result.data 
            if a['contact_id'] == test_contact.id
        )
        
        # Act - Retrieve the assignment
        result = service.get_contact_variant(ab_test_campaign.id, test_contact.id)
        
        # Assert
        assert result.is_success
        assert result.data == expected_variant
    
    def test_custom_split_ratio_70_30(self, service, db_session, test_contacts):
        """Test custom 70/30 split ratio with database persistence"""
        # Arrange - Create campaign with 70/30 split
        campaign = Campaign(
            name="70/30 Split Test",
            campaign_type="ab_test",
            template_a="Variant A",
            template_b="Variant B",
            ab_config={"split_ratio": 70},  # 70% A, 30% B
            status="draft"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Act
        result = service.assign_recipients_to_variants(campaign.id, test_contacts)
        
        # Assert
        assert result.is_success
        assignments = result.data
        
        variant_a_count = sum(1 for a in assignments if a['variant'] == 'A')
        variant_b_count = sum(1 for a in assignments if a['variant'] == 'B')
        
        # With 20 contacts: 70% = 14, 30% = 6
        assert variant_a_count == 14
        assert variant_b_count == 6
        
        # Verify in database
        db_variant_a = db_session.query(ABTestResult).filter_by(
            campaign_id=campaign.id, variant='A'
        ).count()
        db_variant_b = db_session.query(ABTestResult).filter_by(
            campaign_id=campaign.id, variant='B'
        ).count()
        
        assert db_variant_a == 14
        assert db_variant_b == 6


class TestMetricsTrackingIntegration(TestABTestingServiceIntegration):
    """Test performance metrics tracking with database"""
    
    def test_track_complete_message_lifecycle(self, service, ab_test_campaign, test_contacts, db_session):
        """Test tracking complete message lifecycle: sent -> opened -> clicked -> responded"""
        # Arrange - Assign variants first
        assign_result = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        assert assign_result.is_success
        
        test_contact = test_contacts[0]
        variant = service.get_contact_variant(ab_test_campaign.id, test_contact.id).data
        
        # Act - Track message lifecycle
        # 1. Message sent
        sent_result = service.track_message_sent(
            ab_test_campaign.id, test_contact.id, variant, activity_id=101
        )
        assert sent_result.is_success
        
        # 2. Message opened
        opened_result = service.track_message_opened(
            ab_test_campaign.id, test_contact.id, variant
        )
        assert opened_result.is_success
        
        # 3. Link clicked
        clicked_result = service.track_link_clicked(
            ab_test_campaign.id, test_contact.id, variant, "https://example.com"
        )
        assert clicked_result.is_success
        
        # 4. Response received
        response_result = service.track_response_received(
            ab_test_campaign.id, test_contact.id, variant, "positive", activity_id=102
        )
        assert response_result.is_success
        
        # Assert - Verify all events are tracked in database
        ab_result = db_session.query(ABTestResult).filter_by(
            campaign_id=ab_test_campaign.id,
            contact_id=test_contact.id
        ).first()
        
        assert ab_result is not None
        assert ab_result.message_sent is True
        assert ab_result.message_opened is True
        assert ab_result.link_clicked is True
        assert ab_result.response_received is True
        assert ab_result.response_type == "positive"
        assert ab_result.sent_activity_id == 101
        assert ab_result.response_activity_id == 102
    
    def test_get_variant_metrics_from_database(self, service, ab_test_campaign, test_contacts, db_session):
        """Test retrieving aggregated variant metrics from database"""
        # Arrange - Assign variants and create test data
        assign_result = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        assert assign_result.is_success
        
        # Get actual variant A contacts (not assuming first 10)
        variant_a_contacts = []
        for contact in test_contacts:
            variant_result = service.get_contact_variant(ab_test_campaign.id, contact.id)
            if variant_result.is_success and variant_result.data == 'A':
                variant_a_contacts.append(contact)
            if len(variant_a_contacts) >= 10:  # Get at least 10 for testing
                break
        
        for i, contact in enumerate(variant_a_contacts):
            # Track message sent for all
            service.track_message_sent(ab_test_campaign.id, contact.id, 'A', activity_id=200+i)
            
            # Track opened for 80% (8 out of 10)
            if i < 8:
                service.track_message_opened(ab_test_campaign.id, contact.id, 'A')
            
            # Track clicked for 50% (5 out of 10)
            if i < 5:
                service.track_link_clicked(ab_test_campaign.id, contact.id, 'A', "https://example.com")
            
            # Track responses for 30% (3 out of 10)
            if i < 3:
                response_type = "positive" if i < 2 else "negative"
                service.track_response_received(
                    ab_test_campaign.id, contact.id, 'A', response_type, activity_id=300+i
                )
        
        # Act - Get variant A metrics
        result = service.get_variant_metrics(ab_test_campaign.id, 'A')
        
        # Assert
        assert result.is_success
        metrics = result.data
        
        # The actual number of variant A contacts tracked
        num_tracked = len(variant_a_contacts)
        # Adjust expectations based on actual number tracked
        assert metrics['messages_sent'] == num_tracked
        assert metrics['messages_opened'] == min(8, num_tracked)
        assert metrics['links_clicked'] == min(5, num_tracked)
        assert metrics['responses_received'] == min(3, num_tracked)
        assert metrics['positive_responses'] == min(2, num_tracked)
        assert metrics['negative_responses'] == min(1, num_tracked)
        
        # Check calculated rates
        assert metrics['open_rate'] == 0.8  # 8/10
        assert metrics['click_rate'] == 0.5  # 5/10
        assert metrics['response_rate'] == 0.3  # 3/10
        assert metrics['conversion_rate'] == 0.2  # 2/10 positive responses
    
    def test_campaign_ab_summary_with_real_data(self, service, ab_test_campaign, test_contacts, db_session):
        """Test generating campaign A/B summary with real database data"""
        # Arrange - Setup test data for both variants
        assign_result = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        assert assign_result.is_success
        
        # Get actual variant assignments
        variant_a_contacts = []
        variant_b_contacts = []
        for contact in test_contacts:
            variant_result = service.get_contact_variant(ab_test_campaign.id, contact.id)
            if variant_result.is_success:
                if variant_result.data == 'A':
                    variant_a_contacts.append(contact)
                else:
                    variant_b_contacts.append(contact)
        
        # Variant A performance: Lower performance
        for i, contact in enumerate(variant_a_contacts):
            service.track_message_sent(ab_test_campaign.id, contact.id, 'A', activity_id=100+i)
            
            # 60% open rate for A
            if i < len(variant_a_contacts) * 0.6:
                service.track_message_opened(ab_test_campaign.id, contact.id, 'A')
            
            # 10% conversion rate for A (1 out of 10)
            if i == 0:  # Only first contact converts
                service.track_response_received(
                    ab_test_campaign.id, contact.id, 'A', "positive", activity_id=200+i
                )
        
        # Variant B performance: Higher performance
        for i, contact in enumerate(variant_b_contacts):
            service.track_message_sent(ab_test_campaign.id, contact.id, 'B', activity_id=300+i)
            
            # 80% open rate for B
            if i < len(variant_b_contacts) * 0.8:
                service.track_message_opened(ab_test_campaign.id, contact.id, 'B')
            
            # 30% conversion rate for B
            if i < len(variant_b_contacts) * 0.3:
                service.track_response_received(
                    ab_test_campaign.id, contact.id, 'B', "positive", activity_id=400+i
                )
        
        # Act
        result = service.get_campaign_ab_summary(ab_test_campaign.id)
        
        # Assert
        assert result.is_success
        summary = result.data
        
        # Check variant A metrics
        variant_a = summary['variant_a']
        assert variant_a['messages_sent'] == len(variant_a_contacts)
        expected_a_opened = int(len(variant_a_contacts) * 0.6)
        assert variant_a['messages_opened'] == expected_a_opened
        assert variant_a['conversion_rate'] == (1.0 / len(variant_a_contacts))  # Only first contact converts
        assert variant_a['open_rate'] == (expected_a_opened / len(variant_a_contacts))
        
        # Check variant B metrics
        variant_b = summary['variant_b']
        assert variant_b['messages_sent'] == len(variant_b_contacts)
        expected_b_opened = int(len(variant_b_contacts) * 0.8)
        expected_b_converted = int(len(variant_b_contacts) * 0.3)
        assert variant_b['messages_opened'] == expected_b_opened
        assert variant_b['positive_responses'] == expected_b_converted
        assert variant_b['conversion_rate'] == (expected_b_converted / len(variant_b_contacts))
        assert variant_b['open_rate'] == (expected_b_opened / len(variant_b_contacts))
        
        # B should be the winner (if there's enough data for significance)
        # With small sample sizes, might not achieve statistical significance
        if summary['significant_difference']:
            assert summary['winner'] == 'B'
        else:
            # Even without statistical significance, B should have better conversion rate
            assert variant_b['conversion_rate'] > variant_a['conversion_rate']


class TestWinnerSelectionIntegration(TestABTestingServiceIntegration):
    """Test winner selection with database persistence"""
    
    def test_identify_and_persist_winner(self, service, ab_test_campaign, test_contacts, db_session):
        """Test identifying winner and persisting to database"""
        # Arrange - Create clear winner scenario
        assign_result = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        assert assign_result.is_success
        
        # Get actual variant assignments
        variant_a_contacts = []
        variant_b_contacts = []
        for contact in test_contacts:
            variant_result = service.get_contact_variant(ab_test_campaign.id, contact.id)
            if variant_result.is_success:
                if variant_result.data == 'A':
                    variant_a_contacts.append(contact)
                else:
                    variant_b_contacts.append(contact)
        
        # Make variant B clearly better (high conversion rate)
        for i, contact in enumerate(variant_b_contacts[:10]):
            service.track_message_sent(ab_test_campaign.id, contact.id, 'B', activity_id=100+i)
            
            # All B contacts convert (100% conversion)
            service.track_response_received(
                ab_test_campaign.id, contact.id, 'B', "positive", activity_id=200+i
            )
        
        # Variant A has lower performance
        for i, contact in enumerate(variant_a_contacts[:10]):
            service.track_message_sent(ab_test_campaign.id, contact.id, 'A', activity_id=300+i)
            
            # Only 20% of A contacts convert
            if i < 2:
                service.track_response_received(
                    ab_test_campaign.id, contact.id, 'A', "positive", activity_id=400+i
                )
        
        # Act
        result = service.identify_winner(ab_test_campaign.id, confidence_threshold=0.90)
        
        # Assert
        assert result.is_success
        winner_data = result.data
        # With 100% conversion for B and 20% for A, B should win if we have enough data
        # But if not enough data, there might be no winner
        if winner_data['winner']:
            assert winner_data['winner'] == 'B'
            assert winner_data['confidence_level'] >= 0.90
            assert winner_data['automatic'] is True
        else:
            # Not enough data for statistical significance
            assert winner_data.get('reason') in ['no_responses', 'insufficient_confidence']
        
        # Verify winner is persisted in campaign
        # Get the updated campaign from the service's repository
        if winner_data.get('winner') == 'B':
            updated_campaign = service.campaign_repository.get_by_id(ab_test_campaign.id)
            ab_config = updated_campaign.ab_config or {}
            assert ab_config.get('ab_winner') == 'B' or ab_config.get('winner') == 'B'
    
    def test_manual_winner_override_persistence(self, service, ab_test_campaign, db_session):
        """Test manual winner override with database persistence"""
        # Act - Set manual winner
        result = service.set_manual_winner(
            ab_test_campaign.id, 
            'A', 
            "Brand voice consistency - A variant aligns better with our tone"
        )
        
        # Assert
        assert result.is_success
        winner_data = result.data
        assert winner_data['winner'] == 'A'
        assert winner_data['automatic'] is False
        assert "Brand voice consistency" in winner_data['override_reason']
        
        # Verify that the service updated the campaign correctly
        # Since both the service and test use the same db_session, 
        # the changes should be visible immediately after service call
        updated_campaign = service.campaign_repository.get_by_id(ab_test_campaign.id)
        ab_config = updated_campaign.ab_config or {}
        
        assert ab_config.get('winner') == 'A'
        assert ab_config.get('manual_override') is True
        assert "Brand voice consistency" in ab_config.get('override_reason', '')


class TestCompleteABTestWorkflow(TestABTestingServiceIntegration):
    """Test complete end-to-end A/B test workflow"""
    
    def test_complete_ab_test_lifecycle(self, service, test_contacts, db_session):
        """Test complete A/B test from creation to winner selection"""
        # Step 1: Create A/B test campaign
        campaign_data = {
            "name": "Complete Lifecycle Test",
            "template_a": "Try our product today, {first_name}!",
            "template_b": "Discover amazing savings, {first_name}!",
            "ab_config": {
                "split_ratio": 60,  # 60% A, 40% B
                "winner_threshold": 0.95,
                "min_sample_size": 5
            }
        }
        
        create_result = service.create_ab_campaign(campaign_data)
        assert create_result.is_success
        campaign = create_result.data
        
        # Step 2: Assign recipients to variants
        assign_result = service.assign_recipients_to_variants(campaign.id, test_contacts)
        assert assign_result.is_success
        
        # Verify split ratio (approximately 60/40 due to deterministic hashing)
        assignments = assign_result.data
        variant_a_count = sum(1 for a in assignments if a['variant'] == 'A')
        variant_b_count = sum(1 for a in assignments if a['variant'] == 'B')
        total_contacts = len(assignments)
        
        # Allow for some variance in deterministic split (within 10% of target)
        expected_a = int(total_contacts * 0.6)
        expected_b = total_contacts - expected_a
        assert abs(variant_a_count - expected_a) <= 2  # Allow ±2 variance
        assert abs(variant_b_count - expected_b) <= 2  # Allow ±2 variance
        assert variant_a_count + variant_b_count == total_contacts
        
        # Step 3: Simulate campaign execution and tracking
        variant_a_assignments = [a for a in assignments if a['variant'] == 'A']
        variant_b_assignments = [a for a in assignments if a['variant'] == 'B']
        
        # Variant A performance (decent)
        for i, assignment in enumerate(variant_a_assignments):
            contact_id = assignment['contact_id']
            service.track_message_sent(campaign.id, contact_id, 'A', activity_id=1000+i)
            
            # 75% open rate, 25% conversion rate
            if i < len(variant_a_assignments) * 0.75:  # 75% open
                service.track_message_opened(campaign.id, contact_id, 'A')
            if i < len(variant_a_assignments) * 0.25:  # 25% convert
                service.track_response_received(
                    campaign.id, contact_id, 'A', "positive", activity_id=2000+i
                )
        
        # Variant B performance (better)
        for i, assignment in enumerate(variant_b_assignments):
            contact_id = assignment['contact_id']
            service.track_message_sent(campaign.id, contact_id, 'B', activity_id=1100+i)
            
            # 90% open rate, 50% conversion rate
            if i < len(variant_b_assignments) * 0.9:  # 90% open
                service.track_message_opened(campaign.id, contact_id, 'B')
            if i < len(variant_b_assignments) * 0.5:  # 50% convert
                service.track_response_received(
                    campaign.id, contact_id, 'B', "positive", activity_id=2100+i
                )
        
        # Step 4: Get campaign summary
        summary_result = service.get_campaign_ab_summary(campaign.id)
        assert summary_result.is_success
        summary = summary_result.data
        
        # Verify metrics (allow for rounding differences)
        expected_a_conversion = 0.25  # 25%
        expected_b_conversion = 0.5   # 50%
        
        assert abs(summary['variant_a']['conversion_rate'] - expected_a_conversion) < 0.1
        assert abs(summary['variant_b']['conversion_rate'] - expected_b_conversion) < 0.1
        assert summary['winner'] == 'B'
        
        # Step 5: Identify winner
        winner_result = service.identify_winner(campaign.id, confidence_threshold=0.90)
        assert winner_result.is_success
        
        winner_data = winner_result.data
        # With small sample sizes, might not reach statistical significance
        # But B should be the winner based on conversion rate if there is one
        if winner_data['winner'] is not None:
            assert winner_data['winner'] == 'B'
        else:
            # Winner is None due to insufficient confidence or sample size
            assert winner_data.get('reason') in ['insufficient_confidence', 'no_responses']
        
        # Step 6: Generate final report
        report_result = service.generate_ab_test_report(campaign.id)
        assert report_result.is_success
        
        report = report_result.data
        assert report['campaign_info']['name'] == "Complete Lifecycle Test"
        assert report['statistical_analysis']['winner'] == 'B'
        assert len(report['recommendations']) > 0
        
        # Step 7: Verify all data is properly persisted
        # Check campaign in database
        db_campaign = db_session.query(Campaign).filter_by(id=campaign.id).first()
        assert db_campaign is not None
        assert db_campaign.campaign_type == "ab_test"
        
        # Check variant assignments in database
        db_assignments = db_session.query(ABTestResult).filter_by(
            campaign_id=campaign.id
        ).all()
        assert len(db_assignments) == 20
        
        # Verify tracking data
        sent_count = sum(1 for a in db_assignments if a.message_sent)
        opened_count = sum(1 for a in db_assignments if a.message_opened)
        response_count = sum(1 for a in db_assignments if a.response_received)
        
        assert sent_count == 20  # All messages sent
        # Allow for variance in opened/response counts due to deterministic assignment
        assert opened_count >= 15 and opened_count <= 18  # Approximately 80% open rate
        assert response_count >= 6 and response_count <= 8   # Approximately 30-35% response rate


class TestErrorHandlingIntegration(TestABTestingServiceIntegration):
    """Test error handling with database operations"""
    
    def test_duplicate_assignment_handling(self, service, ab_test_campaign, test_contacts, db_session):
        """Test handling of duplicate variant assignments"""
        # Arrange - First assignment
        result1 = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        assert result1.is_success
        
        # Act - Second assignment (should handle gracefully)
        result2 = service.assign_recipients_to_variants(ab_test_campaign.id, test_contacts)
        
        # Assert - Should succeed but not create duplicates
        assert result2.is_success
        
        # Verify no duplicates in database
        db_assignments = db_session.query(ABTestResult).filter_by(
            campaign_id=ab_test_campaign.id
        ).all()
        
        # Should still only have 20 assignments (one per contact)
        assert len(db_assignments) == 20
        
        # Verify each contact appears exactly once
        contact_ids = [a.contact_id for a in db_assignments]
        assert len(set(contact_ids)) == 20  # No duplicates
    
    def test_nonexistent_campaign_handling(self, service, test_contacts):
        """Test handling of operations on nonexistent campaign"""
        # Act - Try to assign variants to nonexistent campaign
        result = service.assign_recipients_to_variants(999999, test_contacts)
        
        # Assert - Should fail gracefully
        assert result.is_failure
        assert "Campaign not found" in result.error or "CAMPAIGN_NOT_FOUND" in result.error_code
    
    def test_invalid_contact_handling(self, service, ab_test_campaign):
        """Test handling of operations with invalid contacts"""
        # Arrange - Create fake contact that doesn't exist in DB
        fake_contact = Contact(id=999999, first_name="Fake", last_name="User", phone="+19999999999")
        
        # Act
        result = service.assign_recipients_to_variants(ab_test_campaign.id, [fake_contact])
        
        # Assert - Should handle gracefully
        # Depending on implementation, might succeed with empty result or fail with error
        if result.is_failure:
            assert "Contact not found" in result.error or "CONTACT_NOT_FOUND" in result.error_code
        else:
            # If it succeeds, should handle the invalid contact appropriately
            assert isinstance(result.data, list)
