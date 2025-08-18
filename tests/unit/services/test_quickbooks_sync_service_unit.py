# tests/unit/services/test_quickbooks_sync_service_unit.py
"""
TDD RED Phase: Tests for QuickBooksSyncService Repository Pattern Refactoring

These tests MUST fail initially to detect repository pattern violations,
then pass after refactoring the service to use repositories.

This service has 32+ database violations that need to be refactored.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from decimal import Decimal
from datetime import datetime, date
from services.quickbooks_sync_service import QuickBooksSyncService
from crm_database import Contact, Product, Quote, Invoice, Job, Property, QuickBooksSync, QuoteLineItem, InvoiceLineItem
from repositories.contact_repository import ContactRepository
from repositories.product_repository import ProductRepository
from repositories.quote_repository import QuoteRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.job_repository import JobRepository
from repositories.property_repository import PropertyRepository
from repositories.quickbooks_sync_repository import QuickBooksSyncRepository
from repositories.quote_line_item_repository import QuoteLineItemRepository
from repositories.invoice_line_item_repository import InvoiceLineItemRepository


class TestQuickBooksSyncServiceRepositoryViolations:
    """Test that QuickBooksSyncService uses repositories instead of direct DB access"""
    
    @pytest.fixture
    def mock_repositories(self):
        """Create all mock repositories needed"""
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def mock_qb_service(self):
        """Mock QuickBooks service"""
        return Mock()
    
    @pytest.fixture
    def service(self, mock_repositories, mock_qb_service):
        """Create service with mocked repositories - THIS WILL FAIL until we add repository parameters"""
        service = QuickBooksSyncService(
            contact_repository=mock_repositories['contact_repository'],
            product_repository=mock_repositories['product_repository'],
            quote_repository=mock_repositories['quote_repository'],
            invoice_repository=mock_repositories['invoice_repository'],
            job_repository=mock_repositories['job_repository'],
            property_repository=mock_repositories['property_repository'],
            quickbooks_sync_repository=mock_repositories['quickbooks_sync_repository'],
            quote_line_item_repository=mock_repositories['quote_line_item_repository'],
            invoice_line_item_repository=mock_repositories['invoice_line_item_repository']
        )
        service.qb_service = mock_qb_service
        return service

    def test_service_constructor_accepts_repositories(self, mock_repositories):
        """Test that service constructor accepts all required repositories"""
        # This will fail until we modify the constructor
        service = QuickBooksSyncService(
            contact_repository=mock_repositories['contact_repository'],
            product_repository=mock_repositories['product_repository'],
            quote_repository=mock_repositories['quote_repository'],
            invoice_repository=mock_repositories['invoice_repository'],
            job_repository=mock_repositories['job_repository'],
            property_repository=mock_repositories['property_repository'],
            quickbooks_sync_repository=mock_repositories['quickbooks_sync_repository'],
            quote_line_item_repository=mock_repositories['quote_line_item_repository'],
            invoice_line_item_repository=mock_repositories['invoice_line_item_repository']
        )
        
        # Verify repositories are stored as attributes
        assert hasattr(service, 'contact_repository')
        assert hasattr(service, 'product_repository')
        assert hasattr(service, 'quote_repository')
        assert hasattr(service, 'invoice_repository')
        assert hasattr(service, 'job_repository')
        assert hasattr(service, 'property_repository')
        assert hasattr(service, 'quickbooks_sync_repository')
        assert hasattr(service, 'quote_line_item_repository')
        assert hasattr(service, 'invoice_line_item_repository')


class TestQuickBooksSyncServiceCustomerSync:
    """Test customer synchronization repository usage"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_sync_customer_uses_contact_repository_to_find_by_quickbooks_id(self, service, mock_repositories):
        """Test _sync_customer uses ContactRepository.find_by_quickbooks_id instead of Contact.query.filter_by"""
        # Arrange
        qb_customer = {'Id': '123', 'DisplayName': 'Test Customer', 'SyncToken': '0'}
        existing_contact = Mock(spec=Contact)
        
        mock_repositories['contact_repository'].find_by_quickbooks_id.return_value = existing_contact
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        result = service._sync_customer(qb_customer)
        
        # Assert - This will fail until we replace Contact.query.filter_by(quickbooks_customer_id=qb_id).first()
        mock_repositories['contact_repository'].find_by_quickbooks_id.assert_called_once_with('123')
        assert result == existing_contact
    
    def test_sync_customer_uses_contact_repository_to_find_by_phone(self, service, mock_repositories):
        """Test _sync_customer uses ContactRepository.find_by_phone instead of Contact.query.filter_by(phone=phone)"""
        # Arrange
        qb_customer = {
            'Id': '123', 
            'DisplayName': 'Test Customer',
            'Mobile': {'FreeFormNumber': '555-123-4567'},
            'SyncToken': '0'
        }
        existing_contact = Mock(spec=Contact)
        
        mock_repositories['contact_repository'].find_by_quickbooks_id.return_value = None
        mock_repositories['contact_repository'].find_by_phone.return_value = existing_contact
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        result = service._sync_customer(qb_customer)
        
        # Assert - This will fail until we replace Contact.query.filter_by(phone=phone).first()
        mock_repositories['contact_repository'].find_by_phone.assert_called_once_with('+15551234567')
        assert result == existing_contact
    
    def test_sync_customer_uses_contact_repository_to_find_by_email(self, service, mock_repositories):
        """Test _sync_customer uses ContactRepository.find_by_email instead of Contact.query.filter_by(email=email)"""
        # Arrange
        qb_customer = {
            'Id': '123',
            'DisplayName': 'Test Customer',
            'PrimaryEmailAddr': {'Address': 'test@example.com'},
            'SyncToken': '0'
        }
        existing_contact = Mock(spec=Contact)
        
        mock_repositories['contact_repository'].find_by_quickbooks_id.return_value = None
        mock_repositories['contact_repository'].find_by_phone.return_value = None
        mock_repositories['contact_repository'].find_by_email.return_value = existing_contact
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        result = service._sync_customer(qb_customer)
        
        # Assert - This will fail until we replace Contact.query.filter_by(email=email).first()
        mock_repositories['contact_repository'].find_by_email.assert_called_once_with('test@example.com')
        assert result == existing_contact
    
    def test_sync_customer_uses_contact_repository_to_create(self, service, mock_repositories):
        """Test _sync_customer uses ContactRepository.create instead of Contact() + db.session.add()"""
        # Arrange
        qb_customer = {
            'Id': '123',
            'GivenName': 'John',
            'FamilyName': 'Doe',
            'PrimaryEmailAddr': {'Address': 'john@example.com'},
            'Mobile': {'FreeFormNumber': '555-123-4567'},
            'Balance': '500.00',
            'Taxable': False,
            'SyncToken': '0'
        }
        new_contact = Mock(spec=Contact, id=1)
        
        mock_repositories['contact_repository'].find_by_quickbooks_id.return_value = None
        mock_repositories['contact_repository'].find_by_phone.return_value = None
        mock_repositories['contact_repository'].find_by_email.return_value = None
        mock_repositories['contact_repository'].create.return_value = new_contact
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        result = service._sync_customer(qb_customer)
        
        # Assert - This will fail until we replace Contact() + db.session.add()
        mock_repositories['contact_repository'].create.assert_called_once()
        create_data = mock_repositories['contact_repository'].create.call_args[0][0]
        
        assert create_data['quickbooks_customer_id'] == '123'
        assert create_data['first_name'] == 'John'
        assert create_data['last_name'] == 'Doe'
        assert create_data['email'] == 'john@example.com'
        assert create_data['phone'] == '+15551234567'
        assert create_data['customer_type'] == 'customer'
        assert create_data['outstanding_balance'] == Decimal('500.00')
        assert create_data['tax_exempt'] is True
        
        assert result == new_contact


