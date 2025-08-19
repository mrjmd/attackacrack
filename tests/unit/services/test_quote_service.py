# tests/unit/services/test_quote_service.py
"""
Tests for the QuoteService using repository mocks.
Ensures that creating, updating, and deleting quotes and their line items works correctly.
"""

import pytest
from services.quote_service import QuoteService
from services.common.result import Result
from tests.fixtures.repository_fixtures import (
    create_quote_repository_mock, 
    create_quote_line_item_repository_mock
)


@pytest.fixture
def quote_repository():
    """Create a mock quote repository with in-memory storage."""
    return create_quote_repository_mock(with_data=True)


@pytest.fixture
def line_item_repository():
    """Create a mock line item repository with in-memory storage."""
    return create_quote_line_item_repository_mock(with_data=True)


@pytest.fixture
def quote_service(quote_repository, line_item_repository):
    """Create QuoteService with mocked repositories."""
    return QuoteService(
        quote_repository=quote_repository,
        line_item_repository=line_item_repository
    )


@pytest.fixture
def sample_job_id():
    """Sample job ID for testing."""
    return 1


@pytest.fixture
def sample_quote_data(sample_job_id):
    """Sample quote data for testing."""
    return {
        "job_id": sample_job_id,
        "status": "Draft",
        "line_items": [
            {"description": "Crack Repair", "quantity": 1, "price": 500.00},
            {"description": "Waterproofing", "quantity": 1, "price": 1200.50}
        ]
    }


class TestQuoteServiceCreate:
    """Test quote creation functionality."""

    def test_create_quote_with_line_items(self, quote_service, sample_quote_data):
        """
        GIVEN valid quote data with line items
        WHEN the create_quote method is called
        THEN it should create a new Quote and associated QuoteLineItem records,
        AND the quote's total amount should be calculated correctly.
        """
        # Act
        result = quote_service.create_quote(sample_quote_data)

        # Assert
        assert result.is_success
        quote = result.data
        assert quote is not None
        assert quote['id'] is not None
        assert quote['status'] == "Draft"
        assert quote['job_id'] == sample_quote_data['job_id']
        
        # Check that the total amount was calculated correctly
        # 1 * 500.00 + 1 * 1200.50 = 1700.50
        assert quote['total_amount'] == 1700.50
        assert quote['subtotal'] == 1700.50

    def test_create_quote_error_handling(self, quote_service):
        """
        GIVEN invalid quote data (missing required fields)
        WHEN create_quote is called
        THEN it should return a failure result
        """        
        # Test with missing job_id
        invalid_data = {
            "status": "Draft",
            "line_items": [{"description": "Test", "quantity": 1, "price": 100}]
        }
        
        result = quote_service.create_quote(invalid_data)
        assert result.is_failure
        assert "job_id" in result.error

    def test_create_quote_with_zero_line_items(self, quote_service, sample_job_id):
        """
        GIVEN quote data with no line items
        WHEN create_quote is called  
        THEN it should create a quote with 0 amount
        """
        quote_data = {
            "job_id": sample_job_id,
            "status": "Draft"
            # No line_items
        }
        
        result = quote_service.create_quote(quote_data)
        assert result.is_success
        quote = result.data
        assert quote is not None
        assert quote['total_amount'] == 0
        assert quote['subtotal'] == 0

    def test_calculate_line_item_totals(self, quote_service, sample_job_id):
        """
        GIVEN quote data with various line item quantities and prices
        WHEN create_quote is called
        THEN it should correctly calculate total amounts including decimals
        """
        quote_data = {
            "job_id": sample_job_id,
            "status": "Draft",
            "line_items": [
                {"description": "Fractional", "quantity": 2.5, "price": 100.25},
                {"description": "Zero quantity", "quantity": 0, "price": 500},
                {"description": "Zero price", "quantity": 10, "price": 0},
                {"description": "Normal", "quantity": 1, "price": 199.99}
            ]
        }
        
        result = quote_service.create_quote(quote_data)
        assert result.is_success
        quote = result.data
        
        expected_total = (2.5 * 100.25) + (0 * 500) + (10 * 0) + (1 * 199.99)
        assert abs(float(quote['total_amount']) - expected_total) < 0.01  # Handle floating point precision


