# crm_database.py

from extensions import db
from datetime import datetime

# --- NEW: Conversation Model ---
# This table holds the high-level information for each conversation thread.
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True, nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    # Storing participants as a simple comma-separated string for now.
    # For a more advanced system, this could be a separate related table.
    participants = db.Column(db.String(500), nullable=True)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    activities = db.relationship('Activity', backref='conversation', lazy=True, cascade="all, delete-orphan")

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True, unique=True)
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

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    google_calendar_event_id = db.Column(db.String(200), nullable=True)

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

# --- RENAMED and ENHANCED: From Message to Activity ---
class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    openphone_id = db.Column(db.String(100), unique=True, nullable=False)
    
    type = db.Column(db.String(20), nullable=False, default='message') # 'message', 'call', 'voicemail'
    direction = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(50), nullable=True) # e.g., 'answered', 'missed', 'delivered'
    
    body = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Integer, nullable=True)
    recording_url = db.Column(db.String(500), nullable=True)
    voicemail_url = db.Column(db.String(500), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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