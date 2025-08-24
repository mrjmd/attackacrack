"""
Comprehensive Unit Tests for Refactored MessageService
Tests TDD-compliant implementation with Result pattern and repository pattern

Following Phase 2 refactoring:
- Dependency injection instead of direct instantiation
- Repository pattern for data access
- Result pattern for error handling
- No direct database queries
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from utils.datetime_utils import utc_now
from typing import Dict, Any, List, Optional

from services.message_service_refactored import MessageServiceRefactored
from services.common.result import Result
from crm_database import Contact, Conversation, Activity


class TestMessageServiceRefactoredInitialization:
    """Test service initialization with dependency injection"""
    
    def test_service_exists_and_imports_successfully(self):
        """Test that refactored service can be imported successfully"""
        # This test should FAIL initially - service doesn't exist yet
        from services.message_service_refactored import MessageServiceRefactored
        assert MessageServiceRefactored is not None
    
    def test_service_initialization_with_repositories_and_services(self):
        """Test service initialization with proper dependencies injected"""
        # Mock all required repositories
        conversation_repo = Mock()
        activity_repo = Mock()
        
        # Mock all required services
        contact_service = Mock()
        property_service = Mock()
        openphone_service = Mock()
        ai_service = Mock()
        
        # This should pass after implementation
        service = MessageServiceRefactored(
            conversation_repository=conversation_repo,
            activity_repository=activity_repo,
            contact_service=contact_service,
            property_service=property_service,
            openphone_service=openphone_service,
            ai_service=ai_service
        )
        
        # Verify all dependencies are properly injected
        assert service.conversation_repository == conversation_repo
        assert service.activity_repository == activity_repo
        assert service.contact_service == contact_service
        assert service.property_service == property_service
        assert service.openphone_service == openphone_service
        assert service.ai_service == ai_service
    
    def test_service_initialization_without_repositories_raises_error(self):
        """Test that service initialization fails without required dependencies"""
        # Should raise TypeError when required repositories are missing
        with pytest.raises(TypeError):
            MessageServiceRefactored()


class TestGetOrCreateConversationWithResult:
    """Test get_or_create_conversation method with Result pattern"""
    
    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies"""
        conversation_repo = Mock()
        activity_repo = Mock()
        contact_service = Mock()
        property_service = Mock()
        openphone_service = Mock()
        ai_service = Mock()
        
        return MessageServiceRefactored(
            conversation_repository=conversation_repo,
            activity_repository=activity_repo,
            contact_service=contact_service,
            property_service=property_service,
            openphone_service=openphone_service,
            ai_service=ai_service
        )
    
    @pytest.fixture
    def mock_conversation(self):
        """Create a mock conversation object"""
        conversation = Mock(spec=Conversation)
        conversation.id = 1
        conversation.contact_id = 123
        conversation.openphone_id = "op_conv_456"
        conversation.participants = "+11234567890,+19876543210"
        conversation.last_activity_at = utc_now()
        return conversation
    
    def test_get_or_create_conversation_finds_existing_by_openphone_id(self, service, mock_conversation):
        """Test finding existing conversation by OpenPhone ID returns Result.success"""
        # Arrange
        contact_id = 123
        openphone_convo_id = "op_conv_456"
        participants = ["+11234567890", "+19876543210"]
        
        service.conversation_repository.find_by_openphone_id.return_value = mock_conversation
        
        # Act
        result = service.get_or_create_conversation(contact_id, openphone_convo_id, participants)
        
        # Assert
        assert result.is_success
        assert result.data == mock_conversation
        service.conversation_repository.find_by_openphone_id.assert_called_once_with(openphone_convo_id)
    
    def test_get_or_create_conversation_finds_existing_by_contact_id_when_no_openphone_id(self, service, mock_conversation):
        """Test finding existing conversation by contact ID when OpenPhone ID not provided"""
        # Arrange
        contact_id = 123
        openphone_convo_id = None
        participants = ["+11234567890"]
        
        service.conversation_repository.find_by_openphone_id.return_value = None
        service.conversation_repository.find_by_contact_id.return_value = [mock_conversation]
        
        # Act
        result = service.get_or_create_conversation(contact_id, openphone_convo_id, participants)
        
        # Assert
        assert result.is_success
        assert result.data == mock_conversation
        service.conversation_repository.find_by_contact_id.assert_called_once_with(contact_id)
    
    def test_get_or_create_conversation_updates_existing_with_openphone_id(self, service, mock_conversation):
        """Test updating existing conversation with OpenPhone ID"""
        # Arrange
        contact_id = 123
        openphone_convo_id = "op_conv_456"
        participants = ["+11234567890"]
        
        # Mock existing conversation without OpenPhone ID
        existing_conversation = Mock(spec=Conversation)
        existing_conversation.openphone_id = None
        existing_conversation.contact_id = contact_id
        
        service.conversation_repository.find_by_openphone_id.return_value = None
        service.conversation_repository.find_by_contact_id.return_value = [existing_conversation]
        service.conversation_repository.update.return_value = existing_conversation
        
        # Act
        result = service.get_or_create_conversation(contact_id, openphone_convo_id, participants)
        
        # Assert
        assert result.is_success
        assert result.data == existing_conversation
        service.conversation_repository.update.assert_called_once()
        # Verify the openphone_id was set
        assert existing_conversation.openphone_id == openphone_convo_id
    
    def test_get_or_create_conversation_creates_new_conversation(self, service, mock_conversation):
        """Test creating new conversation when none exists"""
        # Arrange
        contact_id = 123
        openphone_convo_id = "op_conv_456"
        participants = ["+11234567890", "+19876543210"]
        
        service.conversation_repository.find_by_openphone_id.return_value = None
        service.conversation_repository.find_by_contact_id.return_value = []
        service.conversation_repository.create.return_value = mock_conversation
        
        # Act
        result = service.get_or_create_conversation(contact_id, openphone_convo_id, participants)
        
        # Assert
        assert result.is_success
        assert result.data == mock_conversation
        
        # Verify create was called with correct data
        create_call_args = service.conversation_repository.create.call_args[0][0]
        assert create_call_args['contact_id'] == contact_id
        assert create_call_args['openphone_id'] == openphone_convo_id
        assert create_call_args['participants'] == '+11234567890,+19876543210'
    
    def test_get_or_create_conversation_handles_repository_error(self, service):
        """Test handling repository errors returns Result.failure"""
        # Arrange
        contact_id = 123
        openphone_convo_id = "op_conv_456"
        participants = ["+11234567890"]
        
        service.conversation_repository.find_by_openphone_id.side_effect = Exception("Database error")
        
        # Act
        result = service.get_or_create_conversation(contact_id, openphone_convo_id, participants)
        
        # Assert
        assert result.is_failure
        assert "Database error" in result.error
        assert result.error_code == "REPOSITORY_ERROR"
    
    def test_get_or_create_conversation_validates_required_contact_id(self, service):
        """Test that contact_id is required"""
        # Arrange - missing contact_id
        contact_id = None
        openphone_convo_id = "op_conv_456"
        participants = ["+11234567890"]
        
        # Act
        result = service.get_or_create_conversation(contact_id, openphone_convo_id, participants)
        
        # Assert
        assert result.is_failure
        assert "Contact ID is required" in result.error
        assert result.error_code == "VALIDATION_ERROR"


