# QuickBooks Integration Plan

## Overview
Integrate QuickBooks Online API to enrich Attack-a-Crack CRM with real financial data, customer information, products/services, and automated quote/invoice workflows.

## Business Value
- **Unified Customer Data**: Match phone/text conversations with paying customers
- **Real Products/Services**: Use actual QB items instead of manual entry
- **Automated Workflows**: Sync quotes/invoices bidirectionally
- **Revenue Insights**: Connect campaign performance to actual revenue
- **Customer Segmentation**: Identify high-value customers for targeted campaigns

## Technical Implementation

### Phase 1: Authentication & Connection (Week 1)
**Goal**: Establish secure QuickBooks Online API connection

#### 1.1 OAuth 2.0 Setup
```python
# config.py additions
QUICKBOOKS_CLIENT_ID = os.getenv('QUICKBOOKS_CLIENT_ID')
QUICKBOOKS_CLIENT_SECRET = os.getenv('QUICKBOOKS_CLIENT_SECRET')
QUICKBOOKS_REDIRECT_URI = os.getenv('QUICKBOOKS_REDIRECT_URI', 'http://localhost:5000/auth/quickbooks/callback')
QUICKBOOKS_SANDBOX = os.getenv('QUICKBOOKS_SANDBOX', 'True').lower() == 'true'
```

#### 1.2 New Database Models
```python
# crm_database.py additions
class QuickBooksAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(50), unique=True, nullable=False)  # QB Company ID
    access_token = db.Column(db.Text, nullable=False)  # Encrypted
    refresh_token = db.Column(db.Text, nullable=False)  # Encrypted
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class QuickBooksSync(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)  # 'customer', 'item', 'invoice', etc.
    entity_id = db.Column(db.String(50), nullable=False)  # QB entity ID
    local_id = db.Column(db.Integer, nullable=True)  # Local CRM entity ID
    sync_version = db.Column(db.String(50), nullable=True)  # QB SyncToken
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)
    sync_status = db.Column(db.String(20), default='pending')  # 'pending', 'synced', 'error'
    error_message = db.Column(db.Text, nullable=True)
```

#### 1.3 QuickBooks Service
```python
# services/quickbooks_service.py
class QuickBooksService:
    def __init__(self):
        self.base_url = "https://sandbox-quickbooks.api.intuit.com" if QUICKBOOKS_SANDBOX else "https://quickbooks.api.intuit.com"
        
    def get_authorization_url(self) -> str:
        """Generate OAuth authorization URL"""
        
    def exchange_code_for_tokens(self, code: str, state: str) -> dict:
        """Exchange authorization code for access/refresh tokens"""
        
    def refresh_access_token(self) -> bool:
        """Refresh expired access token"""
        
    def make_api_request(self, endpoint: str, method: str = 'GET', data: dict = None) -> dict:
        """Make authenticated API request to QuickBooks"""
```

#### 1.4 Auth Routes
```python
# routes/auth_routes.py
@auth_bp.route('/auth/quickbooks')
def quickbooks_auth():
    """Redirect to QuickBooks OAuth"""
    
@auth_bp.route('/auth/quickbooks/callback')
def quickbooks_callback():
    """Handle QuickBooks OAuth callback"""
```

### Phase 2: Customer Data Sync (Week 2)
**Goal**: Match CRM contacts with QuickBooks customers

#### 2.1 Customer Import
- Fetch all QB customers via API
- Match by phone number (primary) and email (secondary)
- Enrich CRM contacts with QB customer data
- Handle duplicate customers

#### 2.2 Enhanced Contact Model
```python
# crm_database.py - enhance existing Contact model
class Contact(db.Model):
    # ... existing fields ...
    
    # QuickBooks integration fields
    quickbooks_customer_id = db.Column(db.String(50), nullable=True, unique=True)
    quickbooks_sync_token = db.Column(db.String(50), nullable=True)  # For updates
    customer_type = db.Column(db.String(20), nullable=True)  # 'prospect', 'customer', 'vendor'
    payment_terms = db.Column(db.String(50), nullable=True)  # Net 30, etc.
    credit_limit = db.Column(db.Numeric(10, 2), nullable=True)
    tax_exempt = db.Column(db.Boolean, default=False)
    
    # Financial summary (calculated from QB)
    total_sales = db.Column(db.Numeric(10, 2), default=0)
    outstanding_balance = db.Column(db.Numeric(10, 2), default=0)
    last_payment_date = db.Column(db.DateTime, nullable=True)
    average_days_to_pay = db.Column(db.Integer, nullable=True)
    
    quickbooks_syncs = db.relationship('QuickBooksSync', backref='contact', lazy=True,
                                     foreign_keys='QuickBooksSync.local_id')
```