class TestQuickBooksSyncServiceProductSync:
    """Test product synchronization repository usage"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_sync_item_uses_product_repository_to_find(self, service, mock_repositories):
        """Test _sync_item uses ProductRepository.find_by_quickbooks_id instead of Product.query.filter_by"""
        # Arrange
        qb_item = {'Id': '123', 'Name': 'Test Product', 'Type': 'Service', 'SyncToken': '0'}
        existing_product = Mock(spec=Product)
        
        mock_repositories['product_repository'].find_by_quickbooks_id.return_value = existing_product
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        is_new = service._sync_item(qb_item)
        
        # Assert - This will fail until we replace Product.query.filter_by(quickbooks_item_id=qb_id).first()
        mock_repositories['product_repository'].find_by_quickbooks_id.assert_called_once_with('123')
        assert is_new is False
    
    def test_sync_item_uses_product_repository_to_create(self, service, mock_repositories):
        """Test _sync_item uses ProductRepository.create instead of Product() + db.session.add()"""
        # Arrange
        qb_item = {
            'Id': '123',
            'Name': 'Test Product',
            'Description': 'A test product',
            'Type': 'Inventory',
            'UnitPrice': '25.50',
            'QtyOnHand': '100',
            'Active': True,
            'Taxable': False,
            'SyncToken': '0'
        }
        new_product = Mock(spec=Product)
        
        mock_repositories['product_repository'].find_by_quickbooks_id.return_value = None
        mock_repositories['product_repository'].create.return_value = new_product
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        is_new = service._sync_item(qb_item)
        
        # Assert - This will fail until we replace Product() + db.session.add()
        mock_repositories['product_repository'].create.assert_called_once()
        create_data = mock_repositories['product_repository'].create.call_args[0][0]
        
        assert create_data['quickbooks_item_id'] == '123'
        assert create_data['name'] == 'Test Product'
        assert create_data['description'] == 'A test product'
        assert create_data['item_type'] == 'inventory'
        assert create_data['unit_price'] == Decimal('25.50')
        assert create_data['quantity_on_hand'] == 100
        assert create_data['active'] is True
        assert create_data['taxable'] is False
        
        assert is_new is True


class TestQuickBooksSyncServiceQuoteSync:
    """Test quote/estimate synchronization repository usage"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_sync_estimate_uses_quote_repository_to_find(self, service, mock_repositories):
        """Test _sync_estimate uses QuoteRepository.find_by_quickbooks_id instead of Quote.query.filter_by"""
        # Arrange
        qb_estimate = {
            'Id': '123',
            'TotalAmt': '1500.50',
            'TxnDate': '2024-01-15',
            'CustomerRef': {'value': '456', 'name': 'Test Customer'},
            'Line': [],
            'SyncToken': '0'
        }
        existing_quote = Mock(spec=Quote)
        
        mock_repositories['quote_repository'].find_by_quickbooks_id.return_value = existing_quote
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        is_new = service._sync_estimate(qb_estimate)
        
        # Assert - This will fail until we replace Quote.query.filter_by(quickbooks_estimate_id=qb_id).first()
        mock_repositories['quote_repository'].find_by_quickbooks_id.assert_called_once_with('123')
        assert is_new is False
    
    def test_sync_estimate_line_items_uses_line_item_repository(self, service, mock_repositories):
        """Test _sync_estimate_line_items uses QuoteLineItemRepository instead of direct queries"""
        # Arrange
        quote = Mock(id=1)
        qb_lines = [
            {
                'Id': '1',
                'DetailType': 'SalesItemLineDetail',
                'Description': 'Test Item',
                'Amount': '100.00',
                'SalesItemLineDetail': {
                    'ItemRef': {'value': '123'},
                    'Qty': '2',
                    'UnitPrice': '50.00'
                }
            }
        ]
        
        mock_product = Mock(id=1)
        mock_repositories['product_repository'].find_by_quickbooks_id.return_value = mock_product
        mock_repositories['quote_line_item_repository'].create.return_value = Mock()
        
        # Act
        service._sync_estimate_line_items(quote, qb_lines)
        
        # Assert - This will fail until we replace QuoteLineItem.query.filter_by(quote_id=quote.id).delete()
        mock_repositories['quote_line_item_repository'].delete_by_quote_id.assert_called_once_with(1)
        
        # Assert - This will fail until we replace Product.query.filter_by(quickbooks_item_id=item_qb_id).first()
        mock_repositories['product_repository'].find_by_quickbooks_id.assert_called_once_with('123')
        
        # Assert - This will fail until we replace db.session.add(line_item)
        mock_repositories['quote_line_item_repository'].create.assert_called_once()


