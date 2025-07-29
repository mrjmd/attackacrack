# tests/test_quote_service.py
"""
Tests for the QuoteService, ensuring that creating, updating, and deleting
quotes and their line items works correctly.
"""

import pytest
from services.quote_service import QuoteService
from crm_database import Quote, QuoteLineItem, Job

def test_create_quote_with_line_items(app, db_session):
    """
    GIVEN valid quote data with line items
    WHEN the create_quote method is called
    THEN it should create a new Quote and associated QuoteLineItem records,
    AND the quote's total amount should be calculated correctly.
    """
    # 1. Setup
    quote_service = QuoteService()
    job = db_session.get(Job, 1) # Get the seeded job
    assert job is not None

    quote_data = {
        "job_id": job.id,
        "status": "Draft",
        "line_items": [
            {"description": "Crack Repair", "quantity": 1, "price": 500.00},
            {"description": "Waterproofing", "quantity": 1, "price": 1200.50}
        ]
    }

    # 2. Execution
    new_quote = quote_service.create_quote(quote_data)

    # 3. Assertions
    assert new_quote is not None
    assert new_quote.id is not None
    assert new_quote.status == "Draft"
    
    # Check that the line items were created
    assert len(new_quote.line_items) == 2
    assert new_quote.line_items[0].description == "Crack Repair"
    
    # Check that the total amount was calculated correctly
    assert new_quote.amount == 1700.50

def test_create_quote_error_handling(app, db_session):
    """
    GIVEN invalid quote data (missing required fields)
    WHEN create_quote is called
    THEN it should handle errors gracefully and return None
    """
    quote_service = QuoteService()
    
    # Test with missing job_id
    invalid_data = {
        "status": "Draft",
        "line_items": [{"description": "Test", "quantity": 1, "price": 100}]
    }
    
    result = quote_service.create_quote(invalid_data)
    assert result is None

def test_create_quote_with_zero_line_items(app, db_session):
    """
    GIVEN quote data with no line items
    WHEN create_quote is called  
    THEN it should create a quote with 0 amount
    """
    quote_service = QuoteService()
    job = db_session.get(Job, 1)
    
    quote_data = {
        "job_id": job.id,
        "status": "Draft"
        # No line_items
    }
    
    new_quote = quote_service.create_quote(quote_data)
    assert new_quote is not None
    assert new_quote.amount == 0
    assert len(new_quote.line_items) == 0

def test_update_quote_success(app, db_session):
    """
    GIVEN an existing quote
    WHEN update_quote is called with new data
    THEN it should update the quote and recalculate amount
    """
    quote_service = QuoteService()
    job = db_session.get(Job, 1)
    
    # First create a quote
    initial_data = {
        "job_id": job.id,
        "status": "Draft",
        "line_items": [{"description": "Initial", "quantity": 1, "price": 100}]
    }
    quote = quote_service.create_quote(initial_data)
    
    # Now update it
    update_data = {
        "status": "Sent",
        "line_items": [
            {"description": "Updated Item 1", "quantity": 2, "price": 150},
            {"description": "New Item 2", "quantity": 1, "price": 200}
        ]
    }
    
    updated_quote = quote_service.update_quote(quote.id, update_data)
    assert updated_quote is not None
    assert updated_quote.status == "Sent"
    assert updated_quote.amount == 500.0  # (2 * 150) + (1 * 200)
    assert len(updated_quote.line_items) == 2

def test_update_quote_not_found(app, db_session):
    """
    GIVEN a non-existent quote ID
    WHEN update_quote is called
    THEN it should return None
    """
    quote_service = QuoteService()
    result = quote_service.update_quote(99999, {"status": "Sent"})
    assert result is None

def test_delete_quote_success(app, db_session):
    """
    GIVEN an existing quote with line items
    WHEN delete_quote is called
    THEN it should delete the quote and cascade delete line items
    """
    quote_service = QuoteService()
    job = db_session.get(Job, 1)
    
    # Create a quote with line items
    quote_data = {
        "job_id": job.id,
        "status": "Draft",
        "line_items": [{"description": "Test", "quantity": 1, "price": 100}]
    }
    quote = quote_service.create_quote(quote_data)
    quote_id = quote.id
    
    # Delete the quote
    result = quote_service.delete_quote(quote_id)
    assert result is not None  # Returns the deleted quote object
    
    # Verify it's gone
    deleted_quote = quote_service.get_quote_by_id(quote_id)
    assert deleted_quote is None

def test_delete_quote_not_found(app, db_session):
    """
    GIVEN a non-existent quote ID
    WHEN delete_quote is called
    THEN it should return False
    """
    quote_service = QuoteService()
    result = quote_service.delete_quote(99999)
    assert result is None  # Returns None for non-existent quote

def test_get_all_quotes_ordering(app, db_session):
    """
    GIVEN multiple quotes in the database
    WHEN get_all_quotes is called
    THEN it should return quotes ordered by ID descending (newest first)
    """
    quote_service = QuoteService()
    job = db_session.get(Job, 1)
    
    # Create multiple quotes
    for i in range(3):
        quote_data = {
            "job_id": job.id,
            "status": f"Quote {i}",
            "line_items": [{"description": f"Item {i}", "quantity": 1, "price": 100 + i}]
        }
        quote_service.create_quote(quote_data)
    
    quotes = quote_service.get_all_quotes()
    assert len(quotes) >= 3
    
    # Check ordering (newest first)
    for i in range(len(quotes) - 1):
        assert quotes[i].id >= quotes[i + 1].id

def test_calculate_line_item_totals(app, db_session):
    """
    GIVEN quote data with various line item quantities and prices
    WHEN create_quote is called
    THEN it should correctly calculate total amounts including decimals
    """
    quote_service = QuoteService()
    job = db_session.get(Job, 1)
    
    quote_data = {
        "job_id": job.id,
        "status": "Draft",
        "line_items": [
            {"description": "Fractional", "quantity": 2.5, "price": 100.25},
            {"description": "Zero quantity", "quantity": 0, "price": 500},
            {"description": "Zero price", "quantity": 10, "price": 0},
            {"description": "Normal", "quantity": 1, "price": 199.99}
        ]
    }
    
    quote = quote_service.create_quote(quote_data)
    expected_total = (2.5 * 100.25) + (0 * 500) + (10 * 0) + (1 * 199.99)
    assert abs(quote.amount - expected_total) < 0.01  # Handle floating point precision