#### 2.3 Customer Sync Service
```python
# services/quickbooks_sync_service.py
class QuickBooksSyncService:
    def sync_customers(self) -> dict:
        """Sync all customers from QuickBooks"""
        
    def match_contact_to_customer(self, contact: Contact) -> dict:
        """Match CRM contact to QB customer"""
        
    def create_customer_from_contact(self, contact: Contact) -> dict:
        """Create new QB customer from CRM contact"""
        
    def update_contact_from_customer(self, contact: Contact, qb_customer: dict):
        """Update CRM contact with QB customer data"""
```

### Phase 3: Products & Services (Week 3)
**Goal**: Import QB items as CRM products/services

#### 3.1 New Product Models
```python
# crm_database.py
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # QuickBooks fields
    quickbooks_item_id = db.Column(db.String(50), unique=True, nullable=True)
    item_type = db.Column(db.String(20), nullable=False)  # 'service', 'inventory', 'non_inventory'
    
    # Pricing
    unit_price = db.Column(db.Numeric(10, 2), nullable=True)
    cost = db.Column(db.Numeric(10, 2), nullable=True)
    
    # Inventory tracking
    quantity_on_hand = db.Column(db.Integer, nullable=True)
    reorder_point = db.Column(db.Integer, nullable=True)
    
    # Tax and accounting
    taxable = db.Column(db.Boolean, default=True)
    income_account = db.Column(db.String(100), nullable=True)
    expense_account = db.Column(db.String(100), nullable=True)
    
    # Status
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    quote_items = db.relationship('QuoteItem', backref='product', lazy=True)
```

#### 3.2 Quote/Invoice Integration
```python
# crm_database.py - enhance existing models
class Quote(db.Model):
    # ... existing fields ...
    
    # QuickBooks integration
    quickbooks_estimate_id = db.Column(db.String(50), nullable=True, unique=True)
    quickbooks_sync_token = db.Column(db.String(50), nullable=True)
    
    # Enhanced financial fields
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    
    # Terms and conditions
    payment_terms = db.Column(db.String(50), nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)
    
    quote_items = db.relationship('QuoteItem', backref='quote', lazy=True, cascade="all, delete-orphan")

class QuoteItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    
    # Item details
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(10, 2), default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    
    # QB fields
    quickbooks_line_id = db.Column(db.String(50), nullable=True)

class Invoice(db.Model):
    # ... existing fields ...
    
    # QuickBooks integration
    quickbooks_invoice_id = db.Column(db.String(50), nullable=True, unique=True)
    quickbooks_sync_token = db.Column(db.String(50), nullable=True)
    
    # Link to quote
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=True)
    
    # Enhanced financial fields
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    balance_due = db.Column(db.Numeric(10, 2), default=0)
    
    # Payment tracking
    payment_status = db.Column(db.String(20), default='unpaid')  # 'unpaid', 'partial', 'paid', 'overdue'
    paid_date = db.Column(db.DateTime, nullable=True)
    
    invoice_items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade="all, delete-orphan")

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    
    # Item details (same structure as QuoteItem)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(10, 2), default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    
    # QB fields
    quickbooks_line_id = db.Column(db.String(50), nullable=True)
```

### Phase 4: Bidirectional Workflows (Week 4)
**Goal**: Automated quote/invoice creation and sync

#### 4.1 CRM → QuickBooks
- Create QB estimates from CRM quotes
- Convert estimates to invoices
- Send invoices via QB (email/PDF)
- Track payment status

#### 4.2 QuickBooks → CRM
- Import existing estimates/invoices
- Sync payment updates
- Update contact financial summaries
- Trigger follow-up workflows

#### 4.3 Webhook Integration
```python
# New webhook handler for QB updates
@app.route('/webhooks/quickbooks', methods=['POST'])
def quickbooks_webhook():
    """Handle QuickBooks webhook notifications"""
    # Verify webhook signature
    # Queue background task for processing
    # Update local data accordingly
```

### Phase 5: Advanced Features (Week 5+)
**Goal**: Leverage integrated data for business insights