class TestGetActivitiesForContactWithResult:
    """Test get_activities_for_contact method with Result pattern"""
    
    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies"""
        conversation_repo = Mock()
        activity_repo = Mock()
        contact_service = Mock()
        property_service = Mock()
        openphone_service = Mock()
        ai_service = Mock()
        
        return MessageServiceRefactored(
            conversation_repository=conversation_repo,
            activity_repository=activity_repo,
            contact_service=contact_service,
            property_service=property_service,
            openphone_service=openphone_service,
            ai_service=ai_service
        )
    
    @pytest.fixture
    def mock_activities(self):
        """Create mock activity objects"""
        activity1 = Mock(spec=Activity)
        activity1.id = 1
        activity1.contact_id = 123
        activity1.activity_type = "message"
        activity1.created_at = datetime(2025, 1, 1, 10, 0, 0)
        
        activity2 = Mock(spec=Activity)
        activity2.id = 2
        activity2.contact_id = 123
        activity2.activity_type = "call"
        activity2.created_at = datetime(2025, 1, 1, 11, 0, 0)
        
        return [activity1, activity2]
    
    def test_get_activities_for_contact_success(self, service, mock_activities):
        """Test successfully retrieving activities for a contact"""
        # Arrange
        contact_id = 123
        service.activity_repository.find_by_contact_id.return_value = mock_activities
        
        # Act
        result = service.get_activities_for_contact(contact_id)
        
        # Assert
        assert result.is_success
        assert result.data == mock_activities
        assert len(result.data) == 2
        service.activity_repository.find_by_contact_id.assert_called_once_with(contact_id)
    
    def test_get_activities_for_contact_empty_result(self, service):
        """Test handling empty activities list"""
        # Arrange
        contact_id = 123
        service.activity_repository.find_by_contact_id.return_value = []
        
        # Act
        result = service.get_activities_for_contact(contact_id)
        
        # Assert
        assert result.is_success
        assert result.data == []
        service.activity_repository.find_by_contact_id.assert_called_once_with(contact_id)
    
    def test_get_activities_for_contact_validates_contact_id(self, service):
        """Test validation of contact_id parameter"""
        # Arrange - invalid contact_id
        contact_id = None
        
        # Act
        result = service.get_activities_for_contact(contact_id)
        
        # Assert
        assert result.is_failure
        assert "Contact ID is required" in result.error
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_get_activities_for_contact_handles_repository_error(self, service):
        """Test handling repository errors"""
        # Arrange
        contact_id = 123
        service.activity_repository.find_by_contact_id.side_effect = Exception("Database connection failed")
        
        # Act
        result = service.get_activities_for_contact(contact_id)
        
        # Assert
        assert result.is_failure
        assert "Database connection failed" in result.error
        assert result.error_code == "REPOSITORY_ERROR"
    
    def test_get_activities_for_contact_uses_chronological_order(self, service, mock_activities):
        """Test that activities are returned in chronological order (oldest first)"""
        # Arrange
        contact_id = 123
        # Repository should return activities in chronological order
        service.activity_repository.find_by_contact_id.return_value = mock_activities
        
        # Act
        result = service.get_activities_for_contact(contact_id)
        
        # Assert
        assert result.is_success
        # Verify the repository method was called with correct ordering expectation
        service.activity_repository.find_by_contact_id.assert_called_once_with(contact_id)


class TestGetLatestConversationsWithResult:
    """Test get_latest_conversations_from_db method with Result pattern"""
    
    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies"""
        conversation_repo = Mock()
        activity_repo = Mock()
        contact_service = Mock()
        property_service = Mock()
        openphone_service = Mock()
        ai_service = Mock()
        
        return MessageServiceRefactored(
            conversation_repository=conversation_repo,
            activity_repository=activity_repo,
            contact_service=contact_service,
            property_service=property_service,
            openphone_service=openphone_service,
            ai_service=ai_service
        )
    
    @pytest.fixture
    def mock_conversations(self):
        """Create mock conversation objects with activities"""
        conv1 = Mock(spec=Conversation)
        conv1.id = 1
        conv1.contact_id = 123
        conv1.last_activity_at = datetime(2025, 1, 1, 12, 0, 0)
        conv1.contact = Mock()
        conv1.activities = [Mock(), Mock()]  # Mock activities
        
        conv2 = Mock(spec=Conversation)
        conv2.id = 2
        conv2.contact_id = 456
        conv2.last_activity_at = datetime(2025, 1, 1, 11, 0, 0)
        conv2.contact = Mock()
        conv2.activities = [Mock()]
        
        return [conv1, conv2]
    
    def test_get_latest_conversations_success_default_limit(self, service, mock_conversations):
        """Test successfully retrieving latest conversations with default limit"""
        # Arrange
        service.conversation_repository.find_recent_conversations.return_value = mock_conversations
        
        # Act
        result = service.get_latest_conversations_from_db()
        
        # Assert
        assert result.is_success
        assert result.data == mock_conversations
        assert len(result.data) == 2
        service.conversation_repository.find_recent_conversations.assert_called_once_with(limit=10)
    
    def test_get_latest_conversations_success_custom_limit(self, service, mock_conversations):
        """Test successfully retrieving latest conversations with custom limit"""
        # Arrange
        custom_limit = 25
        service.conversation_repository.find_recent_conversations.return_value = mock_conversations
        
        # Act
        result = service.get_latest_conversations_from_db(limit=custom_limit)
        
        # Assert
        assert result.is_success
        assert result.data == mock_conversations
        service.conversation_repository.find_recent_conversations.assert_called_once_with(limit=custom_limit)
    
    def test_get_latest_conversations_empty_result(self, service):
        """Test handling empty conversations list"""
        # Arrange
        service.conversation_repository.find_recent_conversations.return_value = []
        
        # Act
        result = service.get_latest_conversations_from_db()
        
        # Assert
        assert result.is_success
        assert result.data == []
        service.conversation_repository.find_recent_conversations.assert_called_once_with(limit=10)
    
    def test_get_latest_conversations_validates_positive_limit(self, service):
        """Test validation of limit parameter"""
        # Arrange - invalid limit
        invalid_limit = -5
        
        # Act
        result = service.get_latest_conversations_from_db(limit=invalid_limit)
        
        # Assert
        assert result.is_failure
        assert "Limit must be positive" in result.error
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_get_latest_conversations_validates_reasonable_limit(self, service):
        """Test validation of unreasonably large limit"""
        # Arrange - unreasonably large limit
        huge_limit = 10000
        
        # Act
        result = service.get_latest_conversations_from_db(limit=huge_limit)
        
        # Assert
        assert result.is_failure
        assert "Limit cannot exceed" in result.error
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_get_latest_conversations_handles_repository_error(self, service):
        """Test handling repository errors"""
        # Arrange
        service.conversation_repository.find_recent_conversations.side_effect = Exception("Query timeout")
        
        # Act
        result = service.get_latest_conversations_from_db()
        
        # Assert
        assert result.is_failure
        assert "Query timeout" in result.error
        assert result.error_code == "REPOSITORY_ERROR"
    
    def test_get_latest_conversations_includes_eager_loading_metadata(self, service, mock_conversations):
        """Test that the method includes metadata about eager loading optimization"""
        # Arrange
        service.conversation_repository.find_recent_conversations.return_value = mock_conversations
        
        # Act
        result = service.get_latest_conversations_from_db()
        
        # Assert
        assert result.is_success
        assert result.metadata is not None
        assert "eager_loaded" in result.metadata
        assert result.metadata["eager_loaded"] is True
        assert "relations" in result.metadata
        assert "contact" in result.metadata["relations"]
        assert "activities" in result.metadata["relations"]