class TestQuoteServiceUpdate:
    """Test quote update functionality."""

    def test_update_quote_success(self, quote_service, sample_quote_data, quote_repository, line_item_repository):
        """
        GIVEN an existing quote
        WHEN update_quote is called with new data
        THEN it should update the quote and recalculate amount
        """
        # First create a quote
        create_result = quote_service.create_quote(sample_quote_data)
        assert create_result.is_success
        quote = create_result.data
        quote_id = quote['id']
        
        # Create some line items for the quote
        line_item_repository.bulk_create_line_items(quote_id, [
            {"description": "Initial", "quantity": 1, "price": 100}
        ])
        
        # Now update it
        update_data = {
            "status": "Sent",
            "line_items": [
                {"description": "Updated Item 1", "quantity": 2, "price": 150},
                {"description": "New Item 2", "quantity": 1, "price": 200}
            ]
        }
        
        result = quote_service.update_quote(quote_id, update_data)
        assert result.is_success
        updated_quote = result.data
        assert updated_quote is not None
        assert updated_quote['status'] == "Sent"
        assert updated_quote['total_amount'] == 500.0  # (2 * 150) + (1 * 200)

    def test_update_quote_not_found(self, quote_service):
        """
        GIVEN a non-existent quote ID
        WHEN update_quote is called
        THEN it should return a failure result
        """
        result = quote_service.update_quote(99999, {"status": "Sent"})
        assert result.is_failure
        assert "not found" in result.error


class TestQuoteServiceDelete:
    """Test quote deletion functionality."""

    def test_delete_quote_success(self, quote_service, sample_quote_data, line_item_repository):
        """
        GIVEN an existing quote with line items
        WHEN delete_quote is called
        THEN it should delete the quote and cascade delete line items
        """
        # Create a quote with line items
        create_result = quote_service.create_quote(sample_quote_data)
        assert create_result.is_success
        quote = create_result.data
        quote_id = quote['id']
        
        # Add line items
        line_item_repository.bulk_create_line_items(quote_id, [
            {"description": "Test", "quantity": 1, "price": 100}
        ])
        
        # Delete the quote
        result = quote_service.delete_quote(quote_id)
        assert result.is_success
        deleted_quote = result.data
        assert deleted_quote is not None
        assert deleted_quote['id'] == quote_id
        
        # Verify it's gone
        get_result = quote_service.get_quote_by_id(quote_id)
        assert get_result is None

    def test_delete_quote_not_found(self, quote_service):
        """
        GIVEN a non-existent quote ID
        WHEN delete_quote is called
        THEN it should return a failure result
        """
        result = quote_service.delete_quote(99999)
        assert result.is_failure
        assert "not found" in result.error


class TestQuoteServiceQuery:
    """Test quote query functionality."""

    def test_get_all_quotes_ordering(self, quote_service, sample_job_id, quote_repository):
        """
        GIVEN multiple quotes in the repository
        WHEN get_all_quotes is called
        THEN it should return quotes ordered by ID descending (newest first)
        """
        # Create multiple quotes directly in repository
        quotes_data = []
        for i in range(3):
            quote_data = {
                "job_id": sample_job_id,
                "status": f"Quote {i}",
                "total_amount": 100 + i,
                "subtotal": 100 + i,
                "tax_amount": 0
            }
            quote = quote_repository.create(**quote_data)
            quotes_data.append(quote)
        
        quotes = quote_service.get_all_quotes()
        assert len(quotes) >= 3
        
        # Check ordering (newest first - highest ID first)
        for i in range(len(quotes) - 1):
            assert quotes[i]['id'] >= quotes[i + 1]['id']

    def test_get_quote_by_id_success(self, quote_service, sample_quote_data):
        """
        GIVEN an existing quote ID
        WHEN get_quote_by_id is called
        THEN it should return the quote
        """
        # Create a quote
        create_result = quote_service.create_quote(sample_quote_data)
        assert create_result.is_success
        quote = create_result.data
        quote_id = quote['id']
        
        # Retrieve it
        retrieved_quote = quote_service.get_quote_by_id(quote_id)
        assert retrieved_quote is not None
        assert retrieved_quote['id'] == quote_id
        assert retrieved_quote['status'] == "Draft"

    def test_get_quote_by_id_not_found(self, quote_service):
        """
        GIVEN a non-existent quote ID
        WHEN get_quote_by_id is called
        THEN it should return None
        """
        retrieved_quote = quote_service.get_quote_by_id(99999)
        assert retrieved_quote is None