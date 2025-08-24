# crm_database.py

from extensions import db
from datetime import datetime, time, date, timedelta
from utils.datetime_utils import utc_now
from enum import Enum
import json

# --- NEW: User Model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # Increased size for modern hash algorithms
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='marketer')  # 'admin' or 'marketer'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    last_login = db.Column(db.DateTime)
    
    # Legacy OpenPhone field - keeping for backward compatibility
    openphone_user_id = db.Column(db.String(100), unique=True, nullable=True)
    
    # Flask-Login required properties
    def is_authenticated(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_admin(self):
        return self.role == 'admin'

# --- NEW: InviteToken Model ---
class InviteToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='marketer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    created_by = db.relationship('User', backref='sent_invites')

# --- NEW: PhoneNumber Model ---
class PhoneNumber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True)
    phone_number = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

# --- ENHANCED: Conversation Model ---
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True, nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    
    # Conversation details
    name = db.Column(db.String(200), nullable=True)  # Display name
    participants = db.Column(db.String(500), nullable=True)  # Comma-separated phone numbers
    phone_number_id = db.Column(db.String(100), nullable=True)  # Associated OpenPhone number
    
    # Activity tracking
    last_activity_at = db.Column(db.DateTime, nullable=True)  # Should be set based on actual activity
    last_activity_type = db.Column(db.String(20), nullable=True)  # 'message' or 'call'
    last_activity_id = db.Column(db.String(100), nullable=True)  # OpenPhone activity ID
    
    activities = db.relationship('Activity', backref='conversation', lazy=True, cascade="all, delete-orphan")

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True, unique=True)
    contact_metadata = db.Column(db.JSON, nullable=True)  # For flexible data storage
    
    # CSV Import tracking (keeping legacy field for backward compatibility)
    csv_import_id = db.Column(db.Integer, db.ForeignKey('csv_import.id'), nullable=True)
    import_source = db.Column(db.String(100), nullable=True)
    imported_at = db.Column(db.DateTime, nullable=True)
    
    # NEW: Many-to-many relationship with CSV imports
    csv_imports = db.relationship('CSVImport', secondary='contact_csv_import', back_populates='contacts', lazy=True)
    
    # QuickBooks integration fields
    quickbooks_customer_id = db.Column(db.String(50), nullable=True, unique=True)
    quickbooks_sync_token = db.Column(db.String(50), nullable=True)  # For updates
    customer_type = db.Column(db.String(20), nullable=True, default='prospect')  # 'prospect', 'customer'
    payment_terms = db.Column(db.String(50), nullable=True)  # Net 30, etc.
    credit_limit = db.Column(db.Numeric(10, 2), nullable=True)
    tax_exempt = db.Column(db.Boolean, default=False)
    
    # Financial summary (calculated from QB)
    total_sales = db.Column(db.Numeric(10, 2), default=0)
    outstanding_balance = db.Column(db.Numeric(10, 2), default=0)
    last_payment_date = db.Column(db.DateTime, nullable=True)
    average_days_to_pay = db.Column(db.Integer, nullable=True)
    
    # Production-required fields
    lead_source = db.Column(db.String(100), nullable=True)  # e.g., 'website', 'referral', 'cold-call'
    customer_since = db.Column(db.Date, nullable=True)  # Date when prospect became customer
    
    properties = db.relationship('Property', backref='contact', lazy=True, cascade="all, delete-orphan")
    appointments = db.relationship('Appointment', backref='contact', lazy=True, cascade="all, delete-orphan")
    # A contact can now have multiple conversations
    conversations = db.relationship('Conversation', backref='contact', lazy=True, cascade="all, delete-orphan")

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    property_type = db.Column(db.String(50), nullable=True)  # e.g., 'residential', 'commercial', 'industrial'
    jobs = db.relationship('Job', backref='property', lazy=True, cascade="all, delete-orphan")

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Active')
    completed_at = db.Column(db.DateTime, nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    quotes = db.relationship('Quote', backref='job', lazy=True, cascade="all, delete-orphan")
    invoices = db.relationship('Invoice', backref='job', lazy=True, cascade="all, delete-orphan")
    # Add relationship to Appointment if it's not already there implicitly
    # appointments = db.relationship('Appointment', backref='job', lazy=True) # This would be on Job if Appointment had job_id

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    google_calendar_event_id = db.Column(db.String(200), nullable=True)
    
    # ADDED THIS LINE: Foreign key to Job model
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=True) # Made nullable as not all appts might have a job
    job = db.relationship('Job', backref='appointments_rel') # Define relationship