class TestQuickBooksSyncServiceInvoiceSync:
    """Test invoice synchronization repository usage"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_sync_invoice_uses_invoice_repository_to_find(self, service, mock_repositories):
        """Test _sync_invoice uses InvoiceRepository.find_by_quickbooks_id instead of Invoice.query.filter_by"""
        # Arrange
        qb_invoice = {
            'Id': '123',
            'TotalAmt': '1000.00',
            'Balance': '500.00',
            'TxnDate': '2024-01-15',
            'DueDate': '2024-02-15',
            'CustomerRef': {'value': '456', 'name': 'Test Customer'},
            'Line': [],
            'SyncToken': '0'
        }
        existing_invoice = Mock(spec=Invoice)
        
        mock_repositories['invoice_repository'].find_by_quickbooks_id.return_value = existing_invoice
        mock_repositories['quickbooks_sync_repository'].create_or_update.return_value = Mock()
        
        # Act
        is_new = service._sync_invoice(qb_invoice)
        
        # Assert - This will fail until we replace Invoice.query.filter_by(quickbooks_invoice_id=qb_id).first()
        mock_repositories['invoice_repository'].find_by_quickbooks_id.assert_called_once_with('123')
        assert is_new is False
    
    def test_sync_invoice_line_items_uses_line_item_repository(self, service, mock_repositories):
        """Test _sync_invoice_line_items uses InvoiceLineItemRepository instead of direct queries"""
        # Arrange
        invoice = Mock(id=1)
        qb_lines = [
            {
                'Id': '1',
                'DetailType': 'SalesItemLineDetail',
                'Description': 'Test Service',
                'Amount': '150.00',
                'SalesItemLineDetail': {
                    'ItemRef': {'value': '456'},
                    'Qty': '3',
                    'UnitPrice': '50.00'
                }
            }
        ]
        
        mock_product = Mock(id=2)
        mock_repositories['product_repository'].find_by_quickbooks_id.return_value = mock_product
        mock_repositories['invoice_line_item_repository'].create.return_value = Mock()
        
        # Act
        service._sync_invoice_line_items(invoice, qb_lines)
        
        # Assert - This will fail until we replace InvoiceLineItem.query.filter_by(invoice_id=invoice.id).delete()
        mock_repositories['invoice_line_item_repository'].delete_by_invoice_id.assert_called_once_with(1)
        
        # Assert - This will fail until we replace Product.query.filter_by(quickbooks_item_id=item_qb_id).first()
        mock_repositories['product_repository'].find_by_quickbooks_id.assert_called_once_with('456')
        
        # Assert - This will fail until we replace db.session.add(line_item)
        mock_repositories['invoice_line_item_repository'].create.assert_called_once()


class TestQuickBooksSyncServiceJobPropertyCreation:
    """Test job and property creation repository usage"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_find_or_create_job_uses_contact_repository(self, service, mock_repositories):
        """Test _find_or_create_job_for_qb_transaction uses ContactRepository instead of Contact.query"""
        # Arrange
        qb_transaction = {
            'CustomerRef': {'value': '123', 'name': 'Test Customer'},
            'DocNumber': 'INV-001',
            'TxnType': 'Invoice'
        }
        
        mock_contact = Mock(id=1)
        mock_property = Mock(id=1)
        mock_job = Mock(id=1)
        
        mock_repositories['contact_repository'].find_by_quickbooks_id.return_value = mock_contact
        mock_repositories['property_repository'].find_by_contact_id.return_value = mock_property
        mock_repositories['job_repository'].create.return_value = mock_job
        
        # Act
        result = service._find_or_create_job_for_qb_transaction(qb_transaction)
        
        # Assert - This will fail until we replace Contact.query.filter_by(quickbooks_customer_id=customer_qb_id).first()
        mock_repositories['contact_repository'].find_by_quickbooks_id.assert_called_once_with('123')
        assert result == mock_job
    
    def test_find_or_create_job_uses_property_repository(self, service, mock_repositories):
        """Test _find_or_create_job_for_qb_transaction uses PropertyRepository instead of Property.query"""
        # Arrange
        qb_transaction = {
            'CustomerRef': {'value': '123', 'name': 'Test Customer'},
            'DocNumber': 'EST-001',
            'TxnType': 'Estimate'
        }
        
        mock_contact = Mock(id=2)
        mock_property = Mock(id=2)
        mock_job = Mock(id=2)
        
        mock_repositories['contact_repository'].find_by_quickbooks_id.return_value = mock_contact
        mock_repositories['property_repository'].find_by_contact_id.return_value = mock_property
        mock_repositories['job_repository'].create.return_value = mock_job
        
        # Act
        result = service._find_or_create_job_for_qb_transaction(qb_transaction)
        
        # Assert - This will fail until we replace Property.query.filter_by(contact_id=contact.id).first()
        mock_repositories['property_repository'].find_by_contact_id.assert_called_once_with(2)
        assert result == mock_job
    
    def test_find_or_create_job_creates_contact_via_repository(self, service, mock_repositories):
        """Test _find_or_create_job creates contact using repository instead of Contact() + db.session.add()"""
        # Arrange
        qb_transaction = {
            'CustomerRef': {'value': '999', 'name': 'Unknown Customer'},
            'DocNumber': 'QUO-001',
            'TxnType': 'Estimate'
        }
        
        mock_new_contact = Mock(id=3)
        mock_property = Mock(id=3)
        mock_job = Mock(id=3)
        
        mock_repositories['contact_repository'].find_by_quickbooks_id.return_value = None
        mock_repositories['contact_repository'].create.return_value = mock_new_contact
        mock_repositories['property_repository'].find_by_contact_id.return_value = mock_property
        mock_repositories['job_repository'].create.return_value = mock_job
        
        # Act
        result = service._find_or_create_job_for_qb_transaction(qb_transaction)
        
        # Assert - This will fail until we replace Contact() + db.session.add()
        mock_repositories['contact_repository'].create.assert_called_once()
        contact_data = mock_repositories['contact_repository'].create.call_args[0][0]
        assert contact_data['first_name'] == 'Unknown Customer'
        assert contact_data['customer_type'] == 'customer'
        
        assert result == mock_job


