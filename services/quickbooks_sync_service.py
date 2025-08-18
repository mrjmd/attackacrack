"""
QuickBooks Sync Service
Handles syncing data between QuickBooks and CRM
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from decimal import Decimal
from flask import current_app
from crm_database import Contact, Product, Quote, Invoice, Job, Property
from services.quickbooks_service import QuickBooksService

if TYPE_CHECKING:
    from repositories.contact_repository import ContactRepository
    from repositories.product_repository import ProductRepository
    from repositories.quote_repository import QuoteRepository
    from repositories.invoice_repository import InvoiceRepository
    from repositories.job_repository import JobRepository
    from repositories.property_repository import PropertyRepository
    from repositories.quickbooks_sync_repository import QuickBooksSyncRepository
    from repositories.quote_line_item_repository import QuoteLineItemRepository
    from repositories.invoice_line_item_repository import InvoiceLineItemRepository


class QuickBooksSyncService:
    def __init__(self, 
                 contact_repository: 'ContactRepository' = None,
                 product_repository: 'ProductRepository' = None,
                 quote_repository: 'QuoteRepository' = None,
                 invoice_repository: 'InvoiceRepository' = None,
                 job_repository: 'JobRepository' = None,
                 property_repository: 'PropertyRepository' = None,
                 quickbooks_sync_repository: 'QuickBooksSyncRepository' = None,
                 quote_line_item_repository: 'QuoteLineItemRepository' = None,
                 invoice_line_item_repository: 'InvoiceLineItemRepository' = None):
        self.qb_service = QuickBooksService()
        
        # Repository dependencies
        self.contact_repository = contact_repository
        self.product_repository = product_repository
        self.quote_repository = quote_repository
        self.invoice_repository = invoice_repository
        self.job_repository = job_repository
        self.property_repository = property_repository
        self.quickbooks_sync_repository = quickbooks_sync_repository
        self.quote_line_item_repository = quote_line_item_repository
        self.invoice_line_item_repository = invoice_line_item_repository
    
    def sync_all(self) -> Dict[str, Any]:
        """Run full sync of all QuickBooks data"""
        results = {
            'customers': self.sync_customers(),
            'items': self.sync_items(),
            'estimates': self.sync_estimates(),
            'invoices': self.sync_invoices()
        }
        return results
    
    def sync_customers(self) -> Dict[str, int]:
        """Sync all customers from QuickBooks"""
        results = {'created': 0, 'updated': 0, 'errors': 0}
        
        try:
            customers = self.qb_service.list_customers()
            
            for qb_customer in customers:
                try:
                    self._sync_customer(qb_customer)
                    results['updated'] += 1
                except Exception as e:
                    current_app.logger.error(f"Error syncing customer {qb_customer.get('Id')}: {str(e)}")
                    results['errors'] += 1
            
            # Transaction management handled by repositories
            
        except Exception as e:
            current_app.logger.error(f"Error fetching customers: {str(e)}")
        
        return results
    
    def sync_items(self) -> Dict[str, int]:
        """Sync all items (products/services) from QuickBooks"""
        results = {'created': 0, 'updated': 0, 'errors': 0}
        
        try:
            items = self.qb_service.list_items()
            
            for qb_item in items:
                try:
                    if self._sync_item(qb_item):
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                except Exception as e:
                    current_app.logger.error(f"Error syncing item {qb_item.get('Id')}: {str(e)}")
                    results['errors'] += 1
            
            # Transaction management handled by repositories
            
        except Exception as e:
            current_app.logger.error(f"Error fetching items: {str(e)}")
        
        return results
    
    def sync_estimates(self) -> Dict[str, int]:
        """Sync all estimates from QuickBooks as quotes"""
        results = {'created': 0, 'updated': 0, 'errors': 0}
        
        try:
            estimates = self.qb_service.list_estimates()
            
            for qb_estimate in estimates:
                try:
                    if self._sync_estimate(qb_estimate):
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                except Exception as e:
                    current_app.logger.error(f"Error syncing estimate {qb_estimate.get('Id')}: {str(e)}")
                    results['errors'] += 1
            
            # Transaction management handled by repositories
            
        except Exception as e:
            current_app.logger.error(f"Error fetching estimates: {str(e)}")
        
        return results
    
    def sync_invoices(self) -> Dict[str, int]:
        """Sync all invoices from QuickBooks"""
        results = {'created': 0, 'updated': 0, 'errors': 0}
        
        try:
            invoices = self.qb_service.list_invoices()
            
            for qb_invoice in invoices:
                try:
                    if self._sync_invoice(qb_invoice):
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                except Exception as e:
                    current_app.logger.error(f"Error syncing invoice {qb_invoice.get('Id')}: {str(e)}")
                    results['errors'] += 1
            
            # Transaction management handled by repositories
            
        except Exception as e:
            current_app.logger.error(f"Error fetching invoices: {str(e)}")
        
        return results
    
    def _sync_customer(self, qb_customer: Dict[str, Any]) -> Contact:
        """Sync a single customer to contact"""
        qb_id = qb_customer['Id']
        
        # Try to find by QuickBooks ID first
        contact = self.contact_repository.find_by_quickbooks_customer_id(qb_id)
        
        # If not found, try to match by phone or email
        if not contact:
            # Extract phone numbers
            phones = []
            if qb_customer.get('PrimaryPhone'):
                phones.append(self._normalize_phone(qb_customer['PrimaryPhone']['FreeFormNumber']))
            if qb_customer.get('Mobile'):
                phones.append(self._normalize_phone(qb_customer['Mobile']['FreeFormNumber']))
            
            # Try to find by phone
            for phone in phones:
                if phone:
                    contact = self.contact_repository.find_by_phone(phone)
                    if contact:
                        break
            
            # Try to find by email
            if not contact and qb_customer.get('PrimaryEmailAddr'):
                email = qb_customer['PrimaryEmailAddr']['Address']
                contact = self.contact_repository.find_by_email(email)
        
        # Build contact data
        contact_data = {
            'quickbooks_customer_id': qb_id,
            'quickbooks_sync_token': qb_customer.get('SyncToken'),
            'customer_type': 'customer',
            'tax_exempt': qb_customer.get('Taxable', True) == False
        }
        
        # Set phone (prefer mobile)
        if qb_customer.get('Mobile'):
            contact_data['phone'] = self._normalize_phone(qb_customer['Mobile']['FreeFormNumber'])
        elif qb_customer.get('PrimaryPhone'):
            contact_data['phone'] = self._normalize_phone(qb_customer['PrimaryPhone']['FreeFormNumber'])
        
        # Parse name
        if qb_customer.get('GivenName'):
            contact_data['first_name'] = qb_customer['GivenName']
        if qb_customer.get('FamilyName'):
            contact_data['last_name'] = qb_customer['FamilyName']
        elif qb_customer.get('DisplayName'):
            # Try to split display name
            parts = qb_customer['DisplayName'].split(' ', 1)
            contact_data['first_name'] = parts[0]
            if len(parts) > 1:
                contact_data['last_name'] = parts[1]
        
        # Email
        if qb_customer.get('PrimaryEmailAddr'):
            contact_data['email'] = qb_customer['PrimaryEmailAddr']['Address']
        
        # Financial info
        if qb_customer.get('Balance'):
            contact_data['outstanding_balance'] = Decimal(str(qb_customer['Balance']))
        
        # Create or update contact using repository
        if not contact:
            contact = self.contact_repository.create(contact_data)
        else:
            contact = self.contact_repository.update(contact, contact_data)
        
        # Record sync
        self._record_sync('customer', qb_id, contact.id, 'contact', qb_customer.get('SyncToken'))
        
        return contact
    
    def _sync_item(self, qb_item: Dict[str, Any]) -> bool:
        """Sync a single item to product. Returns True if created, False if updated"""
        qb_id = qb_item['Id']
        
        # Find existing product
        product = self.product_repository.find_by_quickbooks_item_id(qb_id)
        is_new = product is None
        
        # Build product data
        product_data = {
            'quickbooks_item_id': qb_id,
            'quickbooks_sync_token': qb_item.get('SyncToken'),
            'name': qb_item['Name'],
            'description': qb_item.get('Description'),
            'item_type': qb_item['Type'].lower(),
            'active': qb_item.get('Active', True),
            'taxable': qb_item.get('Taxable', True)
        }
        
        # Pricing
        if qb_item.get('UnitPrice'):
            product_data['unit_price'] = Decimal(str(qb_item['UnitPrice']))
        
        # For inventory items
        if qb_item['Type'] == 'Inventory' and qb_item.get('QtyOnHand'):
            product_data['quantity_on_hand'] = int(qb_item['QtyOnHand'])
        
        # Income account
        if qb_item.get('IncomeAccountRef'):
            product_data['income_account'] = qb_item['IncomeAccountRef'].get('name')
        
        # Create or update product using repository
        if not product:
            product = self.product_repository.create(product_data)
        else:
            product = self.product_repository.update(product, product_data)
        
        # Record sync
        self._record_sync('item', qb_id, product.id, 'product', qb_item.get('SyncToken'))
        
        return is_new
    
    def _sync_estimate(self, qb_estimate: Dict[str, Any]) -> bool:
        """Sync a single estimate to quote. Returns True if created, False if updated"""
        qb_id = qb_estimate['Id']
        
        # Find existing quote
        quote = self.quote_repository.find_by_quickbooks_id(qb_id)
        is_new = quote is None
        
        # Build quote data
        quote_data = {
            'quickbooks_estimate_id': qb_id,
            'quickbooks_sync_token': qb_estimate.get('SyncToken'),
            'subtotal': Decimal(str(qb_estimate.get('TotalAmt', 0))),
            'total_amount': Decimal(str(qb_estimate.get('TotalAmt', 0)))
        }
        
        # Tax amount
        if qb_estimate.get('TxnTaxDetail'):
            quote_data['tax_amount'] = Decimal(str(qb_estimate['TxnTaxDetail'].get('TotalTax', 0)))
        
        # Dates
        if qb_estimate.get('TxnDate'):
            quote_data['created_at'] = datetime.strptime(qb_estimate['TxnDate'], '%Y-%m-%d')
        if qb_estimate.get('ExpirationDate'):
            quote_data['expiration_date'] = datetime.strptime(qb_estimate['ExpirationDate'], '%Y-%m-%d').date()
        
        # Status mapping
        if qb_estimate.get('AcceptedDate'):
            quote_data['status'] = 'Accepted'
        elif qb_estimate.get('EmailStatus') == 'EmailSent':
            quote_data['status'] = 'Sent'
        else:
            quote_data['status'] = 'Draft'
        
        # Create or update quote using repository
        if not quote:
            # Need to find or create a job for this quote
            job = self._find_or_create_job_for_qb_transaction(qb_estimate)
            quote_data['job_id'] = job.id
            quote = self.quote_repository.create(quote_data)
        else:
            quote = self.quote_repository.update(quote, quote_data)
        
        # Sync line items
        self._sync_estimate_line_items(quote, qb_estimate.get('Line', []))
        
        # Record sync
        self._record_sync('estimate', qb_id, quote.id, 'quote', qb_estimate.get('SyncToken'))
        
        return is_new
    
    def _sync_invoice(self, qb_invoice: Dict[str, Any]) -> bool:
        """Sync a single invoice. Returns True if created, False if updated"""
        qb_id = qb_invoice['Id']
        
        # Find existing invoice
        invoice = self.invoice_repository.find_by_quickbooks_id(qb_id)
        is_new = invoice is None
        
        # Calculate financial fields
        total_amount = Decimal(str(qb_invoice.get('TotalAmt', 0)))
        balance_due = Decimal(str(qb_invoice.get('Balance', 0)))
        amount_paid = total_amount - balance_due
        
        # Build invoice data
        invoice_data = {
            'quickbooks_invoice_id': qb_id,
            'quickbooks_sync_token': qb_invoice.get('SyncToken'),
            'subtotal': total_amount,
            'total_amount': total_amount,
            'balance_due': balance_due,
            'amount_paid': amount_paid
        }
        
        # Tax amount
        if qb_invoice.get('TxnTaxDetail'):
            invoice_data['tax_amount'] = Decimal(str(qb_invoice['TxnTaxDetail'].get('TotalTax', 0)))
        
        # Dates
        if qb_invoice.get('TxnDate'):
            invoice_data['invoice_date'] = datetime.strptime(qb_invoice['TxnDate'], '%Y-%m-%d').date()
        if qb_invoice.get('DueDate'):
            invoice_data['due_date'] = datetime.strptime(qb_invoice['DueDate'], '%Y-%m-%d').date()
        
        # Payment status
        if balance_due == 0:
            invoice_data['payment_status'] = 'paid'
        elif amount_paid > 0:
            invoice_data['payment_status'] = 'partial'
        elif invoice_data.get('due_date') and invoice_data['due_date'] < datetime.now().date():
            invoice_data['payment_status'] = 'overdue'
        else:
            invoice_data['payment_status'] = 'unpaid'
        
        # Link to estimate if exists
        if qb_invoice.get('LinkedTxn'):
            for linked in qb_invoice['LinkedTxn']:
                if linked['TxnType'] == 'Estimate':
                    estimate_qb_id = linked['TxnId']
                    quote = self.quote_repository.find_by_quickbooks_id(estimate_qb_id)
                    if quote:
                        invoice_data['quote_id'] = quote.id
        
        # Create or update invoice using repository
        if not invoice:
            # Need to find or create a job for this invoice
            job = self._find_or_create_job_for_qb_transaction(qb_invoice)
            invoice_data['job_id'] = job.id
            invoice = self.invoice_repository.create(invoice_data)
        else:
            invoice = self.invoice_repository.update(invoice, invoice_data)
        
        # Sync line items
        self._sync_invoice_line_items(invoice, qb_invoice.get('Line', []))
        
        # Record sync
        self._record_sync('invoice', qb_id, invoice.id, 'invoice', qb_invoice.get('SyncToken'))
        
        return is_new
    
    def _sync_estimate_line_items(self, quote: Quote, qb_lines: List[Dict[str, Any]]):
        """Sync line items for an estimate"""
        # Remove existing line items
        self.quote_line_item_repository.delete_by_quote_id(quote.id)
        
        for qb_line in qb_lines:
            if qb_line.get('DetailType') == 'SalesItemLineDetail':
                # Build line item data
                line_item_data = {
                    'quote_id': quote.id,
                    'description': qb_line.get('Description', ''),
                    'quantity': Decimal(str(qb_line.get('SalesItemLineDetail', {}).get('Qty', 1))),
                    'unit_price': Decimal(str(qb_line.get('SalesItemLineDetail', {}).get('UnitPrice', 0))),
                    'line_total': Decimal(str(qb_line.get('Amount', 0))),
                    'quickbooks_line_id': qb_line.get('Id')
                }
                
                # Link to product if exists
                if qb_line['SalesItemLineDetail'].get('ItemRef'):
                    item_qb_id = qb_line['SalesItemLineDetail']['ItemRef']['value']
                    product = self.product_repository.find_by_quickbooks_item_id(item_qb_id)
                    if product:
                        line_item_data['product_id'] = product.id
                
                # Create line item using repository
                self.quote_line_item_repository.create(line_item_data)
    
    def _sync_invoice_line_items(self, invoice: Invoice, qb_lines: List[Dict[str, Any]]):
        """Sync line items for an invoice"""
        # Remove existing line items
        self.invoice_line_item_repository.delete_by_invoice_id(invoice.id)
        
        for qb_line in qb_lines:
            if qb_line.get('DetailType') == 'SalesItemLineDetail':
                # Build line item data
                line_item_data = {
                    'invoice_id': invoice.id,
                    'description': qb_line.get('Description', ''),
                    'quantity': Decimal(str(qb_line.get('SalesItemLineDetail', {}).get('Qty', 1))),
                    'unit_price': Decimal(str(qb_line.get('SalesItemLineDetail', {}).get('UnitPrice', 0))),
                    'line_total': Decimal(str(qb_line.get('Amount', 0))),
                    'quickbooks_line_id': qb_line.get('Id')
                }
                
                # Link to product if exists
                if qb_line['SalesItemLineDetail'].get('ItemRef'):
                    item_qb_id = qb_line['SalesItemLineDetail']['ItemRef']['value']
                    product = self.product_repository.find_by_quickbooks_item_id(item_qb_id)
                    if product:
                        line_item_data['product_id'] = product.id
                
                # Create line item using repository
                self.invoice_line_item_repository.create(line_item_data)
    
    def _find_or_create_job_for_qb_transaction(self, qb_transaction: Dict[str, Any]) -> Job:
        """Find or create a job for a QuickBooks transaction"""
        # Try to find contact first
        contact = None
        if qb_transaction.get('CustomerRef'):
            customer_qb_id = qb_transaction['CustomerRef']['value']
            contact = self.contact_repository.find_by_quickbooks_customer_id(customer_qb_id)
        
        if not contact:
            # Create a placeholder contact
            contact_data = {
                'first_name': qb_transaction.get('CustomerRef', {}).get('name', 'Unknown'),
                'customer_type': 'customer'
            }
            contact = self.contact_repository.create(contact_data)
        
        # Find or create property
        property = self.property_repository.find_by_contact_id(contact.id)
        if not property:
            # Extract address from billing address if available
            bill_addr = qb_transaction.get('BillAddr', {})
            address_parts = []
            if bill_addr.get('Line1'):
                address_parts.append(bill_addr['Line1'])
            if bill_addr.get('City'):
                address_parts.append(bill_addr['City'])
            if bill_addr.get('CountrySubDivisionCode'):
                address_parts.append(bill_addr['CountrySubDivisionCode'])
            
            address = ', '.join(address_parts) if address_parts else 'Unknown Address'
            
            property_data = {
                'contact_id': contact.id,
                'address': address
            }
            property = self.property_repository.create(property_data)
        
        # Create job
        doc_number = qb_transaction.get('DocNumber', '')
        description = f"QuickBooks Import - {qb_transaction.get('TxnType', 'Transaction')} #{doc_number}"
        
        job_data = {
            'property_id': property.id,
            'description': description,
            'status': 'Active'
        }
        job = self.job_repository.create(job_data)
        
        return job
    
    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Normalize phone number to match CRM format"""
        if not phone:
            return None
        
        # Remove all non-digits
        digits = ''.join(filter(str.isdigit, phone))
        
        # Add country code if missing
        if len(digits) == 10:
            digits = '1' + digits
        
        # Format as +1XXXXXXXXXX
        if len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        
        return None  # Invalid format
    
    def _record_sync(self, entity_type: str, entity_id: str, 
                    local_id: int, local_table: str, sync_version: str):
        """Record a sync operation"""
        # First try to find by entity_id (primary lookup)
        sync = self.quickbooks_sync_repository.find_by_entity_id(entity_id)
        
        # Build sync data
        sync_data = {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'local_id': local_id,
            'local_table': local_table,
            'sync_version': sync_version,
            'last_synced': datetime.utcnow(),
            'sync_status': 'synced'
        }
        
        # Create or update sync record using repository
        if not sync:
            sync = self.quickbooks_sync_repository.create(sync_data)
        else:
            sync = self.quickbooks_sync_repository.update(sync, sync_data)
    
    def update_contact_financial_summary(self, contact: Contact):
        """Update contact's financial summary from invoices"""
        invoices = self.invoice_repository.find_by_contact_id(contact.id)
        
        total_sales = Decimal('0')
        outstanding = Decimal('0')
        
        for invoice in invoices:
            total_sales += invoice.total_amount
            outstanding += invoice.balance_due
        
        # Calculate average days to pay from paid invoices
        paid_invoices = [inv for inv in invoices if inv.payment_status == 'paid' and hasattr(inv, 'paid_date') and inv.paid_date]
        average_days_to_pay = None
        if paid_invoices:
            total_days = 0
            for inv in paid_invoices:
                days_to_pay = (inv.paid_date.date() - inv.invoice_date).days
                total_days += days_to_pay
            average_days_to_pay = total_days // len(paid_invoices)
        
        # Update contact using repository
        contact_data = {
            'total_sales': total_sales,
            'outstanding_balance': outstanding
        }
        if average_days_to_pay is not None:
            contact_data['average_days_to_pay'] = average_days_to_pay
            
        self.contact_repository.update(contact, contact_data)