class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # QuickBooks fields
    quickbooks_item_id = db.Column(db.String(50), unique=True, nullable=True)
    quickbooks_sync_token = db.Column(db.String(50), nullable=True)
    item_type = db.Column(db.String(20), nullable=False, default='service')  # 'service', 'inventory', 'non_inventory'
    
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

# Keep alias for backward compatibility
ProductService = Product

class QuoteLineItem(db.Model):
    __tablename__ = 'quote_line_item'
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
    
    product = db.relationship('Product', backref='quote_items')

class Quote(db.Model):
    __tablename__ = 'quote'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='Draft')
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    
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
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    line_items = db.relationship('QuoteLineItem', backref='quote', lazy=True, cascade="all, delete-orphan")

class Invoice(db.Model):
    __tablename__ = 'invoice'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='Draft')
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    
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
    
    # Dates
    invoice_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    
    # Payment tracking
    payment_status = db.Column(db.String(20), default='unpaid')  # 'unpaid', 'partial', 'paid', 'overdue'
    paid_date = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    quote = db.relationship('Quote', backref='invoices')
    invoice_items = db.relationship('InvoiceLineItem', backref='invoice', lazy=True, cascade="all, delete-orphan")

class InvoiceLineItem(db.Model):
    __tablename__ = 'invoice_line_item'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    
    # Item details
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(10, 2), default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    
    # QB fields
    quickbooks_line_id = db.Column(db.String(50), nullable=True)
    
    product = db.relationship('Product', backref='invoice_items')

# --- ENHANCED: Activity Model (Unified Communication Model) ---
class Activity(db.Model):
    # Core fields
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=True)
    
    # Activity details
    activity_type = db.Column(db.String(20))  # 'call', 'message', 'voicemail', 'email'
    direction = db.Column(db.String(10))  # 'incoming', 'outgoing'
    status = db.Column(db.String(50))  # 'answered', 'missed', 'delivered', 'completed', etc.
    
    # Participants
    from_number = db.Column(db.String(20), nullable=True)
    to_numbers = db.Column(db.JSON, nullable=True)  # Array for multiple recipients
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    phone_number_id = db.Column(db.String(100), nullable=True)  # OpenPhone number used
    
    # Message content
    body = db.Column(db.Text, nullable=True)
    media_urls = db.Column(db.JSON, nullable=True)  # Array of media attachment URLs
    
    # Email-specific fields
    email_from = db.Column(db.String(120), nullable=True)
    email_to = db.Column(db.JSON, nullable=True)  # Array for multiple recipients
    email_cc = db.Column(db.JSON, nullable=True)
    email_bcc = db.Column(db.JSON, nullable=True)
    email_subject = db.Column(db.String(200), nullable=True)
    email_thread_id = db.Column(db.String(100), nullable=True)
    smartlead_id = db.Column(db.String(100), nullable=True)
    
    # Call-specific fields
    duration_seconds = db.Column(db.Integer, nullable=True)
    recording_url = db.Column(db.String(500), nullable=True)
    voicemail_url = db.Column(db.String(500), nullable=True)
    answered_at = db.Column(db.DateTime, nullable=True)
    answered_by = db.Column(db.String(100), nullable=True)  # User ID
    completed_at = db.Column(db.DateTime, nullable=True)
    initiated_by = db.Column(db.String(100), nullable=True)  # User ID
    forwarded_from = db.Column(db.String(100), nullable=True)
    forwarded_to = db.Column(db.String(100), nullable=True)
    
    # AI-generated content (stored in same model for unified view)
    ai_summary = db.Column(db.Text, nullable=True)  # Call summary
    ai_next_steps = db.Column(db.Text, nullable=True)  # Recommended actions
    ai_transcript = db.Column(db.JSON, nullable=True)  # Call transcript dialogue
    ai_content_status = db.Column(db.String(50), nullable=True)  # 'pending', 'completed', 'failed'
    
    # SMS Metrics tracking
    activity_metadata = db.Column(db.JSON, nullable=True)  # For bounce tracking and other metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    media_attachments = db.relationship('MediaAttachment', backref='activity', lazy=True, cascade="all, delete-orphan")

class MediaAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # The foreign key now points to the 'activity' table
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    local_path = db.Column(db.String(500), nullable=True)
    content_type = db.Column(db.String(100), nullable=True)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

# --- NEW: WebhookEvent Model (for reliability) ---
class WebhookEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(100), unique=True)  # OpenPhone event ID
    event_type = db.Column(db.String(50))  # 'message.new', 'call.completed', etc.
    api_version = db.Column(db.String(10))  # 'v1', 'v2', 'v4'
    payload = db.Column(db.JSON)  # Full webhook payload for reprocessing
    processed = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- NEW: Campaign Model (Enhanced) ---
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='draft')  # 'draft', 'running', 'paused', 'complete', 'scheduled'
    template_a = db.Column(db.Text)  # A/B test variant A
    template_b = db.Column(db.Text, nullable=True)  # A/B test variant B
    quiet_hours_start = db.Column(db.Time, default=time(20, 0))  # 8 PM
    quiet_hours_end = db.Column(db.Time, default=time(9, 0))  # 9 AM
    on_existing_contact = db.Column(db.String(50), default='ignore')  # 'ignore', 'flag_for_review', 'adapt_script'
    
    # NEW: Enhanced campaign features
    campaign_type = db.Column(db.String(20), default='blast')  # 'blast', 'automated', 'ab_test'
    audience_type = db.Column(db.String(20), default='mixed')  # 'cold', 'customer', 'mixed'  
    daily_limit = db.Column(db.Integer, default=125)
    business_hours_only = db.Column(db.Boolean, default=True)
    ab_config = db.Column(db.JSON, nullable=True)  # A/B test configuration
    channel = db.Column(db.String(10), default='sms')  # 'sms', 'email'
    
    # List management
    list_id = db.Column(db.Integer, db.ForeignKey('campaign_list.id'), nullable=True)
    
    # Contact history handling
    adapt_script_template = db.Column(db.Text, nullable=True)  # Template for previously contacted
    days_between_contacts = db.Column(db.Integer, default=30)  # Minimum days before recontacting
    
    # Phase 3C: Campaign Scheduling fields
    scheduled_at = db.Column(db.DateTime, nullable=True)  # When the campaign should run
    timezone = db.Column(db.String(50), default='UTC')  # Timezone for scheduling
    recurrence_pattern = db.Column(db.JSON, nullable=True)  # Recurring campaign configuration
    next_run_at = db.Column(db.DateTime, nullable=True)  # Next execution time for recurring campaigns
    is_recurring = db.Column(db.Boolean, default=False)  # Whether this is a recurring campaign
    parent_campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True)  # For duplicated campaigns
    archived = db.Column(db.Boolean, default=False)  # Whether the campaign is archived
    archived_at = db.Column(db.DateTime, nullable=True)  # When the campaign was archived
    
    # Relationships
    memberships = db.relationship('CampaignMembership', backref='campaign', lazy=True, cascade="all, delete-orphan")
    parent_campaign = db.relationship('Campaign', remote_side=[id], backref=db.backref('child_campaigns', lazy='dynamic'))

# --- NEW: CampaignMembership Model (Enhanced) ---
class CampaignMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    status = db.Column(db.String(50), default='pending')  # 'pending', 'sent', 'failed', 'replied_positive', 'replied_negative', 'suppressed'
    variant_sent = db.Column(db.String(1), nullable=True)  # 'A' or 'B'
    sent_at = db.Column(db.DateTime, nullable=True)
    sent_activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)
    reply_activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)
    
    # NEW: Enhanced tracking fields
    pre_send_flags = db.Column(db.JSON, nullable=True)  # Flags detected before sending
    override_action = db.Column(db.String(20), nullable=True)  # 'skip', 'modify_script', 'flag_review'
    response_sentiment = db.Column(db.String(20), nullable=True)  # 'positive', 'negative', 'neutral'
    message_sent = db.Column(db.Text, nullable=True)  # Actual message sent (for A/B tracking)
    
    # Contact history tracking
    previous_contact_date = db.Column(db.DateTime, nullable=True)
    previous_contact_type = db.Column(db.String(50), nullable=True)  # 'sms', 'email', 'call'
    previous_response = db.Column(db.String(50), nullable=True)  # 'positive', 'negative', 'no_response'
    script_adapted = db.Column(db.Boolean, default=False)
    
    # SMS Metrics tracking
    membership_metadata = db.Column(db.JSON, nullable=True)  # For bounce tracking and other metadata
    
    contact = db.relationship('Contact', backref='campaign_memberships')
    sent_activity = db.relationship('Activity', foreign_keys=[sent_activity_id], backref='sent_campaign_memberships')
    reply_activity = db.relationship('Activity', foreign_keys=[reply_activity_id], backref='reply_campaign_memberships')