#### 5.1 Customer Segmentation
- High-value customers (>$X annual revenue)
- Payment behavior (fast pay vs. slow pay)
- Service frequency patterns
- Geographic revenue concentration

#### 5.2 Campaign Integration
- Exclude customers with outstanding balances
- Target high-value customers for upsells
- Seasonal campaign timing based on payment patterns
- ROI tracking: campaigns → quotes → invoices → revenue

#### 5.3 Financial Analytics
- Revenue forecasting from quote pipeline
- Payment prediction models
- Profit margin analysis by service type
- Customer lifetime value calculations

## Data Flow Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   QuickBooks    │◄──►│  Attack-a-Crack │◄──►│   OpenPhone     │
│     Online      │    │      CRM        │    │      API        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │ Customers             │ Conversations         │ Messages
        │ Items/Services        │ Contacts              │ Calls
        │ Estimates/Invoices    │ Quotes/Jobs           │ Activities
        │ Payments              │ Appointments          │ Webhooks
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                    ┌─────────────────┐
                    │   Background    │
                    │   Processing    │
                    │  (Celery/Redis) │
                    └─────────────────┘
```

## Security Considerations

### 1. Token Management
- Encrypt OAuth tokens in database
- Implement token rotation
- Secure storage of client secrets
- API request rate limiting

### 2. Data Privacy
- PCI compliance for payment data
- Customer data access controls
- Audit logging for financial operations
- Secure webhook verification

### 3. Error Handling
- Graceful API failure handling
- Data consistency checks
- Transaction rollback capabilities
- Sync conflict resolution

## Implementation Checklist

### Prerequisites
- [ ] QuickBooks Developer Account
- [ ] OAuth 2.0 application registration
- [ ] SSL certificate for webhook endpoints
- [ ] Database backup strategy

### Phase 1: Authentication
- [ ] OAuth flow implementation
- [ ] Token storage and encryption
- [ ] Connection testing interface
- [ ] Error handling and logging

### Phase 2: Customer Sync
- [ ] Customer import functionality
- [ ] Phone/email matching logic
- [ ] Contact enrichment workflows
- [ ] Duplicate handling procedures

### Phase 3: Products & Financial
- [ ] Product/service import
- [ ] Quote/invoice model updates
- [ ] Line item management
- [ ] Tax calculation integration

### Phase 4: Workflows
- [ ] CRM → QB sync processes
- [ ] QB → CRM update handling
- [ ] Webhook endpoint security
- [ ] Background job processing

### Phase 5: Analytics
- [ ] Customer segmentation logic
- [ ] Financial reporting dashboards
- [ ] Campaign ROI tracking
- [ ] Performance metrics

## Success Metrics

### Technical Metrics
- API response times < 500ms
- Sync accuracy > 99.5%
- Zero data loss incidents
- 99.9% uptime for webhooks

### Business Metrics
- 100% customer data coverage
- 50% reduction in manual quote entry
- 30% improvement in payment collection
- 25% increase in campaign ROI tracking

## Risk Assessment

### High Risk
- **Data corruption during sync**: Implement comprehensive testing
- **OAuth token expiration**: Automated refresh mechanisms
- **API rate limit exceeded**: Intelligent queuing and throttling

### Medium Risk
- **Customer data mismatches**: Manual review workflows
- **Duplicate record creation**: Robust duplicate detection
- **Webhook delivery failures**: Retry mechanisms

### Low Risk
- **Minor sync delays**: Acceptable for non-critical updates
- **QB API version changes**: Backward compatibility planning
- **Network connectivity issues**: Standard retry logic

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| 1 | Week 1 | OAuth integration, authentication flows |
| 2 | Week 2 | Customer sync, contact enrichment |
| 3 | Week 3 | Products import, enhanced financial models |
| 4 | Week 4 | Bidirectional workflows, webhooks |
| 5 | Week 5+ | Advanced analytics, customer segmentation |

**Total Estimated Effort**: 4-5 weeks for full implementation
**MVP Timeline**: 2-3 weeks for basic sync functionality

## Dependencies

### External
- QuickBooks Online subscription (business user)
- Developer app approval (if using production)
- SSL certificate for webhooks

### Internal
- Database migration capabilities
- Background job processing (Celery)
- Error monitoring and alerting
- Data backup and recovery procedures

---

*This plan integrates with the existing CRM architecture and follows established patterns for service integration and data management.*