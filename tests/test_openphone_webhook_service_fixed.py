"""
Fixed tests for OpenPhone Webhook Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from services.openphone_webhook_service import OpenPhoneWebhookService
from crm_database import db, Contact, Conversation, Activity


class TestOpenPhoneWebhookServiceFixed:
    """Fixed test cases for OpenPhone Webhook service"""
    
    @pytest.fixture
    def webhook_service(self, app):
        """Create a webhook service instance"""
        with app.app_context():
            service = OpenPhoneWebhookService()
            yield service
    
    def test_process_webhook_unknown_type(self, webhook_service, app):
        """Test processing webhook with unknown type"""
        with app.app_context():
            webhook_data = {
                'type': 'unknown.event',
                'data': {}
            }
            
            result = webhook_service.process_webhook(webhook_data)
            
            assert result['status'] == 'ignored'
            assert 'Unknown event type' in result['reason']
    
    def test_process_webhook_empty(self, webhook_service, app):
        """Test processing empty webhook"""
        with app.app_context():
            result = webhook_service.process_webhook({})
            
            assert result['status'] == 'ignored'
            assert 'Unknown event type' in result['reason']
    
    def test_handle_message_webhook_missing_data(self, webhook_service, app):
        """Test handling message webhook with missing data"""
        with app.app_context():
            webhook_data = {
                'type': 'message.created',
                'data': {
                    'object': {
                        # Missing required fields
                    }
                }
            }
            
            result = webhook_service.process_webhook(webhook_data)
            
            assert result['status'] == 'error'
    
    def test_handle_token_validation(self, webhook_service, app):
        """Test handling token validation webhook"""
        with app.app_context():
            webhook_data = {
                'type': 'token.validated',
                'data': {
                    'valid': True
                }
            }
            
            result = webhook_service.process_webhook(webhook_data)
            
            assert result['status'] == 'success'
            assert result['message'] == 'Token validated successfully'
    
    @patch('services.openphone_webhook_service.db.session.commit')
    def test_process_webhook_database_error(self, mock_commit, webhook_service, app):
        """Test handling database errors"""
        with app.app_context():
            mock_commit.side_effect = Exception('Database error')
            
            webhook_data = {
                'type': 'message.created',
                'data': {
                    'object': {
                        'id': 'msg123',
                        'body': 'Test message',
                        'from': '+15551234567',
                        'to': ['+15559999999'],
                        'conversationId': 'conv123',
                        'direction': 'incoming',
                        'createdAt': '2025-01-01T10:00:00Z'
                    }
                }
            }
            
            result = webhook_service.process_webhook(webhook_data)
            
            assert result['status'] == 'error'
            assert 'Error processing webhook' in result['message']
    
    def test_handle_call_webhook(self, webhook_service, app):
        """Test handling call webhook"""
        with app.app_context():
            webhook_data = {
                'type': 'call.completed',
                'data': {
                    'object': {
                        'id': 'call123',
                        'from': '+15551234567',
                        'to': '+15559999999',
                        'conversationId': 'conv123',
                        'direction': 'incoming',
                        'status': 'completed',
                        'duration': 120,
                        'createdAt': '2025-01-01T10:00:00Z',
                        'completedAt': '2025-01-01T10:02:00Z'
                    }
                }
            }
            
            # Create a contact for the test
            contact = Contact(
                first_name='Test',
                last_name='Contact',
                phone='+15551234567'
            )
            db.session.add(contact)
            db.session.commit()
            
            result = webhook_service.process_webhook(webhook_data)
            
            # Clean up
            Activity.query.filter_by(activity_id='call123').delete()
            Conversation.query.filter_by(conversation_id='conv123').delete()
            db.session.delete(contact)
            db.session.commit()
            
            assert result['status'] == 'success'
    
    def test_get_or_create_contact_new(self, webhook_service, app):
        """Test creating new contact"""
        with app.app_context():
            phone = '+15552223333'
            
            contact = webhook_service._get_or_create_contact(phone)
            
            assert contact is not None
            assert contact.phone == phone
            assert contact.first_name == 'Unknown'
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()
    
    def test_get_or_create_contact_existing(self, webhook_service, app):
        """Test getting existing contact"""
        with app.app_context():
            # Create existing contact
            existing = Contact(
                first_name='Existing',
                last_name='Contact',
                phone='+15554445555'
            )
            db.session.add(existing)
            db.session.commit()
            
            # Get contact
            contact = webhook_service._get_or_create_contact('+15554445555')
            
            assert contact.id == existing.id
            assert contact.first_name == 'Existing'
            
            # Clean up
            db.session.delete(existing)
            db.session.commit()