# --- NEW: ContactFlag Model (for opt-outs and compliance) ---
class ContactFlag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    flag_type = db.Column(db.String(50), nullable=False)  # 'opted_out', 'office_number', 'recently_texted', 'do_not_contact'
    flag_reason = db.Column(db.Text, nullable=True)  # Human readable reason
    applies_to = db.Column(db.String(20), default='sms')  # 'sms', 'email', 'both'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # For temporary flags like 'recently_texted'
    created_by = db.Column(db.String(100), nullable=True)  # Who/what created this flag
    
    contact = db.relationship('Contact', backref='flags')

# --- CSV Import Tracking ---
class CSVImport(db.Model):
    __tablename__ = 'csv_import'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    imported_by = db.Column(db.String(100), nullable=True)
    total_rows = db.Column(db.Integer, nullable=True)
    successful_imports = db.Column(db.Integer, nullable=True)
    failed_imports = db.Column(db.Integer, nullable=True)
    import_type = db.Column(db.String(50), nullable=True)  # 'contacts', 'properties', etc.
    import_metadata = db.Column(db.JSON, nullable=True)
    
    # Update relationship to use association table
    contacts = db.relationship('Contact', secondary='contact_csv_import', back_populates='csv_imports', lazy=True)

# --- NEW: Association table for many-to-many relationship between contacts and CSV imports ---
class ContactCSVImport(db.Model):
    __tablename__ = 'contact_csv_import'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id', ondelete='CASCADE'), nullable=False)
    csv_import_id = db.Column(db.Integer, db.ForeignKey('csv_import.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_new = db.Column(db.Boolean, default=True)  # Was this a new contact or existing?
    data_updated = db.Column(db.JSON, nullable=True)  # Track what fields were updated
    
    __table_args__ = (
        db.UniqueConstraint('contact_id', 'csv_import_id', name='unique_contact_csv_import'),
    )

# --- Campaign List Management ---
class CampaignList(db.Model):
    __tablename__ = 'campaign_list'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100), nullable=True)
    filter_criteria = db.Column(db.JSON, nullable=True)  # Store dynamic filter rules
    is_dynamic = db.Column(db.Boolean, default=False)  # Dynamic lists update automatically
    
    members = db.relationship('CampaignListMember', backref='list', lazy=True, cascade="all, delete-orphan")
    campaigns = db.relationship('Campaign', backref='list', lazy=True)

class CampaignListMember(db.Model):
    __tablename__ = 'campaign_list_member'
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('campaign_list.id', ondelete='CASCADE'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id', ondelete='CASCADE'), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    added_by = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='active')  # 'active', 'removed', 'suppressed'
    import_metadata = db.Column(db.JSON, nullable=True)
    
    contact = db.relationship('Contact', backref='list_memberships')
    
    __table_args__ = (
        db.UniqueConstraint('list_id', 'contact_id', name='unique_list_member'),
    )

# --- QuickBooks Integration Models ---
class QuickBooksAuth(db.Model):
    __tablename__ = 'quickbooks_auth'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(50), unique=True, nullable=False)  # QB Company ID
    access_token = db.Column(db.Text, nullable=False)  # Encrypted
    refresh_token = db.Column(db.Text, nullable=False)  # Encrypted
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class QuickBooksSync(db.Model):
    __tablename__ = 'quickbooks_sync'
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)  # 'customer', 'item', 'invoice', 'estimate'
    entity_id = db.Column(db.String(50), nullable=False)  # QB entity ID
    local_id = db.Column(db.Integer, nullable=True)  # Local CRM entity ID
    local_table = db.Column(db.String(50), nullable=True)  # Which local table (contact, product, invoice, quote)
    sync_version = db.Column(db.String(50), nullable=True)  # QB SyncToken
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)
    sync_status = db.Column(db.String(20), default='pending')  # 'pending', 'synced', 'error'
    error_message = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('entity_type', 'entity_id', name='unique_qb_entity'),
    )


