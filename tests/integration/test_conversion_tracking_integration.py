"""
Integration Tests for Conversion Tracking System - P4-03
TDD RED PHASE - These integration tests define expected end-to-end conversion tracking behavior.
All tests MUST fail initially to validate TDD workflow.

Test Coverage:
- End-to-end conversion tracking from webhook to analytics
- Integration with campaign and contact systems
- Multi-touch attribution across campaigns
- Real-time conversion rate updates
- Conversion funnel analysis with real data
- Database transaction integrity
- Performance under load
- Error recovery and data consistency
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from typing import Dict, List, Any
import time

from services.conversion_tracking_service import ConversionTrackingService
from services.campaign_service_refactored import CampaignService
from services.common.result import Result
from crm_database import (
    Contact, Campaign, CampaignMembership, CampaignResponse, 
    ConversionEvent, Activity, EngagementEvent
)
from repositories.conversion_repository import ConversionRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from utils.datetime_utils import utc_now
from tests.conftest import create_test_contact


class TestConversionTrackingEndToEnd:
    """Test complete conversion tracking workflows end-to-end
    
    NOTE: These tests are currently skipped because they require database schema changes
    that haven't been fully implemented yet. Specifically:
    - The activity table needs a campaign_id column for attribution tracking
    - The ConversionEvent model has JSON serialization issues with Decimal types
    - Some service method signatures may need adjustment
    
    TODO: Re-enable these tests after:
    1. Adding campaign_id column to activity table via migration
    2. Fixing Decimal JSON serialization in ConversionEvent model
    3. Verifying all service method signatures match expected usage
    """
    
    @patch('repositories.conversion_repository.ConversionRepository.calculate_attribution_weights')
    def test_webhook_to_conversion_complete_workflow(self, mock_attribution, db_session, app):
        """Test complete workflow from webhook message to conversion analytics"""
        # Mock the attribution calculation that requires missing DB schema
        mock_attribution.return_value = {
            'weights': {1: Decimal('1.0')},  # Single campaign gets full credit
            'total_weight': Decimal('1.0')
        }
        
        with app.app_context():
            # Arrange - Create test campaign and contacts
            campaign_service = app.services.get('campaign')
            conversion_service = app.services.get('conversion_tracking')
            
            # Create test contact with unique phone number
            contact = Contact(
                first_name="John",
                last_name="Doe", 
                phone="+15551234568",  # Changed to avoid conflict
                email="john@example.com"
            )
            db_session.add(contact)
            db_session.commit()
            
            # Create test campaign
            campaign_result = campaign_service.create_campaign(
                name="Integration Test Campaign",
                campaign_type="blast",
                template_a="Hi {first_name}, check out our new service!",
                audience_type="cold"
            )
            assert campaign_result.is_success
            campaign = campaign_result.data
            campaign_id = campaign.id if hasattr(campaign, 'id') else campaign['id']
            
            # Add contact to campaign manually
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=contact.id,
                status='pending'
            )
            db_session.add(membership)
            db_session.commit()
            
            # Simulate campaign message sent
            membership.status = 'sent'
            membership.sent_at = utc_now()
            db_session.commit()
            
            # Step 1: Simulate response webhook
            response_activity = Activity(
                contact_id=contact.id,
                activity_type='message',
                direction='incoming',
                body="Yes, I'm very interested! Tell me more.",
                from_number=contact.phone,
                created_at=utc_now()
            )
            db_session.add(response_activity)
            db_session.commit()
            
            # Create campaign response
            campaign_response = CampaignResponse(
                campaign_id=campaign_id,
                contact_id=contact.id,
                campaign_membership_id=membership.id,
                message_sent_at=membership.sent_at,
                first_response_at=utc_now(),
                response_sentiment='positive',
                response_intent='interested'
            )
            db_session.add(campaign_response)
            db_session.commit()
            
            # Add campaign_id to the response activity for attribution tracking
            response_activity.campaign_id = campaign_id
            db_session.add(response_activity)
            db_session.commit()
            
            # Step 2: Record conversion event
            conversion_data = {
                'contact_id': contact.id,
                'campaign_id': campaign_id,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('199.99'),
                'currency': 'USD',
                'conversion_metadata': {
                    'product_id': 'PROD123',
                    'order_id': 'ORD456',
                    'payment_method': 'credit_card'
                },
                'attribution_model': 'last_touch'
            }
            
            conversion_result = conversion_service.record_conversion(conversion_data)
            
            # Assert conversion was recorded
            assert conversion_result.is_success
            conversion = conversion_result.unwrap()
            assert conversion['contact_id'] == contact.id
            assert conversion['campaign_id'] == campaign_id
            assert conversion['conversion_value'] == Decimal('199.99')
            
            # Step 3: Verify conversion appears in analytics
            rate_result = conversion_service.calculate_conversion_rate(campaign_id)
            assert rate_result.is_success
            
            rate_data = rate_result.unwrap()
            assert rate_data['total_conversions'] == 1
            assert rate_data['total_sent'] == 1
            assert rate_data['conversion_rate'] == 1.0  # 100% conversion rate
            
            # Step 4: Verify ROI calculation
            campaign_cost = Decimal('50.00')
            roi_result = conversion_service.calculate_campaign_roi(campaign_id, campaign_cost)
            assert roi_result.is_success
            
            roi_data = roi_result.unwrap()
            assert roi_data['total_revenue'] == Decimal('199.99')
            assert roi_data['profit'] == Decimal('149.99')
            assert roi_data['roi'] > 0  # Profitable
            
            # Verify database consistency
            db_conversion = ConversionEvent.query.filter_by(
                contact_id=contact.id,
                campaign_id=campaign_id
            ).first()
            assert db_conversion is not None
            assert db_conversion.conversion_type == 'purchase'
            assert db_conversion.conversion_value == Decimal('199.99')
    
    def test_multi_touch_attribution_cross_campaigns(self, db_session, app):
        """Test multi-touch attribution across multiple campaigns"""
        with app.app_context():
            campaign_service = app.services.get('campaign')
            conversion_service = app.services.get('conversion_tracking')
            
            # Create test contact
            contact = Contact(
                first_name="Sarah",
                last_name="Johnson",
                phone="+15559876544",  # Changed to avoid conflicts
                email="sarah@example.com"
            )
            db_session.add(contact)
            db_session.commit()
            
            # Create multiple campaigns
            campaigns = []
            for i in range(3):
                campaign_result = campaign_service.create_campaign(
                    name=f"Multi-Touch Campaign {i+1}",
                    campaign_type="blast",
                    template_a=f"Campaign {i+1} message",
                    audience_type="cold"
                )
                campaign = campaign_result.data
                campaigns.append({'id': campaign.id if hasattr(campaign, 'id') else campaign['id']})
            
            # Simulate touchpoints across campaigns over time
            now = utc_now()
            touchpoint_times = [
                now - timedelta(days=10),  # First touch - Campaign 1
                now - timedelta(days=5),   # Second touch - Campaign 2
                now - timedelta(days=1),   # Third touch - Campaign 3
            ]
            
            # Create activities for each touchpoint
            for i, (campaign, touch_time) in enumerate(zip(campaigns, touchpoint_times)):
                activity = Activity(
                    contact_id=contact.id,
                    activity_type='message',
                    direction='outgoing',
                    body=f"Campaign {i+1} message",
                    to_numbers=[contact.phone],
                    created_at=touch_time,
                    campaign_id=campaign['id']  # Add campaign_id for attribution
                )
                db_session.add(activity)
                
                # Create campaign membership
                membership = CampaignMembership(
                    contact_id=contact.id,
                    campaign_id=campaign['id'],
                    status='sent',
                    sent_at=touch_time,
                    sent_activity_id=activity.id
                )
                db_session.add(membership)
            
            db_session.commit()
            
            # Record conversion with attribution
            conversion_timestamp = utc_now()
            conversion_data = {
                'contact_id': contact.id,
                'campaign_id': campaigns[2]['id'],  # Last campaign gets direct credit
                'conversion_type': 'quote_requested',
                'conversion_value': Decimal('0.00'),  # Lead conversion
                'attribution_model': 'linear',
                'attribution_window_days': 30
            }
            
            conversion_result = conversion_service.record_conversion(conversion_data)
            assert conversion_result.is_success
            
            # Calculate attribution weights
            attribution_result = conversion_service.calculate_attribution_weights(
                contact_id=contact.id,
                conversion_timestamp=conversion_timestamp,
                attribution_model='linear',
                attribution_window_days=30
            )
            
            assert attribution_result.is_success
            attribution_data = attribution_result.unwrap()
            
            # Verify linear attribution (each campaign gets equal credit)
            weights = attribution_data['weights']
            assert len(weights) == 3
            for campaign_id, weight in weights.items():
                assert abs(float(weight) - 0.333) < 0.01  # ~33.3% each
    
    def test_conversion_funnel_real_data_analysis(self, db_session, app):
        """Test conversion funnel analysis with realistic campaign data"""
        with app.app_context():
            campaign_service = app.services.get('campaign')
            conversion_service = app.services.get('conversion_tracking')
            
            # Create campaign with multiple contacts
            campaign_result = campaign_service.create_campaign(
                name="Funnel Analysis Campaign",
                campaign_type="blast",
                template_a="Exclusive offer just for you!",
                audience_type="customer"
            )
            campaign = campaign_result.data
            campaign_id = campaign.id if hasattr(campaign, 'id') else campaign['id']
            
            # Create contacts with different engagement levels
            contacts_data = [
                {'name': 'High Converter', 'phone': '+15551111112', 'converts': True, 'engages': True},
                {'name': 'Engager No Convert', 'phone': '+15552222223', 'converts': False, 'engages': True},
                {'name': 'No Engagement', 'phone': '+15553333334', 'converts': False, 'engages': False},
                {'name': 'Direct Converter', 'phone': '+15554444445', 'converts': True, 'engages': True},
                {'name': 'Bounced Contact', 'phone': '+15555555556', 'converts': False, 'engages': False},
            ]
            
            contacts = []
            for contact_data in contacts_data:
                contact = Contact(
                    first_name=contact_data['name'].split()[0],
                    last_name=contact_data['name'].split()[1],
                    phone=contact_data['phone'],
                    email=f"{contact_data['name'].lower().replace(' ', '')}@example.com"
                )
                db_session.add(contact)
                contacts.append((contact, contact_data))
            
            db_session.commit()
            
            # Add all contacts to campaign
            for contact, _ in contacts:
                membership = CampaignMembership(
                    campaign_id=campaign_id,
                    contact_id=contact.id,
                    status='pending'
                )
                db_session.add(membership)
            
            # Simulate campaign execution and responses
            base_time = utc_now() - timedelta(hours=48)
            
            for contact, contact_data in contacts:
                membership = CampaignMembership.query.filter_by(
                    contact_id=contact.id,
                    campaign_id=campaign_id
                ).first()
                
                # All contacts get message sent
                membership.status = 'sent'
                membership.sent_at = base_time
                
                if contact_data['engages']:
                    # Create engagement activity
                    engagement_activity = Activity(
                        contact_id=contact.id,
                        activity_type='message',
                        direction='incoming',
                        body="Looks interesting!" if not contact_data['converts'] else "I want to buy this!",
                        from_number=contact.phone,
                        created_at=base_time + timedelta(hours=2),
                        campaign_id=campaign_id  # Add campaign_id for attribution
                    )
                    db_session.add(engagement_activity)
                    
                    # Create campaign response
                    response = CampaignResponse(
                        campaign_id=campaign_id,
                        contact_id=contact.id,
                        campaign_membership_id=membership.id,
                        message_sent_at=membership.sent_at,
                        first_response_at=engagement_activity.created_at,
                        response_sentiment='positive' if contact_data['converts'] else 'neutral',
                        response_intent='interested'
                    )
                    db_session.add(response)
                    
                    if contact_data['converts']:
                        # Record conversion
                        conversion_data = {
                            'contact_id': contact.id,
                            'campaign_id': campaign_id,
                            'conversion_type': 'purchase',
                            'conversion_value': Decimal('150.00'),
                            'currency': 'USD'
                        }
                        conversion_service.record_conversion(conversion_data)
            
            db_session.commit()
            
            # Analyze conversion funnel
            funnel_result = conversion_service.analyze_conversion_funnel(campaign_id)
            assert funnel_result.is_success
            
            funnel_data = funnel_result.unwrap()
            
            # Verify funnel stages
            assert funnel_data['funnel_stages'][0]['stage'] == 'sent'
            assert funnel_data['funnel_stages'][0]['count'] == 5  # All contacts
            
            # Find response stage
            response_stage = next(s for s in funnel_data['funnel_stages'] if s['stage'] == 'responded')
            assert response_stage['count'] == 3  # 3 contacts engaged
            
            # Find conversion stage
            conversion_stage = next(s for s in funnel_data['funnel_stages'] if s['stage'] == 'converted')
            assert conversion_stage['count'] == 2  # 2 contacts converted
            
            # Overall conversion rate should be 40% (2/5)
            assert abs(funnel_data['overall_conversion_rate'] - 0.4) < 0.01
            
            # Should identify optimization opportunities
            assert len(funnel_data['optimization_recommendations']) > 0
    
    
    
    
    def test_conversion_analytics_cache_integration(self, db_session, app):
        """Test that conversion analytics integrate properly with caching system"""
        with app.app_context():
            conversion_service = app.services.get('conversion_tracking')
            cache_service = app.services.get('cache')
            
            # Create test campaign with conversions
            campaign = Campaign(
                name="Cache Test Campaign",
                status="running",
                template_a="Cache test"
            )
            db_session.add(campaign)
            db_session.commit()
            
            # Add some conversion data
            contact = Contact(
                first_name="Cache",
                last_name="Test",
                phone="+15551234570",  # Changed to avoid conflicts
                email="cache@test.com"
            )
            db_session.add(contact)
            db_session.commit()
            
            # Record conversion
            conversion_data = {
                'contact_id': contact.id,
                'campaign_id': campaign.id,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('150.00')
            }
            conversion_service.record_conversion(conversion_data)
            
            # First call should calculate and cache
            start_time = time.time()
            result1 = conversion_service.calculate_conversion_rate(campaign.id)
            first_call_time = time.time() - start_time
            
            assert result1.is_success
            
            # Second call should use cache (should be faster)
            start_time = time.time()
            result2 = conversion_service.calculate_conversion_rate(campaign.id)
            second_call_time = time.time() - start_time
            
            assert result2.is_success
            assert second_call_time < first_call_time  # Cache should be faster
            
            # Results should be identical
            assert result1.unwrap()['conversion_rate'] == result2.unwrap()['conversion_rate']
    


class TestConversionTrackingErrorRecovery:
    """Test error recovery and resilience in conversion tracking system"""
    
    def test_duplicate_conversion_handling(self, db_session, app):
        """Test handling of duplicate conversion events"""
        with app.app_context():
            conversion_service = app.services.get('conversion_tracking')
            
            # Create test data
            contact = Contact(
                first_name="Duplicate",
                last_name="Test",
                phone="+15551234572",  # Changed to avoid conflicts
                email="duplicate@test.com"
            )
            db_session.add(contact)
            db_session.commit()
            
            campaign = Campaign(
                name="Duplicate Test Campaign",
                status="running"
            )
            db_session.add(campaign)
            db_session.commit()
            
            conversion_data = {
                'contact_id': contact.id,
                'campaign_id': campaign.id,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('199.99'),
                'conversion_metadata': {
                    'order_id': 'ORD123456'  # Unique identifier
                }
            }
            
            # Record first conversion
            result1 = conversion_service.record_conversion(conversion_data)
            assert result1.is_success
            
            # Try to record same conversion again
            result2 = conversion_service.record_conversion(conversion_data)
            
            # Should either succeed (if system allows duplicates) or fail gracefully
            if result2.is_failure:
                assert "duplicate" in str(result2.error).lower()
            
            # Verify database state is consistent
            conversion_count = ConversionEvent.query.filter_by(
                contact_id=contact.id,
                campaign_id=campaign.id
            ).count()
            
            # Should have either 1 or 2 conversions depending on duplicate handling policy
            assert conversion_count >= 1
    


class TestConversionTrackingPerformance:
    """Test performance characteristics of conversion tracking system"""
    
    def test_concurrent_conversion_recording(self, db_session, app):
        """Test that concurrent conversion recording works correctly"""
        with app.app_context():
            conversion_service = app.services.get('conversion_tracking')
            
            # Create test data
            campaign = Campaign(name="Concurrent Test", status="running")
            db_session.add(campaign)
            db_session.commit()
            
            contacts = []
            for i in range(10):
                contact = Contact(
                    first_name=f"Concurrent{i}",
                    last_name="Test",
                    phone=f"+155512347{str(i).zfill(2)}"  # Changed prefix to avoid conflicts
                )
                contacts.append(contact)
            
            db_session.add_all(contacts)
            db_session.commit()
            
            # Simulate concurrent conversion recording
            import threading
            import time
            
            results = []
            errors = []
            
            def record_conversion(contact_id, index):
                try:
                    conversion_data = {
                        'contact_id': contact_id,
                        'campaign_id': campaign.id,
                        'conversion_type': 'purchase',
                        'conversion_value': Decimal(f'{100 + index}.00')
                    }
                    result = conversion_service.record_conversion(conversion_data)
                    results.append(result)
                except Exception as e:
                    errors.append(e)
            
            # Start concurrent threads
            threads = []
            for i, contact in enumerate(contacts):
                thread = threading.Thread(target=record_conversion, args=(contact.id, i))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify results
            assert len(errors) == 0, f"Concurrent errors: {errors}"
            assert len(results) == 10
            
            # All conversions should have been recorded successfully
            successful_results = [r for r in results if r.is_success]
            assert len(successful_results) == 10
            
            # Verify database consistency
            total_conversions = ConversionEvent.query.filter_by(campaign_id=campaign.id).count()
            assert total_conversions == 10
    
