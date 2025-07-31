"""
Fixed tests for Quote Service
"""
import pytest
from datetime import datetime, timedelta
from services.quote_service import QuoteService
from crm_database import db, Quote


class TestQuoteServiceFixed:
    """Fixed test cases for Quote service"""
    
    @pytest.fixture
    def quote_service(self, app):
        """Create a quote service instance"""
        with app.app_context():
            service = QuoteService()
            yield service
    
    def test_get_all_quotes(self, quote_service, app):
        """Test getting all quotes"""
        with app.app_context():
            # Create test quotes
            quote1 = Quote(
                job_id=1,
                subtotal=1000,
                tax_amount=100,
                total_amount=1100,
                valid_until=datetime.utcnow().date() + timedelta(days=30),
                status='Pending'
            )
            quote2 = Quote(
                job_id=2,
                subtotal=2000,
                tax_amount=200,
                total_amount=2200,
                valid_until=datetime.utcnow().date() + timedelta(days=30),
                status='Accepted'
            )
            db.session.add_all([quote1, quote2])
            db.session.commit()
            
            # Get all quotes
            quotes = quote_service.get_all_quotes()
            assert len(quotes) >= 2  # May include seeded data
            
            # Clean up
            db.session.delete(quote1)
            db.session.delete(quote2)
            db.session.commit()
    
    def test_get_quote_by_id(self, quote_service, app):
        """Test getting quote by ID"""
        with app.app_context():
            # Create test quote
            quote = Quote(
                job_id=1,
                subtotal=1500,
                tax_amount=150,
                total_amount=1650,
                valid_until=datetime.utcnow().date() + timedelta(days=30),
                status='Draft'
            )
            db.session.add(quote)
            db.session.commit()
            
            # Get by ID
            result = quote_service.get_quote_by_id(quote.id)
            assert result is not None
            assert result.id == quote.id
            assert result.subtotal == 1500
            
            # Test non-existent ID
            result = quote_service.get_quote_by_id(99999)
            assert result is None
            
            # Clean up
            db.session.delete(quote)
            db.session.commit()
    
    def test_create_quote(self, quote_service, app):
        """Test creating a quote"""
        with app.app_context():
            data = {
                'job_id': 1,
                'subtotal': 3000,
                'tax_amount': 300,
                'total_amount': 3300,
                'valid_until': (datetime.utcnow() + timedelta(days=15)).date().isoformat(),
                'status': 'Pending'
            }
            
            quote = quote_service.create_quote(data)
            assert quote is not None
            assert quote.subtotal == 3000
            assert quote.status == 'Pending'
            
            # Clean up
            db.session.delete(quote)
            db.session.commit()
    
    def test_update_quote(self, quote_service, app):
        """Test updating a quote"""
        with app.app_context():
            # Create test quote
            quote = Quote(
                job_id=1,
                subtotal=1000,
                tax_amount=100,
                total_amount=1100,
                valid_until=datetime.utcnow().date() + timedelta(days=30),
                status='Draft'
            )
            db.session.add(quote)
            db.session.commit()
            
            # Update quote
            update_data = {
                'subtotal': 1500,
                'tax_amount': 150,
                'total_amount': 1650,
                'status': 'Sent'
            }
            
            updated = quote_service.update_quote(quote.id, update_data)
            assert updated is not None
            assert updated.subtotal == 1500
            assert updated.status == 'Sent'
            
            # Test non-existent ID
            result = quote_service.update_quote(99999, update_data)
            assert result is None
            
            # Clean up
            db.session.delete(quote)
            db.session.commit()
    
    def test_delete_quote(self, quote_service, app):
        """Test deleting a quote"""
        with app.app_context():
            # Create test quote
            quote = Quote(
                job_id=1,
                subtotal=500,
                tax_amount=50,
                total_amount=550,
                valid_until=datetime.utcnow().date() + timedelta(days=30),
                status='Draft'
            )
            db.session.add(quote)
            db.session.commit()
            quote_id = quote.id
            
            # Delete quote
            result = quote_service.delete_quote(quote_id)
            assert result is not None
            assert result.id == quote_id
            
            # Verify it's deleted
            deleted = Quote.query.get(quote_id)
            assert deleted is None
            
            # Test deleting non-existent quote
            result = quote_service.delete_quote(99999)
            assert result is None
    
    def test_expire_old_quotes(self, quote_service, app):
        """Test expiring old quotes"""
        with app.app_context():
            # Create quotes with different expiry dates
            old_quote = Quote(
                job_id=1,
                subtotal=1000,
                tax_amount=100,
                total_amount=1100,
                valid_until=datetime.utcnow().date() - timedelta(days=1),  # Expired
                status='Pending'
            )
            new_quote = Quote(
                job_id=2,
                subtotal=2000,
                tax_amount=200,
                total_amount=2200,
                valid_until=datetime.utcnow().date() + timedelta(days=30),  # Not expired
                status='Pending'
            )
            db.session.add_all([old_quote, new_quote])
            db.session.commit()
            
            # Expire old quotes
            count = quote_service.expire_old_quotes()
            assert count >= 1
            
            # Check statuses
            db.session.refresh(old_quote)
            db.session.refresh(new_quote)
            assert old_quote.status == 'Expired'
            assert new_quote.status == 'Pending'
            
            # Clean up
            db.session.delete(old_quote)
            db.session.delete(new_quote)
            db.session.commit()