class Todo(db.Model):
    """Todo items for task management"""
    __tablename__ = 'todos'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    due_date = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # User association (optional for now to avoid migration issues)
    user_id = db.Column(db.Integer, nullable=True)
    # Note: Foreign key relationship commented out to avoid migration issues
    # user = db.relationship('User', backref='todos')
    
    def __repr__(self):
        return f'<Todo {self.id}: {self.title}>'
    
    def mark_complete(self):
        """Mark todo as completed"""
        self.is_completed = True
        self.completed_at = utc_now()
        
    def mark_incomplete(self):
        """Mark todo as incomplete"""
        self.is_completed = False
        self.completed_at = None


# --- Campaign Template Models ---

class TemplateCategory(str, Enum):
    """Categories for campaign templates"""
    PROMOTIONAL = 'promotional'
    REMINDER = 'reminder'
    FOLLOW_UP = 'follow_up'
    NOTIFICATION = 'notification'
    CUSTOM = 'custom'


class TemplateStatus(str, Enum):
    """Status options for campaign templates"""
    DRAFT = 'draft'
    APPROVED = 'approved'
    ACTIVE = 'active'
    ARCHIVED = 'archived'


class CampaignTemplate(db.Model):
    """Campaign template for SMS messages"""
    __tablename__ = 'campaign_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False, default=TemplateCategory.CUSTOM)
    
    # Variables stored as JSON array
    variables = db.Column(db.JSON, default=list)
    
    # Status management
    status = db.Column(db.String(20), nullable=False, default=TemplateStatus.DRAFT)
    
    # Version management
    version = db.Column(db.Integer, default=1, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('campaign_templates.id'), nullable=True)
    
    # Usage tracking
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    last_used_at = db.Column(db.DateTime)
    
    # Approval tracking
    approved_by = db.Column(db.String(100))
    approved_at = db.Column(db.DateTime)
    archived_at = db.Column(db.DateTime)
    activated_at = db.Column(db.DateTime)
    
    # Audit fields
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent_template = db.relationship('CampaignTemplate', remote_side=[id], backref='versions')
    
    def __repr__(self):
        return f'<CampaignTemplate {self.id}: {self.name} v{self.version}>'
    
    def to_dict(self):
        """Convert template to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'description': self.description,
            'category': self.category,
            'variables': self.variables or [],
            'status': self.status,
            'version': self.version,
            'parent_id': self.parent_id,
            'is_active': self.is_active,
            'usage_count': self.usage_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class FailedWebhookQueue(db.Model):
    """Failed webhook queue for error recovery and retry management (P1-16)"""
    __tablename__ = 'failed_webhook_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(100), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    original_payload = db.Column(db.JSON, nullable=False)
    error_message = db.Column(db.Text, nullable=False)
    
    # Retry configuration
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    max_retries = db.Column(db.Integer, nullable=False, default=5)
    backoff_multiplier = db.Column(db.DECIMAL(precision=3, scale=1), nullable=False, default=2.0)
    base_delay_seconds = db.Column(db.Integer, nullable=False, default=60)
    
    # Retry timing
    next_retry_at = db.Column(db.DateTime, nullable=True, index=True)
    last_retry_at = db.Column(db.DateTime, nullable=True)
    
    # Resolution tracking
    resolved = db.Column(db.Boolean, nullable=False, default=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<FailedWebhookQueue {self.id}: {self.event_id} ({self.retry_count}/{self.max_retries})>'
    
    def calculate_next_retry_time(self) -> datetime:
        """Calculate next retry time using exponential backoff"""
        from decimal import Decimal
        delay_seconds = self.base_delay_seconds * (Decimal(str(self.backoff_multiplier)) ** self.retry_count)
        return utc_now() + timedelta(seconds=int(delay_seconds))
    
    def is_retry_exhausted(self) -> bool:
        """Check if retry attempts are exhausted"""
        return self.retry_count >= self.max_retries
    
    def can_retry_now(self) -> bool:
        """Check if webhook can be retried now"""
        from utils.datetime_utils import utc_now
        if self.is_retry_exhausted():
            return False
        if self.next_retry_at is None:
            return True
        return utc_now() >= self.next_retry_at
    
    def can_retry_now(self) -> bool:
        """Check if webhook can be retried now"""
        if self.resolved or self.is_retry_exhausted():
            return False
        if self.next_retry_at is None:
            return True
        return utc_now() >= self.next_retry_at


# --- Opt-Out Management ---
class OptOutAudit(db.Model):
    """Audit trail for all opt-out and opt-in events"""
    __tablename__ = 'opt_out_audit'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)  # Store for reference even if contact deleted
    contact_name = db.Column(db.String(100), nullable=True)  # Store for reference
    
    # Event details
    opt_out_method = db.Column(db.String(50), nullable=False)  # 'sms_keyword', 'sms_opt_in', 'manual', 'web_form'
    keyword_used = db.Column(db.String(50), nullable=True)  # The actual keyword that triggered it
    source = db.Column(db.String(100), nullable=True)  # 'webhook', 'api', 'admin_ui', etc.
    
    # Related entities
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True)  # If triggered by campaign response
    message_id = db.Column(db.String(100), nullable=True)  # OpenPhone message ID if applicable
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    contact = db.relationship('Contact', backref='opt_out_audits')
    campaign = db.relationship('Campaign', backref='opt_out_events')
    
    # Indexes for reporting
    __table_args__ = (
        db.Index('idx_opt_out_audit_contact', 'contact_id'),
        db.Index('idx_opt_out_audit_created', 'created_at'),
        db.Index('idx_opt_out_audit_method', 'opt_out_method'),
        db.Index('idx_opt_out_audit_phone', 'phone_number'),
    )


# --- NEW: PhoneValidation Model ---
class PhoneValidation(db.Model):
    """Cache for phone number validation results from NumVerify API"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Phone number and validation result
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    is_valid = db.Column(db.Boolean, nullable=False, default=False)
    
    # Line type information
    line_type = db.Column(db.String(20), nullable=True)  # mobile, landline, voip, etc.
    carrier = db.Column(db.String(100), nullable=True)
    
    # Location information
    country_code = db.Column(db.String(5), nullable=True, index=True)
    country_name = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    
    # Caching metadata
    validation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cached_until = db.Column(db.DateTime, nullable=False, index=True, default=lambda: utc_now() + timedelta(days=30))  # When cache expires
    
    # Raw API response for debugging
    raw_response = db.Column(db.JSON, nullable=True)
    
    # Legacy support (some tests reference these fields)
    api_response = db.Column(db.JSON, nullable=True)  # Alias for raw_response
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # Alias for validation_date
    
    def __repr__(self):
        return f'<PhoneValidation {self.phone_number}: {"valid" if self.is_valid else "invalid"}>'


