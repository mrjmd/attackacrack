# crm_database.py

from extensions import db
from datetime import datetime, time

# --- NEW: User Model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_user_id = db.Column(db.String(100), unique=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(120))

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
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    
    # CSV Import tracking
    csv_import_id = db.Column(db.Integer, db.ForeignKey('csv_import.id'), nullable=True)
    import_source = db.Column(db.String(100), nullable=True)
    imported_at = db.Column(db.DateTime, nullable=True)
    
    properties = db.relationship('Property', backref='contact', lazy=True, cascade="all, delete-orphan")
    appointments = db.relationship('Appointment', backref='contact', lazy=True, cascade="all, delete-orphan")
    # A contact can now have multiple conversations
    conversations = db.relationship('Conversation', backref='contact', lazy=True, cascade="all, delete-orphan")

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
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

class ProductService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)

class QuoteLineItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    product_service_id = db.Column(db.Integer, db.ForeignKey('product_service.id'), nullable=True)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False)
    product_service = db.relationship('ProductService')

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Draft')
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    line_items = db.relationship('QuoteLineItem', backref='quote', lazy=True, cascade="all, delete-orphan")

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Draft')
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)

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
    status = db.Column(db.String(20), default='draft')  # 'draft', 'running', 'paused', 'complete'
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
    
    memberships = db.relationship('CampaignMembership', backref='campaign', lazy=True, cascade="all, delete-orphan")

# --- NEW: CampaignMembership Model (Enhanced) ---
class CampaignMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    status = db.Column(db.String(50), default='pending')  # 'pending', 'sent', 'failed', 'replied_positive', 'replied_negative', 'suppressed'
    variant_sent = db.Column(db.String(1), nullable=True)  # 'A' or 'B'
    sent_at = db.Column(db.DateTime, nullable=True)
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
    
    contact = db.relationship('Contact', backref='campaign_memberships')
    reply_activity = db.relationship('Activity', backref='campaign_reply')

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
    
    contacts = db.relationship('Contact', backref='csv_import', lazy=True)

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
