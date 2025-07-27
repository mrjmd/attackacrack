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

# TODO: Add a test for updating a quote (e.g., adding/removing line items).
# TODO: Add a test for deleting a quote, ensuring its line items are also deleted.
# TODO: Add a test for creating a quote with a pre-defined ProductService item.
