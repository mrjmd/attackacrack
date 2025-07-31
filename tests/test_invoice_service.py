"""
Tests for Invoice Service
"""
import pytest
from datetime import date, datetime, timedelta
from services.invoice_service import InvoiceService  
from crm_database import db, Invoice, InvoiceLineItem, Job, Quote, Product


class TestInvoiceService:
    """Test cases for Invoice service"""
    
    @pytest.fixture
    def invoice_service(self, app):
        """Create an invoice service instance"""
        with app.app_context():
            service = InvoiceService()
            yield service
            # Clean up
            InvoiceLineItem.query.delete()
            Invoice.query.filter(Invoice.id > 1).delete()  # Keep seeded invoice
            db.session.commit()
    
    @pytest.fixture
    def sample_job(self, app):
        """Get the seeded job"""
        with app.app_context():
            return db.session.get(Job, 1)
    
    @pytest.fixture
    def sample_products(self, app):
        """Create sample products"""
        with app.app_context():
            products = [
                Product(
                    name='Service A',
                    description='Basic service',
                    unit_price=100.00,
                    product_type='Service'
                ),
                Product(
                    name='Product B', 
                    description='Physical product',
                    unit_price=50.00,
                    product_type='Product'
                )
            ]
            db.session.add_all(products)
            db.session.commit()
            return products
    
    def test_get_all_invoices(self, invoice_service, app):
        """Test getting all invoices"""
        with app.app_context():
            invoices = invoice_service.get_all_invoices()
            # Should have the seeded invoice
            assert len(invoices) >= 1
            assert invoices[0].id == 1
    
    def test_get_invoice_by_id_exists(self, invoice_service, app):
        """Test getting invoice by ID when it exists"""
        with app.app_context():
            invoice = invoice_service.get_invoice_by_id(1)
            assert invoice is not None
            assert invoice.id == 1
    
    def test_get_invoice_by_id_not_exists(self, invoice_service, app):
        """Test getting invoice by ID when it doesn't exist"""
        with app.app_context():
            invoice = invoice_service.get_invoice_by_id(99999)
            assert invoice is None
    
    def test_create_invoice_basic(self, invoice_service, sample_job, app):
        """Test creating a basic invoice"""
        with app.app_context():
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'status': 'Draft'
            }
            
            invoice = invoice_service.create_invoice(invoice_data)
            
            assert invoice is not None
            assert invoice.job_id == sample_job.id
            assert invoice.status == 'Draft'
            assert invoice.subtotal == 0
            assert invoice.total_amount == 0
    
    def test_create_invoice_with_line_items(self, invoice_service, sample_job, sample_products, app):
        """Test creating invoice with line items"""
        with app.app_context():
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'line_items': [
                    {
                        'product_id': sample_products[0].id,
                        'description': 'Service A work',
                        'quantity': 2,
                        'unit_price': 100.00
                    },
                    {
                        'description': 'Custom work',
                        'quantity': 1,
                        'unit_price': 150.00
                    }
                ]
            }
            
            invoice = invoice_service.create_invoice(invoice_data)
            
            assert invoice is not None
            assert len(invoice.line_items) == 2
            assert invoice.subtotal == 350.00  # (2 * 100) + (1 * 150)
            assert invoice.total_amount == 350.00  # No tax
            
            # Check line items
            assert invoice.line_items[0].product_id == sample_products[0].id
            assert invoice.line_items[0].line_total == 200.00
            assert invoice.line_items[1].product_id is None
            assert invoice.line_items[1].line_total == 150.00
    
    def test_create_invoice_with_tax(self, invoice_service, sample_job, app):
        """Test creating invoice with tax"""
        with app.app_context():
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'tax_amount': 20.00,
                'line_items': [
                    {
                        'description': 'Service',
                        'quantity': 1,
                        'unit_price': 200.00
                    }
                ]
            }
            
            invoice = invoice_service.create_invoice(invoice_data)
            
            assert invoice.subtotal == 200.00
            assert invoice.tax_amount == 20.00
            assert invoice.total_amount == 220.00
    
    def test_create_invoice_from_quote(self, invoice_service, sample_job, app):
        """Test creating invoice from a quote"""
        with app.app_context():
            # Get the seeded quote
            quote = db.session.get(Quote, 1)
            
            invoice_data = {
                'job_id': sample_job.id,
                'quote_id': quote.id,
                'due_date': date.today() + timedelta(days=30)
            }
            
            invoice = invoice_service.create_invoice(invoice_data)
            
            assert invoice is not None
            assert invoice.quote_id == quote.id
    
    def test_update_invoice_basic_fields(self, invoice_service, app):
        """Test updating basic invoice fields"""
        with app.app_context():
            # Get seeded invoice
            invoice = db.session.get(Invoice, 1)
            original_due_date = invoice.due_date
            
            update_data = {
                'status': 'Sent',
                'due_date': original_due_date + timedelta(days=15)
            }
            
            updated = invoice_service.update_invoice(1, update_data)
            
            assert updated is not None
            assert updated.status == 'Sent'
            assert updated.due_date == original_due_date + timedelta(days=15)
    
    def test_update_invoice_line_items(self, invoice_service, sample_job, app):
        """Test updating invoice line items"""
        with app.app_context():
            # Create invoice with line items
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'line_items': [
                    {'description': 'Item 1', 'quantity': 1, 'unit_price': 100.00}
                ]
            }
            invoice = invoice_service.create_invoice(invoice_data)
            line_item_id = invoice.line_items[0].id
            
            # Update with modified line items
            update_data = {
                'line_items': [
                    {
                        'id': line_item_id,
                        'description': 'Updated Item 1',
                        'quantity': 2,
                        'unit_price': 100.00
                    },
                    {
                        'description': 'New Item 2',
                        'quantity': 1,
                        'unit_price': 50.00
                    }
                ]
            }
            
            updated = invoice_service.update_invoice(invoice.id, update_data)
            
            assert len(updated.line_items) == 2
            assert updated.line_items[0].description == 'Updated Item 1'
            assert updated.line_items[0].line_total == 200.00
            assert updated.subtotal == 250.00
    
    def test_update_invoice_remove_line_items(self, invoice_service, sample_job, app):
        """Test removing line items from invoice"""
        with app.app_context():
            # Create invoice with multiple line items
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'line_items': [
                    {'description': 'Item 1', 'quantity': 1, 'unit_price': 100.00},
                    {'description': 'Item 2', 'quantity': 1, 'unit_price': 50.00}
                ]
            }
            invoice = invoice_service.create_invoice(invoice_data)
            
            # Update with only first item
            update_data = {
                'line_items': [
                    {
                        'id': invoice.line_items[0].id,
                        'description': 'Item 1',
                        'quantity': 1,
                        'unit_price': 100.00
                    }
                ]
            }
            
            updated = invoice_service.update_invoice(invoice.id, update_data)
            
            assert len(updated.line_items) == 1
            assert updated.subtotal == 100.00
    
    def test_update_nonexistent_invoice(self, invoice_service, app):
        """Test updating non-existent invoice"""
        with app.app_context():
            result = invoice_service.update_invoice(99999, {'status': 'Paid'})
            assert result is None
    
    def test_delete_invoice_success(self, invoice_service, sample_job, app):
        """Test deleting an invoice"""
        with app.app_context():
            # Create invoice to delete
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30)
            }
            invoice = invoice_service.create_invoice(invoice_data)
            invoice_id = invoice.id
            
            result = invoice_service.delete_invoice(invoice_id)
            
            assert result is True
            
            # Verify deleted
            deleted = Invoice.query.get(invoice_id)
            assert deleted is None
    
    def test_delete_invoice_with_line_items(self, invoice_service, sample_job, app):
        """Test deleting invoice cascades to line items"""
        with app.app_context():
            # Create invoice with line items
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'line_items': [
                    {'description': 'Item', 'quantity': 1, 'unit_price': 100.00}
                ]
            }
            invoice = invoice_service.create_invoice(invoice_data)
            invoice_id = invoice.id
            
            # Delete invoice
            invoice_service.delete_invoice(invoice_id)
            
            # Verify line items also deleted
            line_items = InvoiceLineItem.query.filter_by(invoice_id=invoice_id).all()
            assert len(line_items) == 0
    
    def test_delete_nonexistent_invoice(self, invoice_service, app):
        """Test deleting non-existent invoice"""
        with app.app_context():
            result = invoice_service.delete_invoice(99999)
            assert result is False
    
    def test_calculate_invoice_totals(self, invoice_service, sample_job, app):
        """Test invoice total calculations"""
        with app.app_context():
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'tax_amount': 25.00,
                'line_items': [
                    {'description': 'Item 1', 'quantity': 2, 'unit_price': 100.00},
                    {'description': 'Item 2', 'quantity': 1, 'unit_price': 50.00}
                ]
            }
            
            invoice = invoice_service.create_invoice(invoice_data)
            
            # Refresh to ensure calculations
            invoice_service._calculate_invoice_totals(invoice)
            
            assert invoice.subtotal == 250.00  # (2*100) + (1*50)
            assert invoice.tax_amount == 25.00
            assert invoice.total_amount == 275.00
            assert invoice.balance_due == 275.00  # No payments
    
    def test_record_payment(self, invoice_service, sample_job, app):
        """Test recording payment on invoice"""
        with app.app_context():
            # Create invoice
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'line_items': [
                    {'description': 'Service', 'quantity': 1, 'unit_price': 1000.00}
                ]
            }
            invoice = invoice_service.create_invoice(invoice_data)
            
            # Record partial payment
            invoice.amount_paid = 400.00
            invoice_service._calculate_invoice_totals(invoice)
            
            assert invoice.balance_due == 600.00
            assert invoice.payment_status == 'partial'
            
            # Record full payment
            invoice.amount_paid = 1000.00
            invoice_service._calculate_invoice_totals(invoice)
            
            assert invoice.balance_due == 0.00
            assert invoice.payment_status == 'paid'
            assert invoice.paid_date is not None
    
    def test_invoice_overdue_status(self, invoice_service, sample_job, app):
        """Test invoice overdue status calculation"""
        with app.app_context():
            # Create past due invoice
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() - timedelta(days=5),  # 5 days overdue
                'line_items': [
                    {'description': 'Service', 'quantity': 1, 'unit_price': 100.00}
                ]
            }
            invoice = invoice_service.create_invoice(invoice_data)
            
            # Update status
            invoice_service._calculate_invoice_totals(invoice)
            
            # Should be marked as overdue
            assert invoice.payment_status == 'overdue'
            assert invoice.balance_due == 100.00
    
    def test_create_invoice_error_handling(self, invoice_service, app):
        """Test invoice creation error handling"""
        with app.app_context():
            # Missing required field
            result = invoice_service.create_invoice({})
            assert result is None
            
            # Invalid job ID
            result = invoice_service.create_invoice({
                'job_id': 99999,
                'due_date': date.today()
            })
            assert result is None
    
    def test_get_invoices_by_job(self, invoice_service, sample_job, app):
        """Test getting invoices for a specific job"""
        with app.app_context():
            # Create multiple invoices for the job
            for i in range(3):
                invoice_service.create_invoice({
                    'job_id': sample_job.id,
                    'due_date': date.today() + timedelta(days=30 + i)
                })
            
            invoices = invoice_service.get_invoices_by_job(sample_job.id)
            
            # Should have original seeded invoice + 3 new ones
            assert len(invoices) >= 4
            assert all(inv.job_id == sample_job.id for inv in invoices)
    
    def test_invoice_line_item_calculations(self, invoice_service, sample_job, app):
        """Test line item total calculations"""
        with app.app_context():
            invoice_data = {
                'job_id': sample_job.id,
                'due_date': date.today() + timedelta(days=30),
                'line_items': [
                    # Test decimal quantities and prices
                    {'description': 'Hourly work', 'quantity': 2.5, 'unit_price': 100.00},
                    {'description': 'Materials', 'quantity': 10, 'unit_price': 12.99},
                    {'description': 'Flat fee', 'quantity': 1, 'unit_price': 500.00}
                ]
            }
            
            invoice = invoice_service.create_invoice(invoice_data)
            
            assert invoice.line_items[0].line_total == 250.00  # 2.5 * 100
            assert invoice.line_items[1].line_total == 129.90  # 10 * 12.99
            assert invoice.line_items[2].line_total == 500.00  # 1 * 500
            
            # Total should be sum of line items
            expected_subtotal = 250.00 + 129.90 + 500.00
            assert float(invoice.subtotal) == expected_subtotal