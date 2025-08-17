# tests/test_ai_service_comprehensive.py
"""
Comprehensive tests for AI Service covering all functionality including error handling,
edge cases, and integration scenarios.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.ai_service import AIService
from crm_database import Contact, Conversation, Activity
from datetime import datetime
import json


@pytest.fixture
def ai_service():
    """Fixture to provide AIService instance"""
    return AIService()


@pytest.fixture
def mock_activities():
    """Fixture providing mock activity objects for testing"""
    activities = [
        MagicMock(direction="incoming", body="I have a crack in my foundation that's getting worse."),
        MagicMock(direction="outgoing", body="I can help with that. Can you send pictures?"),
        MagicMock(direction="incoming", body="Yes, I'll send them now.")
    ]
    return activities


class TestAISummarization:
    """Test AI summarization functionality"""
    
    @patch('services.ai_service.genai')
    def test_summarize_conversation_success(self, mock_genai, ai_service, mock_activities, app):
        """Test successful conversation summarization"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            # Mock the AI response
            mock_response = MagicMock()
            mock_response.text = "Customer has foundation crack issue. Requested photos for assessment."
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = ai_service.summarize_conversation_for_appointment(mock_activities)
            
            assert result is not None
            assert "foundation crack" in result.lower()
            mock_genai.configure.assert_called_once_with(api_key='test_key')
            mock_model.generate_content.assert_called_once()
    
    @patch('services.ai_service.genai')
    def test_summarize_conversation_api_error(self, mock_genai, ai_service, mock_activities, app):
        """Test handling of AI API errors"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = ai_service.summarize_conversation_for_appointment(mock_activities)
            assert result == "Could not generate summary."
    
    def test_summarize_conversation_no_activities(self, ai_service):
        """Test summarization with no conversation activities"""
        result = ai_service.summarize_conversation_for_appointment([])
        assert result == ""
    
    def test_summarize_conversation_missing_api_key(self, ai_service, app):
        """Test behavior when API key is missing"""
        with app.app_context():
            # Don't set GEMINI_API_KEY in config
            result = ai_service.summarize_conversation_for_appointment([MagicMock()])
            assert result == "Could not generate summary."


class TestAIConfiguration:
    """Test AI service configuration and initialization"""
    
    def test_ai_service_initialization(self, ai_service):
        """Test that AI service initializes correctly"""
        assert ai_service is not None
        assert ai_service.model is None  # Model should be None until first use
    
    def test_configure_model_success(self, ai_service, app):
        """Test successful model configuration"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            with patch('services.ai_service.genai') as mock_genai:
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model
                
                ai_service._configure_model()
                
                assert ai_service.model is not None
                mock_genai.configure.assert_called_once_with(api_key='test_key')
                mock_genai.GenerativeModel.assert_called_once_with('gemini-1.5-flash')
    
    def test_configure_model_missing_api_key(self, ai_service, app):
        """Test model configuration with missing API key"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = None  # Explicitly set to None
            ai_service._configure_model()
            assert ai_service.model is False


class TestAddressExtraction:
    """Test AI address extraction functionality"""
    
    @patch('services.ai_service.genai')
    def test_extract_address_success(self, mock_genai, ai_service, app):
        """Test successful address extraction"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_response = MagicMock()
            mock_response.text = "123 Beacon St, Boston, MA 02116"
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = ai_service.extract_address_from_text("I need a quote for 123 Beacon St in Boston")
            
            assert result == "123 Beacon St, Boston, MA 02116"
            mock_model.generate_content.assert_called_once()
    
    @patch('services.ai_service.genai')
    def test_extract_address_none_found(self, mock_genai, ai_service, app):
        """Test address extraction when no address is found"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_response = MagicMock()
            mock_response.text = "None"
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = ai_service.extract_address_from_text("Can you call me later?")
            
            assert result is None
    
    def test_extract_address_no_text(self, ai_service):
        """Test address extraction with empty text"""
        result = ai_service.extract_address_from_text("")
        assert result is None
        
        result = ai_service.extract_address_from_text(None)
        assert result is None


class TestNameExtraction:
    """Test AI name extraction functionality"""
    
    @patch('services.ai_service.genai')
    def test_extract_name_success(self, mock_genai, ai_service, app):
        """Test successful name extraction"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_response = MagicMock()
            mock_response.text = '{"first_name": "John", "last_name": "Doe"}'
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            first_name, last_name = ai_service.extract_name_from_text("Hi, my name is John Doe")
            
            assert first_name == "John"
            assert last_name == "Doe"
    
    @patch('services.ai_service.genai')
    def test_extract_name_first_only(self, mock_genai, ai_service, app):
        """Test name extraction with first name only"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_response = MagicMock()
            mock_response.text = '{"first_name": "Jane", "last_name": null}'
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            first_name, last_name = ai_service.extract_name_from_text("This is Jane")
            
            assert first_name == "Jane"
            assert last_name is None
    
    @patch('services.ai_service.genai')
    def test_extract_name_api_error(self, mock_genai, ai_service, app):
        """Test name extraction with API error"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_genai.GenerativeModel.return_value = mock_model
            
            first_name, last_name = ai_service.extract_name_from_text("My name is John")
            
            assert first_name is None
            assert last_name is None


class TestAIErrorHandling:
    """Test AI service error handling and resilience"""
    
    @patch('services.ai_service.genai')  
    def test_extract_address_api_error(self, mock_genai, ai_service, app):
        """Test address extraction with API error"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = ai_service.extract_address_from_text("123 Main St")
            assert result is None
    
    def test_extract_address_no_api_key(self, ai_service, app):
        """Test address extraction without API key"""
        with app.app_context():
            # Don't set GEMINI_API_KEY
            result = ai_service.extract_address_from_text("123 Main St")
            assert result is None
    
    @patch('services.ai_service.genai')
    def test_extract_name_invalid_json(self, mock_genai, ai_service, app):
        """Test name extraction with invalid JSON response"""
        with app.app_context():
            app.config['GEMINI_API_KEY'] = 'test_key'
            
            mock_response = MagicMock()
            mock_response.text = "Invalid JSON response"
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            first_name, last_name = ai_service.extract_name_from_text("My name is John")
            
            assert first_name is None
            assert last_name is None