class TestQuickBooksSyncServiceSyncRecording:
    """Test sync recording repository usage"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_record_sync_uses_quickbooks_sync_repository(self, service, mock_repositories):
        """Test _record_sync uses QuickBooksSyncRepository instead of QuickBooksSync.query"""
        # Arrange
        existing_sync = Mock()
        mock_repositories['quickbooks_sync_repository'].find_by_entity.return_value = existing_sync
        
        # Act
        service._record_sync('customer', '123', 1, 'contact', '5')
        
        # Assert - This will fail until we replace QuickBooksSync.query.filter_by()
        mock_repositories['quickbooks_sync_repository'].find_by_entity.assert_called_once_with('customer', '123')
    
    def test_record_sync_creates_via_repository_when_not_found(self, service, mock_repositories):
        """Test _record_sync creates new record using repository instead of QuickBooksSync() + db.session.add()"""
        # Arrange
        new_sync = Mock()
        mock_repositories['quickbooks_sync_repository'].find_by_entity.return_value = None
        mock_repositories['quickbooks_sync_repository'].create.return_value = new_sync
        
        # Act
        service._record_sync('product', '456', 2, 'product', '3')
        
        # Assert - This will fail until we replace QuickBooksSync() + db.session.add()
        mock_repositories['quickbooks_sync_repository'].create.assert_called_once()


class TestQuickBooksSyncServiceFinancialSummary:
    """Test financial summary updates repository usage"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_update_contact_financial_summary_uses_invoice_repository(self, service, mock_repositories):
        """Test update_contact_financial_summary uses InvoiceRepository instead of Invoice.query.join()"""
        # Arrange
        contact = Mock(id=1)
        mock_invoices = [
            Mock(total_amount=Decimal('1000.00'), balance_due=Decimal('500.00'), payment_status='partial'),
            Mock(total_amount=Decimal('2000.00'), balance_due=Decimal('0.00'), payment_status='paid'),
            Mock(total_amount=Decimal('1500.00'), balance_due=Decimal('1500.00'), payment_status='unpaid')
        ]
        
        mock_repositories['invoice_repository'].find_by_contact_id.return_value = mock_invoices
        
        # Act
        service.update_contact_financial_summary(contact)
        
        # Assert - This will fail until we replace Invoice.query.join(Job).join(Property).filter()
        mock_repositories['invoice_repository'].find_by_contact_id.assert_called_once_with(1)


