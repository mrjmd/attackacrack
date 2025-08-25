"""
Integration Tests for Response Rate Analytics - TDD RED PHASE
These tests are written FIRST before implementing the complete analytics system
All tests should FAIL initially to ensure proper TDD workflow

Tests cover:
1. End-to-end response tracking workflow
2. Real-time analytics updates
3. A/B test comparison integration
4. Performance with large campaign datasets
5. Database integration and transactions
6. Service registry integration
7. Webhook processing pipeline
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
import time
from decimal import Decimal

from app import create_app
from flask import current_app
from crm_database import (
    db, Campaign, Contact, Activity, CampaignMembership, CampaignResponse
)
from services.response_analytics_service import ResponseAnalyticsService
from services.webhook_service import WebhookService
from services.campaign_service import CampaignService
from repositories.campaign_response_repository import CampaignResponseRepository
from utils.datetime_utils import utc_now, ensure_utc
from tests.fixtures.factory import (
    CampaignFactory, ContactFactory, ActivityFactory, CampaignMembershipFactory
)


class TestResponseAnalyticsIntegration:
    """Integration tests for Response Analytics system"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application"""
        app = create_app(testing=True)
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def db_session(self, app):
        """Database session for testing"""
        with app.app_context():
            yield db.session
            db.session.rollback()
    
    @pytest.fixture
    def response_analytics_service(self, app):
        """Get response analytics service from service registry"""
        with app.app_context():
            service = current_app.services.get('response_analytics')
            assert service is not None
            assert isinstance(service, ResponseAnalyticsService)
            return service
    
    @pytest.fixture
    def webhook_service(self, app):
        """Get webhook service from service registry"""
        with app.app_context():
            service = current_app.services.get('webhook')
            assert service is not None
            return service
    
    @pytest.fixture
    def campaign_service(self, app):
        """Get campaign service from service registry"""
        with app.app_context():
            service = current_app.services.get('campaign')
            assert service is not None
            return service
    
    @pytest.fixture
    def sample_ab_campaign(self, db_session):
        """Create a sample A/B test campaign with members"""
        campaign = CampaignFactory.create(
            name="A/B Test Campaign",
            status="running",
            campaign_type="ab_test",
            template_a="Hi {name}, interested in our services?",
            template_b="Hello {name}, would you like to learn about our services?",
            ab_config={
                'split_percentage': 50,
                'test_metric': 'response_rate',
                'minimum_sample_size': 100
            }
        )
        
        # Create contacts and memberships
        contacts = ContactFactory.create_batch(
            200,
            phone_factory_kwargs={'start_with': '+1555'}
        )
        
        memberships = []
        for i, contact in enumerate(contacts):
            variant = 'A' if i % 2 == 0 else 'B'
            membership = CampaignMembershipFactory.create(
                campaign=campaign,
                contact=contact,
                variant_sent=variant,
                status='sent',
                sent_at=utc_now() - timedelta(hours=2)
            )
            memberships.append(membership)
        
        db_session.commit()
        return {
            'campaign': campaign,
            'contacts': contacts,
            'memberships': memberships
        }

    # ===== End-to-End Response Tracking =====
    
    def test_complete_response_tracking_workflow(self, app, db_session, 
                                                response_analytics_service, 
                                                webhook_service, sample_ab_campaign):
        """Test complete response tracking from webhook to analytics"""
        with app.app_context():
            # Arrange
            campaign = sample_ab_campaign['campaign']
            test_contact = sample_ab_campaign['contacts'][0]
            membership = sample_ab_campaign['memberships'][0]
            
            # Simulate webhook payload for incoming response
            webhook_payload = {
                'type': 'message.received',
                'data': {
                    'id': 'msg_response_123',
                    'conversation_id': 'conv_123',
                    'from': test_contact.phone,
                    'to': '+15551234567',
                    'body': "Yes, I'm very interested! Please tell me more.",
                    'created_at': utc_now().isoformat(),
                    'direction': 'incoming'
                }
            }
            
            # Act 1: Process webhook (should create activity)
            webhook_result = webhook_service.process_webhook(webhook_payload)
            
            # Act 2: Track response in analytics
            response_event = {
                'campaign_id': campaign.id,
                'contact_id': test_contact.id,
                'activity_id': webhook_result.unwrap()['activity_id'],
                'response_text': webhook_payload['data']['body'],
                'received_at': utc_now(),
                'variant': membership.variant_sent
            }
            
            tracking_result = response_analytics_service.track_response_from_webhook(response_event)
            
            # Act 3: Calculate updated analytics
            analytics_result = response_analytics_service.calculate_response_rate_with_confidence(
                campaign.id
            )
            
            # Assert
            assert webhook_result.is_success()
            assert tracking_result.is_success()
            assert analytics_result.is_success()
            
            # Verify response was tracked
            tracking_data = tracking_result.unwrap()
            assert tracking_data['response_tracked'] == True
            assert tracking_data['sentiment'] in ['positive', 'neutral', 'negative']
            
            # Verify analytics updated
            analytics_data = analytics_result.unwrap()
            assert analytics_data['total_responses'] >= 1
            assert analytics_data['response_rate'] > 0
            
            # Verify database state
            response_record = db_session.query(CampaignResponse).filter_by(
                campaign_id=campaign.id,
                contact_id=test_contact.id
            ).first()
            
            assert response_record is not None
            assert response_record.response_received == True
            assert response_record.sentiment is not None
    
    def test_multiple_responses_same_campaign(self, app, db_session, 
                                           response_analytics_service, 
                                           sample_ab_campaign):
        """Test tracking multiple responses for the same campaign"""
        with app.app_context():
            # Arrange
            campaign = sample_ab_campaign['campaign']
            contacts = sample_ab_campaign['contacts'][:5]  # Use first 5 contacts
            
            response_events = [
                {
                    'campaign_id': campaign.id,
                    'contact_id': contact.id,
                    'activity_id': 100 + i,
                    'response_text': f"Response {i} - {'positive' if i % 2 == 0 else 'negative'}",
                    'received_at': utc_now() - timedelta(minutes=30 - i * 5),
                    'variant': 'A' if i % 2 == 0 else 'B'
                }
                for i, contact in enumerate(contacts)
            ]
            
            # Act
            results = []
            for event in response_events:
                result = response_analytics_service.track_response_from_webhook(event)
                results.append(result)
            
            # Calculate final analytics
            analytics_result = response_analytics_service.calculate_response_rate_with_confidence(
                campaign.id
            )
            
            # Assert
            assert all(r.is_success() for r in results)
            assert analytics_result.is_success()
            
            analytics_data = analytics_result.unwrap()
            assert analytics_data['total_responses'] == 5
            assert analytics_data['response_rate'] > 0
            
            # Verify database has all responses
            response_count = db_session.query(CampaignResponse).filter_by(
                campaign_id=campaign.id
            ).count()
            assert response_count == 5

    # ===== A/B Testing Integration =====
    
    def test_ab_test_variant_comparison_integration(self, app, db_session,
                                                  response_analytics_service,
                                                  sample_ab_campaign):
        """Test A/B test variant comparison with real data"""
        with app.app_context():
            # Arrange
            campaign = sample_ab_campaign['campaign']
            variant_a_contacts = [c for i, c in enumerate(sample_ab_campaign['contacts']) if i % 2 == 0]
            variant_b_contacts = [c for i, c in enumerate(sample_ab_campaign['contacts']) if i % 2 == 1]
            
            # Create responses for variant A (higher response rate)
            variant_a_responses = variant_a_contacts[:30]  # 30 out of 100 = 30% response rate
            for i, contact in enumerate(variant_a_responses):
                response_event = {
                    'campaign_id': campaign.id,
                    'contact_id': contact.id,
                    'activity_id': 200 + i,
                    'response_text': "Variant A response - looks good!",
                    'received_at': utc_now() - timedelta(minutes=60 - i),
                    'variant': 'A'
                }
                response_analytics_service.track_response_from_webhook(response_event)
            
            # Create responses for variant B (lower response rate)
            variant_b_responses = variant_b_contacts[:20]  # 20 out of 100 = 20% response rate
            for i, contact in enumerate(variant_b_responses):
                response_event = {
                    'campaign_id': campaign.id,
                    'contact_id': contact.id,
                    'activity_id': 300 + i,
                    'response_text': "Variant B response - okay",
                    'received_at': utc_now() - timedelta(minutes=45 - i),
                    'variant': 'B'
                }
                response_analytics_service.track_response_from_webhook(response_event)
            
            # Act
            comparison_result = response_analytics_service.compare_ab_test_variants(campaign.id)
            
            # Assert
            assert comparison_result.is_success()
            data = comparison_result.unwrap()
            
            # Verify variant performance
            assert data['variant_a']['response_rate'] == 0.30
            assert data['variant_b']['response_rate'] == 0.20
            assert data['variant_a']['responses'] == 30
            assert data['variant_b']['responses'] == 20
            
            # Verify statistical testing
            assert 'statistical_test' in data
            assert 'chi_square' in data['statistical_test']
            assert 'p_value' in data['statistical_test']
            assert isinstance(data['statistical_test']['significant'], bool)
    
    def test_ab_test_insufficient_data_handling(self, app, db_session,
                                              response_analytics_service):
        """Test A/B test handling when insufficient data for statistical significance"""
        with app.app_context():
            # Arrange - create small campaign
            campaign = CampaignFactory.create(
                name="Small A/B Test",
                campaign_type="ab_test",
                status="running"
            )
            
            contacts = ContactFactory.create_batch(10)  # Very small sample
            
            # Create minimal responses
            for i, contact in enumerate(contacts[:3]):
                response_event = {
                    'campaign_id': campaign.id,
                    'contact_id': contact.id,
                    'activity_id': 400 + i,
                    'response_text': "Test response",
                    'received_at': utc_now(),
                    'variant': 'A' if i % 2 == 0 else 'B'
                }
                response_analytics_service.track_response_from_webhook(response_event)
            
            # Act
            comparison_result = response_analytics_service.compare_ab_test_variants(campaign.id)
            
            # Assert
            assert comparison_result.is_success()
            data = comparison_result.unwrap()
            
            # Should indicate insufficient data
            assert data.get('insufficient_data') == True
            assert data.get('minimum_sample_size') > 10
            assert data.get('recommendation') == 'collect_more_data'

    # ===== Real-Time Analytics Updates =====
    
    def test_real_time_analytics_updates(self, app, db_session,
                                       response_analytics_service,
                                       sample_ab_campaign):
        """Test that analytics update in real-time as responses come in"""
        with app.app_context():
            campaign = sample_ab_campaign['campaign']
            contacts = sample_ab_campaign['contacts'][:10]
            
            # Take baseline measurement
            initial_analytics = response_analytics_service.calculate_response_rate_with_confidence(
                campaign.id
            )
            assert initial_analytics.is_success()
            initial_data = initial_analytics.unwrap()
            initial_responses = initial_data.get('total_responses', 0)
            
            # Add responses one by one and verify updates
            for i, contact in enumerate(contacts):
                # Track response
                response_event = {
                    'campaign_id': campaign.id,
                    'contact_id': contact.id,
                    'activity_id': 500 + i,
                    'response_text': f"Real-time response {i}",
                    'received_at': utc_now(),
                    'variant': 'A' if i % 2 == 0 else 'B'
                }
                
                track_result = response_analytics_service.track_response_from_webhook(response_event)
                assert track_result.is_success()
                
                # Verify analytics updated
                updated_analytics = response_analytics_service.calculate_response_rate_with_confidence(
                    campaign.id
                )
                assert updated_analytics.is_success()
                updated_data = updated_analytics.unwrap()
                
                # Should have one more response
                expected_responses = initial_responses + i + 1
                assert updated_data['total_responses'] == expected_responses
                
                # Response rate should be recalculated
                if updated_data['total_sent'] > 0:
                    expected_rate = expected_responses / updated_data['total_sent']
                    assert abs(updated_data['response_rate'] - expected_rate) < 0.01

    # ===== Performance Testing =====
    
    def test_large_campaign_analytics_performance(self, app, db_session,
                                                 response_analytics_service):
        """Test analytics performance with large campaign datasets"""
        with app.app_context():
            # Arrange - create large campaign
            campaign = CampaignFactory.create(
                name="Large Performance Test Campaign",
                status="completed"
            )
            
            # Create large number of contacts and responses
            large_contact_batch = ContactFactory.create_batch(
                1000,  # 1000 contacts
                phone_factory_kwargs={'start_with': '+1777'}
            )
            
            # Simulate 200 responses (20% response rate)
            responding_contacts = large_contact_batch[:200]
            
            # Use bulk operations for performance
            start_time = time.time()
            
            # Bulk create response records
            response_records = [
                {
                    'contact_id': contact.id,
                    'sent_activity_id': 1000 + i,
                    'variant_sent': 'A' if i % 2 == 0 else 'B',
                    'message_sent': f"Bulk message {i}",
                    'sent_at': utc_now() - timedelta(hours=2),
                    'response_received': True,
                    'responded_at': utc_now() - timedelta(minutes=30),
                    'sentiment': 'positive' if i % 3 == 0 else 'neutral'
                }
                for i, contact in enumerate(responding_contacts)
            ]
            
            # Bulk create using repository (should be implemented)
            repository = current_app.services.get('campaign_response_repository')
            bulk_result = repository.bulk_create_responses(campaign.id, response_records)
            
            # Calculate analytics
            analytics_result = response_analytics_service.calculate_response_rate_with_confidence(
                campaign.id
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Assert
            assert bulk_result >= 200  # At least 200 records created
            assert analytics_result.is_success()
            
            analytics_data = analytics_result.unwrap()
            assert analytics_data['total_responses'] == 200
            assert analytics_data['response_rate'] == 0.20
            
            # Performance assertion - should complete within reasonable time
            assert processing_time < 5.0  # Less than 5 seconds for 1000 contacts, 200 responses
    
    def test_concurrent_response_tracking(self, app, db_session,
                                        response_analytics_service,
                                        sample_ab_campaign):
        """Test concurrent response tracking doesn't cause race conditions"""
        import threading
        import time
        
        with app.app_context():
            campaign = sample_ab_campaign['campaign']
            contacts = sample_ab_campaign['contacts'][:20]
            
            results = []
            errors = []
            
            def track_responses_batch(contact_batch, batch_id):
                """Track responses for a batch of contacts"""
                try:
                    for i, contact in enumerate(contact_batch):
                        response_event = {
                            'campaign_id': campaign.id,
                            'contact_id': contact.id,
                            'activity_id': batch_id * 100 + i,
                            'response_text': f"Concurrent response {batch_id}-{i}",
                            'received_at': utc_now(),
                            'variant': 'A' if (batch_id + i) % 2 == 0 else 'B'
                        }
                        
                        result = response_analytics_service.track_response_from_webhook(response_event)
                        results.append(result)
                        
                        # Small delay to increase chance of race conditions
                        time.sleep(0.01)
                        
                except Exception as e:
                    errors.append(e)
            
            # Create multiple threads to track responses concurrently
            threads = []
            batch_size = 5
            for i in range(0, len(contacts), batch_size):
                batch = contacts[i:i + batch_size]
                thread = threading.Thread(
                    target=track_responses_batch,
                    args=(batch, i // batch_size)
                )
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # Assert no errors occurred
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(results) == len(contacts)
            assert all(r.is_success() for r in results)
            
            # Verify final analytics are consistent
            final_analytics = response_analytics_service.calculate_response_rate_with_confidence(
                campaign.id
            )
            assert final_analytics.is_success()
            
            final_data = final_analytics.unwrap()
            assert final_data['total_responses'] == len(contacts)

    # ===== Service Registry Integration =====
    
    def test_service_registry_provides_all_dependencies(self, app):
        """Test that service registry provides all required dependencies"""
        with app.app_context():
            # Verify all required services are available
            required_services = [
                'response_analytics',
                'campaign_response_repository',
                'campaign_repository',
                'activity_repository',
                'contact_repository',
                'sentiment_analysis',
                'cache'
            ]
            
            for service_name in required_services:
                service = current_app.services.get(service_name)
                assert service is not None, f"Service '{service_name}' not found in registry"
            
            # Verify response analytics service has all dependencies
            analytics_service = current_app.services.get('response_analytics')
            assert hasattr(analytics_service, 'response_repository')
            assert hasattr(analytics_service, 'campaign_repository')
            assert hasattr(analytics_service, 'sentiment_service')
    
    def test_database_transaction_integrity(self, app, db_session,
                                          response_analytics_service):
        """Test that database transactions maintain integrity during response tracking"""
        with app.app_context():
            # Arrange
            campaign = CampaignFactory.create(name="Transaction Test")
            contact = ContactFactory.create()
            
            # Act - simulate transaction failure scenario
            response_event = {
                'campaign_id': campaign.id,
                'contact_id': contact.id,
                'activity_id': 999,
                'response_text': "Test response",
                'received_at': utc_now(),
                'variant': 'A'
            }
            
            # Mock a failure in sentiment analysis to test rollback
            with patch.object(response_analytics_service.sentiment_service, 'analyze_response') as mock_sentiment:
                mock_sentiment.side_effect = Exception("Sentiment analysis failed")
                
                # Attempt to track response
                result = response_analytics_service.track_response_from_webhook(response_event)
                
                # Should handle error gracefully
                # Either succeed without sentiment or fail cleanly
                if result.is_failure():
                    # Verify no partial data was saved
                    response_count = db_session.query(CampaignResponse).filter_by(
                        campaign_id=campaign.id,
                        contact_id=contact.id
                    ).count()
                    assert response_count == 0
                else:
                    # If it succeeded, verify data integrity
                    response = db_session.query(CampaignResponse).filter_by(
                        campaign_id=campaign.id,
                        contact_id=contact.id
                    ).first()
                    assert response is not None
                    # Sentiment should be None due to failure
                    assert response.sentiment is None

    # ===== Error Recovery and Resilience =====
    
    def test_analytics_graceful_degradation(self, app, db_session,
                                          response_analytics_service):
        """Test that analytics degrade gracefully when external services fail"""
        with app.app_context():
            # Arrange
            campaign = CampaignFactory.create()
            contact = ContactFactory.create()
            
            # Mock cache service failure
            with patch.object(response_analytics_service.cache_service, 'get') as mock_cache:
                mock_cache.side_effect = Exception("Cache service unavailable")
                
                # Analytics should still work without cache
                result = response_analytics_service.get_response_analytics_cached(campaign.id)
                
                # Should either succeed without cache or fail gracefully
                if result.is_success():
                    data = result.unwrap()
                    assert 'cache_hit' in data
                    assert data['cache_hit'] == False
                else:
                    # Acceptable failure mode
                    assert "Cache service" in str(result.unwrap_error())
    
    def test_webhook_processing_pipeline_resilience(self, app, db_session,
                                                   response_analytics_service,
                                                   webhook_service):
        """Test resilience of webhook processing pipeline"""
        with app.app_context():
            # Arrange
            campaign = CampaignFactory.create()
            contact = ContactFactory.create()
            
            # Test various malformed webhook payloads
            malformed_payloads = [
                {'type': 'message.received'},  # Missing data
                {'data': {'body': 'test'}},  # Missing type
                {'type': 'unknown_type', 'data': {}},  # Unknown type
                {'type': 'message.received', 'data': {'body': None}},  # Null body
            ]
            
            for payload in malformed_payloads:
                # Should handle malformed payloads gracefully
                result = webhook_service.process_webhook(payload)
                
                # Either handle gracefully or fail with clear error
                if result.is_failure():
                    error = result.unwrap_error()
                    assert isinstance(error, (ValueError, KeyError, TypeError))