# --- A/B Testing Models ---
class ABTestResult(db.Model):
    """Track A/B test variant assignments and performance metrics"""
    __tablename__ = 'ab_test_result'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Core assignment data
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False, index=True)
    variant = db.Column(db.String(1), nullable=False, index=True)  # 'A' or 'B'
    assigned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Message sending tracking
    message_sent = db.Column(db.Boolean, default=False, index=True)
    sent_activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    # Engagement tracking
    message_opened = db.Column(db.Boolean, default=False, index=True)
    opened_at = db.Column(db.DateTime, nullable=True)
    
    # Click tracking
    link_clicked = db.Column(db.Boolean, default=False, index=True)
    clicked_link_url = db.Column(db.String(500), nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)
    
    # Response tracking
    response_received = db.Column(db.Boolean, default=False, index=True)
    response_type = db.Column(db.String(20), nullable=True)  # 'positive', 'negative', 'neutral'
    response_activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    campaign = db.relationship('Campaign', backref='ab_test_results')
    contact = db.relationship('Contact', backref='ab_test_assignments')
    sent_activity = db.relationship('Activity', foreign_keys=[sent_activity_id], backref='ab_test_sent_messages')
    response_activity = db.relationship('Activity', foreign_keys=[response_activity_id], backref='ab_test_responses')
    
    # Constraints and indexes
    __table_args__ = (
        db.UniqueConstraint('campaign_id', 'contact_id', name='unique_campaign_contact_assignment'),
        db.Index('idx_ab_test_campaign_variant', 'campaign_id', 'variant'),
        db.Index('idx_ab_test_performance', 'campaign_id', 'variant', 'message_sent', 'response_received'),
        db.Index('idx_ab_test_assigned_at', 'assigned_at'),
    )
    
    def __repr__(self):
        return f'<ABTestResult Campaign:{self.campaign_id} Contact:{self.contact_id} Variant:{self.variant}>'
    
    @property
    def conversion_achieved(self) -> bool:
        """Check if this assignment resulted in a positive conversion"""
        return self.response_received and self.response_type == 'positive'