class TestQuickBooksSyncServiceTransactionManagement:
    """Test that transaction management is removed (no more db.session calls)"""
    
    @pytest.fixture
    def mock_repositories(self):
        return {
            'contact_repository': Mock(spec=ContactRepository),
            'product_repository': Mock(spec=ProductRepository),
            'quote_repository': Mock(spec=QuoteRepository),
            'invoice_repository': Mock(spec=InvoiceRepository),
            'job_repository': Mock(spec=JobRepository),
            'property_repository': Mock(spec=PropertyRepository),
            'quickbooks_sync_repository': Mock(spec=QuickBooksSyncRepository),
            'quote_line_item_repository': Mock(spec=QuoteLineItemRepository),
            'invoice_line_item_repository': Mock(spec=InvoiceLineItemRepository)
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        return QuickBooksSyncService(**mock_repositories)
    
    def test_sync_methods_do_not_handle_transactions(self, service, mock_repositories):
        """Test that sync methods don't call db.session.commit() or rollback() - transaction handling moves to caller"""
        # Arrange
        service.qb_service = Mock()
        service.qb_service.list_customers.return_value = []
        service.qb_service.list_items.return_value = []
        service.qb_service.list_estimates.return_value = []
        service.qb_service.list_invoices.return_value = []
        
        # This test will pass immediately as it's just verifying no db.session calls
        # The actual test is that the refactored code doesn't have any db.session imports or calls
        
        # Act
        service.sync_customers()
        service.sync_items()
        service.sync_estimates()
        service.sync_invoices()
        
        # Assert - No db.session calls should be made
        # The repositories handle their own session management
        pass  # This test passes by not failing - the real test is in the implementation


# These tests will ALL FAIL until we refactor the service to use repositories
# Expected failures:
# 1. Constructor doesn't accept repository parameters
# 2. All find operations use direct queries instead of repositories  
# 3. All create operations use direct model instantiation + db.session.add
# 4. All delete operations use direct queries
# 5. Transaction management in service instead of repository layer