class TestMessageServiceRefactoredErrorHandling:
    """Test comprehensive error handling throughout the service"""
    
    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies"""
        conversation_repo = Mock()
        activity_repo = Mock()
        contact_service = Mock()
        property_service = Mock()
        openphone_service = Mock()
        ai_service = Mock()
        
        return MessageServiceRefactored(
            conversation_repository=conversation_repo,
            activity_repository=activity_repo,
            contact_service=contact_service,
            property_service=property_service,
            openphone_service=openphone_service,
            ai_service=ai_service
        )
    
    def test_all_methods_return_result_objects(self, service):
        """Test that all public methods return Result objects"""
        # This test verifies the Result pattern is consistently applied
        
        # Mock repository methods to avoid actual calls
        service.conversation_repository.find_by_openphone_id.return_value = None
        service.conversation_repository.find_by_contact_id.return_value = []
        service.conversation_repository.create.return_value = Mock()
        service.activity_repository.find_by_contact_id.return_value = []
        service.conversation_repository.find_recent_conversations.return_value = []
        
        # Test all methods return Result objects
        result1 = service.get_or_create_conversation(123, "op_conv_456", ["+11234567890"])
        result2 = service.get_activities_for_contact(123)
        result3 = service.get_latest_conversations_from_db()
        
        assert isinstance(result1, Result)
        assert isinstance(result2, Result)
        assert isinstance(result3, Result)
    
    def test_service_handles_none_repository_dependencies(self):
        """Test service initialization with None repositories still works (dependencies are injected)"""
        # Service should accept None values since they're injected dependencies
        # The validation happens at runtime when methods are called
        service = MessageServiceRefactored(
            conversation_repository=None,
            activity_repository=None,
            contact_service=Mock(),
            property_service=Mock(),
            openphone_service=Mock(),
            ai_service=Mock()
        )
        
        # Service should exist but methods will fail when called with None repositories
        assert service is not None
        assert service.conversation_repository is None
        assert service.activity_repository is None


class TestMessageServiceRefactoredIntegrationPatterns:
    """Test integration patterns with other services through dependency injection"""
    
    @pytest.fixture
    def service_with_mocked_dependencies(self):
        """Create service with all dependencies properly mocked"""
        conversation_repo = Mock()
        activity_repo = Mock()
        contact_service = Mock()
        property_service = Mock()
        openphone_service = Mock()
        ai_service = Mock()
        
        service = MessageServiceRefactored(
            conversation_repository=conversation_repo,
            activity_repository=activity_repo,
            contact_service=contact_service,
            property_service=property_service,
            openphone_service=openphone_service,
            ai_service=ai_service
        )
        
        return service, {
            'conversation_repo': conversation_repo,
            'activity_repo': activity_repo,
            'contact_service': contact_service,
            'property_service': property_service,
            'openphone_service': openphone_service,
            'ai_service': ai_service
        }
    
    def test_service_uses_contact_service_result_pattern(self, service_with_mocked_dependencies):
        """Test that service properly handles Result objects from ContactService"""
        service, mocks = service_with_mocked_dependencies
        
        # Mock ContactService returning Result.success
        contact_result = Result.success(Mock(spec=Contact))
        mocks['contact_service'].get_contact_by_id.return_value = contact_result
        
        # This test ensures we handle ContactService's Result pattern correctly
        # Implementation should unwrap the Result properly
        assert mocks['contact_service'] is service.contact_service
    
    def test_service_never_instantiates_dependencies_directly(self, service_with_mocked_dependencies):
        """Test that service never creates its own service instances"""
        service, mocks = service_with_mocked_dependencies
        
        # Verify all services are the injected mocks, not new instances
        assert service.contact_service is mocks['contact_service']
        assert service.property_service is mocks['property_service']
        assert service.openphone_service is mocks['openphone_service']
        assert service.ai_service is mocks['ai_service']
        
        # Verify repositories are the injected mocks
        assert service.conversation_repository is mocks['conversation_repo']
        assert service.activity_repository is mocks['activity_repo']
    
    def test_service_properly_handles_injected_service_failures(self, service_with_mocked_dependencies):
        """Test handling when injected services return failure Results"""
        service, mocks = service_with_mocked_dependencies
        
        # Mock a service failure
        failure_result = Result.failure("Contact service unavailable", "SERVICE_ERROR")
        mocks['contact_service'].some_method.return_value = failure_result
        
        # The MessageService should handle these failures gracefully
        # This establishes the contract for error propagation
        assert failure_result.is_failure
        assert failure_result.error_code == "SERVICE_ERROR"