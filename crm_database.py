# crm_database.py

from extensions import db
from datetime import datetime, time, date, timedelta
from utils.datetime_utils import utc_now
from enum import Enum
import json
from decimal import Decimal
from typing import Optional

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
    
    # Note: The 'properties' relationship is now handled via many-to-many through PropertyContact
    appointments = db.relationship('Appointment', backref='contact', lazy=True, cascade="all, delete-orphan")
    # A contact can now have multiple conversations
    conversations = db.relationship('Conversation', backref='contact', lazy=True, cascade="all, delete-orphan")

# --- Property-Contact Association Table ---
class PropertyContact(db.Model):
    """Association table for many-to-many relationship between Property and Contact"""
    __tablename__ = 'property_contact'
    
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id', ondelete='CASCADE'), nullable=False)
    relationship_type = db.Column(db.String(20), nullable=True)  # 'owner', 'tenant', 'agent', etc.
    ownership_percentage = db.Column(db.Numeric(5, 2), nullable=True)  # For fractional ownership
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    
    # Relationships
    property = db.relationship('Property', backref=db.backref('contact_associations', lazy='dynamic'))
    contact = db.relationship('Contact', backref=db.backref('property_associations', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('property_id', 'contact_id', name='uq_property_contact'),
    )
    
    def __repr__(self):
        return f'<PropertyContact Property:{self.property_id} Contact:{self.contact_id} Type:{self.relationship_type}>'


class Property(db.Model):
    """Enhanced Property model with PropertyRadar fields and many-to-many Contact relationship"""
    __tablename__ = 'property'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic property information
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(2), nullable=True)
    zip_code = db.Column(db.String(10), nullable=True)
    subdivision = db.Column(db.String(100), nullable=True)
    property_type = db.Column(db.String(50), nullable=True)  # 'SFR', 'Condo', 'Townhouse', 'Multi-Family', etc.
    
    # Geographic coordinates
    longitude = db.Column(db.Numeric(10, 7), nullable=True)
    latitude = db.Column(db.Numeric(10, 7), nullable=True)
    
    # Property identifiers
    apn = db.Column(db.String(100), nullable=True, unique=True)  # Assessor Parcel Number
    external_id = db.Column(db.String(100), nullable=True)  # ID from external source
    
    # Property details
    year_built = db.Column(db.Integer, nullable=True)
    square_feet = db.Column(db.Integer, nullable=True)
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Numeric(3, 1), nullable=True)
    
    # Financial fields
    assessed_value = db.Column(db.Numeric(12, 2), nullable=True)
    market_value = db.Column(db.Numeric(12, 2), nullable=True)
    equity_estimate = db.Column(db.Numeric(12, 2), nullable=True)
    last_sale_price = db.Column(db.Numeric(12, 2), nullable=True)
    last_sale_date = db.Column(db.Date, nullable=True)
    purchase_months_since = db.Column(db.Integer, nullable=True)
    
    # PropertyRadar specific fields (legacy naming preserved)
    estimated_value = db.Column(db.Numeric(12, 2), nullable=True)
    estimated_equity = db.Column(db.Numeric(12, 2), nullable=True)
    estimated_equity_percent = db.Column(db.Integer, nullable=True)
    
    # Purchase information
    purchase_date = db.Column(db.Date, nullable=True)
    purchase_price = db.Column(db.Numeric(12, 2), nullable=True)
    
    # Status flags
    owner_occupied = db.Column(db.Boolean, default=False)
    listed_for_sale = db.Column(db.Boolean, default=False)
    listing_status = db.Column(db.String(50), nullable=True)
    foreclosure = db.Column(db.Boolean, default=False)
    foreclosure_status = db.Column(db.String(50), nullable=True)
    high_equity = db.Column(db.Boolean, default=False)
    
    # Owner information
    owner_name = db.Column(db.String(200), nullable=True)
    
    # Mailing address fields (both naming conventions for compatibility)
    mail_address = db.Column(db.String(200), nullable=True)
    mail_city = db.Column(db.String(100), nullable=True)
    mail_state = db.Column(db.String(2), nullable=True)
    mail_zip = db.Column(db.String(10), nullable=True)
    
    mailing_address = db.Column(db.String(200), nullable=True)
    mailing_city = db.Column(db.String(100), nullable=True)
    mailing_state = db.Column(db.String(2), nullable=True)
    mailing_zip = db.Column(db.String(10), nullable=True)
    
    # Metadata
    property_metadata = db.Column(db.JSON, nullable=True)
    import_source = db.Column(db.String(50), nullable=True)  # 'PropertyRadar', 'Manual', etc.
    
    # Legacy field - kept for backward compatibility (will be migrated to PropertyContact)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=True)
    
    # Audit fields
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', backref='property', lazy=True, cascade="all, delete-orphan")
    # Many-to-many relationship with contacts
    contacts = db.relationship(
        'Contact',
        secondary='property_contact',
        backref=db.backref('properties', lazy='dynamic'),
        overlaps="contact_associations,property_associations"
    )
    
    def __repr__(self):
        return f'<Property {self.id}: {self.address}, {self.city} {self.state} {self.zip_code}>'
    
    # Backward compatibility property
    @property
    def contact(self):
        """Returns the primary contact for backward compatibility.
        
        Returns:
            Contact: The primary contact if exists, or first contact, or None
        """
        # First try to find a contact marked as primary
        primary_assoc = self.contact_associations.filter_by(is_primary=True).first()
        if primary_assoc:
            return primary_assoc.contact
        
        # If no primary, return the first contact
        if self.contacts:
            return self.contacts[0]
        
        return None
    
    @property
    def contact_id(self):
        """Returns the primary contact ID for backward compatibility."""
        contact = self.contact
        return contact.id if contact else None
    
    @contact_id.setter
    def contact_id(self, value):
        """
        Sets the primary contact by ID for backward compatibility.
        Creates or updates the PropertyContact association.
        """
        if value is None:
            # Remove all contact associations if setting to None
            PropertyContact.query.filter_by(property_id=self.id).delete()
        else:
            # Check if we already have this contact associated
            existing = PropertyContact.query.filter_by(
                property_id=self.id, 
                contact_id=value
            ).first()
            
            if existing:
                # Make this contact primary, others non-primary
                PropertyContact.query.filter_by(property_id=self.id).update({'is_primary': False})
                existing.is_primary = True
            else:
                # Remove other primary designations
                PropertyContact.query.filter_by(property_id=self.id).update({'is_primary': False})
                # Create new primary association
                new_assoc = PropertyContact(
                    property_id=self.id,
                    contact_id=value,
                    relationship_type='owner',
                    is_primary=True
                )
                db.session.add(new_assoc)
    
    # Utility methods
    @classmethod
    def search_by_address(cls, address):
        """Search properties by address"""
        return cls.query.filter(cls.address.ilike(f'%{address}%')).all()
    
    @classmethod
    def search_by_zip(cls, zip_code):
        """Search properties by zip code"""
        return cls.query.filter_by(zip_code=zip_code).all()
    
    @classmethod
    def search_by_city(cls, city):
        """Search properties by city"""
        return cls.query.filter(cls.city.ilike(f'%{city}%')).all()
    
    def calculate_equity_percentage(self):
        """Calculate equity percentage based on values"""
        if self.estimated_value and self.estimated_equity:
            return int((self.estimated_equity / self.estimated_value) * 100)
        return 0
    
    def is_high_equity(self, threshold=50):
        """Determine if property has high equity"""
        equity_pct = self.calculate_equity_percentage()
        return equity_pct >= threshold
    
    def get_equity_tier(self):
        """Classify equity tier"""
        equity_pct = self.calculate_equity_percentage()
        if equity_pct >= 70:
            return 'high'
        elif equity_pct >= 40:
            return 'medium'
        else:
            return 'low'
    
    def has_valid_coordinates(self):
        """Check if property has valid geographic coordinates"""
        if self.longitude and self.latitude:
            return -180 <= self.longitude <= 180 and -90 <= self.latitude <= 90
        return False
    
    def distance_to(self, other_property):
        """Calculate approximate distance to another property in miles"""
        if not (self.has_valid_coordinates() and other_property.has_valid_coordinates()):
            return None
        
        # Simple haversine formula for distance calculation
        from math import radians, sin, cos, sqrt, atan2
        
        R = 3959  # Earth's radius in miles
        lat1, lon1 = radians(float(self.latitude)), radians(float(self.longitude))
        lat2, lon2 = radians(float(other_property.latitude)), radians(float(other_property.longitude))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    @classmethod
    def bulk_create(cls, properties_data):
        """Bulk create properties for efficient imports"""
        properties = []
        for data in properties_data:
            prop = cls(**data)
            db.session.add(prop)
            properties.append(prop)
        
        db.session.flush()  # Get IDs without committing
        return properties
    
    @classmethod
    def bulk_update(cls, properties, update_data):
        """Bulk update properties"""
        prop_ids = [p.id for p in properties]
        updated = cls.query.filter(cls.id.in_(prop_ids)).update(
            update_data, synchronize_session=False
        )
        db.session.flush()
        return updated

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
    
    # Campaign attribution
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    media_attachments = db.relationship('MediaAttachment', backref='activity', lazy=True, cascade="all, delete-orphan")
    campaign = db.relationship('Campaign', backref=db.backref('activities', lazy='dynamic'))

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


# --- P4-01: Engagement Scoring System Models ---
class EngagementEvent(db.Model):
    """Track individual engagement events for scoring calculation"""
    __tablename__ = 'engagement_events'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Core relationships
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)  # Link to actual message/call
    parent_event_id = db.Column(db.Integer, db.ForeignKey('engagement_events.id'), nullable=True)  # For event chains
    
    # Event details
    event_type = db.Column(db.String(20), nullable=False, index=True)  # 'delivered', 'opened', 'clicked', 'responded', 'converted', 'opted_out', 'bounced'
    event_timestamp = db.Column(db.DateTime, nullable=False, index=True)
    channel = db.Column(db.String(10), nullable=False, index=True)  # 'sms', 'email', 'call'
    
    # Message/Campaign context
    message_id = db.Column(db.String(100), nullable=True, index=True)  # OpenPhone message ID or similar
    campaign_message_variant = db.Column(db.String(1), nullable=True)  # 'A' or 'B' for A/B testing
    
    # Event-specific data
    click_url = db.Column(db.String(500), nullable=True)  # For 'clicked' events
    response_text = db.Column(db.Text, nullable=True)  # For 'responded' events
    response_sentiment = db.Column(db.String(20), nullable=True)  # 'positive', 'negative', 'neutral'
    
    # Conversion tracking
    conversion_type = db.Column(db.String(50), nullable=True)  # 'purchase', 'appointment_booked', 'quote_requested'
    conversion_value = db.Column(db.Numeric(10, 2), nullable=True)  # Monetary value if applicable
    
    # Opt-out tracking
    opt_out_method = db.Column(db.String(50), nullable=True)  # 'keyword', 'link', 'manual'
    opt_out_keyword = db.Column(db.String(20), nullable=True)  # 'STOP', 'UNSUBSCRIBE', etc.
    
    # Metadata and analytics
    event_metadata = db.Column(db.JSON, nullable=True)  # Flexible storage for additional data
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    contact = db.relationship('Contact', backref='engagement_events')
    campaign = db.relationship('Campaign', backref='engagement_events')
    activity = db.relationship('Activity', backref='engagement_events')
    parent_event = db.relationship('EngagementEvent', remote_side=[id], backref='child_events')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_engagement_events_contact_time', 'contact_id', 'event_timestamp'),
        db.Index('idx_engagement_events_campaign_time', 'campaign_id', 'event_timestamp'),
        db.Index('idx_engagement_events_type_time', 'event_type', 'event_timestamp'),
        db.Index('idx_engagement_events_message', 'message_id', 'event_type'),
    )
    
    def __repr__(self):
        return f'<EngagementEvent {self.id}: {self.event_type} for Contact {self.contact_id}>'
    
    @property
    def is_positive_event(self) -> bool:
        """Check if this is a positive engagement event"""
        positive_events = ['opened', 'clicked', 'responded', 'converted']
        return self.event_type in positive_events
    
    @property
    def is_negative_event(self) -> bool:
        """Check if this is a negative engagement event"""
        negative_events = ['opted_out', 'bounced', 'complained']
        return self.event_type in negative_events
    
    @property
    def has_monetary_value(self) -> bool:
        """Check if this event has associated monetary value"""
        return self.conversion_value is not None and self.conversion_value > 0


class EngagementScore(db.Model):
    """Calculated engagement scores for contacts in campaigns"""
    __tablename__ = 'engagement_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Core relationships
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True, index=True)
    
    # Primary scores (0-100 scale)
    overall_score = db.Column(db.Numeric(5, 2), nullable=False, index=True)  # Composite engagement score
    recency_score = db.Column(db.Numeric(5, 2), nullable=False, default=0)  # How recent is engagement
    frequency_score = db.Column(db.Numeric(5, 2), nullable=False, default=0)  # How frequent is engagement
    monetary_score = db.Column(db.Numeric(5, 2), nullable=False, default=0)  # Monetary value contribution
    
    # Advanced scoring components
    engagement_diversity_score = db.Column(db.Numeric(5, 2), nullable=True, default=0)  # Variety of engagement types
    time_decay_score = db.Column(db.Numeric(5, 2), nullable=True, default=0)  # Time-weighted engagement
    negative_events_penalty = db.Column(db.Numeric(5, 2), nullable=True, default=0)  # Penalty for opt-outs, etc.
    
    # Predictive metrics
    engagement_probability = db.Column(db.Numeric(4, 3), nullable=False, default=0)  # 0-1 probability of future engagement
    conversion_probability = db.Column(db.Numeric(4, 3), nullable=True, default=0)  # 0-1 probability of conversion
    churn_risk_score = db.Column(db.Numeric(5, 2), nullable=True, default=0)  # Risk of disengagement
    
    # Percentile rankings (calculated relative to campaign)
    overall_percentile = db.Column(db.Numeric(5, 2), nullable=True)  # Percentile within campaign
    recency_percentile = db.Column(db.Numeric(5, 2), nullable=True)
    frequency_percentile = db.Column(db.Numeric(5, 2), nullable=True)
    monetary_percentile = db.Column(db.Numeric(5, 2), nullable=True)
    
    # Metadata
    score_version = db.Column(db.String(10), nullable=False, default='1.0')  # Algorithm version
    calculation_method = db.Column(db.String(50), nullable=True)  # 'rfm', 'ml_model', 'hybrid'
    confidence_level = db.Column(db.Numeric(4, 3), nullable=True)  # Confidence in score accuracy
    
    # Event statistics (cached for performance)
    total_events_count = db.Column(db.Integer, nullable=False, default=0)
    positive_events_count = db.Column(db.Integer, nullable=False, default=0)
    negative_events_count = db.Column(db.Integer, nullable=False, default=0)
    last_event_timestamp = db.Column(db.DateTime, nullable=True)
    first_event_timestamp = db.Column(db.DateTime, nullable=True)
    
    # Flexible metadata storage
    score_metadata = db.Column(db.JSON, nullable=True)
    
    # Timestamps
    calculated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    
    # Relationships
    contact = db.relationship('Contact', backref='engagement_scores')
    campaign = db.relationship('Campaign', backref='engagement_scores')
    
    # Unique constraint - one score per contact per campaign
    __table_args__ = (
        db.UniqueConstraint('contact_id', 'campaign_id', name='unique_contact_campaign_score'),
        db.Index('idx_engagement_scores_overall', 'overall_score'),
        db.Index('idx_engagement_scores_probability', 'engagement_probability'),
        db.Index('idx_engagement_scores_calculated', 'calculated_at'),
        db.Index('idx_engagement_scores_campaign_score', 'campaign_id', 'overall_score'),
    )
    
    def __repr__(self):
        return f'<EngagementScore {self.id}: {self.overall_score} for Contact {self.contact_id}>'
    
    @property
    def score_grade(self) -> str:
        """Convert overall score to letter grade"""
        if self.overall_score >= 90:
            return 'A+'
        elif self.overall_score >= 80:
            return 'A'
        elif self.overall_score >= 70:
            return 'B'
        elif self.overall_score >= 60:
            return 'C'
        elif self.overall_score >= 50:
            return 'D'
        else:
            return 'F'
    
    @property
    def engagement_level(self) -> str:
        """Categorize engagement level"""
        if self.overall_score >= 80:
            return 'high'
        elif self.overall_score >= 60:
            return 'medium'
        elif self.overall_score >= 40:
            return 'low'
        else:
            return 'very_low'
    
    @property
    def is_recent(self, hours: int = 24) -> bool:
        """Check if score was calculated recently"""
        if not self.calculated_at:
            return False
        cutoff = utc_now() - timedelta(hours=hours)
        return self.calculated_at >= cutoff
    
    def needs_recalculation(self, max_age_hours: int = 168) -> bool:
        """Check if score needs recalculation (default 7 days)"""
        if not self.calculated_at:
            return True
        cutoff = utc_now() - timedelta(hours=max_age_hours)
        return self.calculated_at < cutoff
    
    def to_dict(self) -> dict:
        """Convert score to dictionary for API responses"""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'campaign_id': self.campaign_id,
            'overall_score': float(self.overall_score),
            'recency_score': float(self.recency_score),
            'frequency_score': float(self.frequency_score),
            'monetary_score': float(self.monetary_score),
            'engagement_probability': float(self.engagement_probability),
            'score_grade': self.score_grade,
            'engagement_level': self.engagement_level,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None,
            'score_version': self.score_version
        }


# --- Campaign Response Analytics Model ---
class CampaignResponse(db.Model):
    """Track and analyze responses to campaign messages for response rate analytics"""
    __tablename__ = 'campaign_responses'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    campaign_membership_id = db.Column(db.Integer, db.ForeignKey('campaign_membership.id', ondelete='CASCADE'), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id', ondelete='CASCADE'), nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Message tracking fields
    message_sent_at = db.Column(db.DateTime, nullable=False, index=True)
    first_response_at = db.Column(db.DateTime, nullable=True, index=True)
    response_time_seconds = db.Column(db.Integer, nullable=True)
    
    # Response analysis fields
    response_sentiment = db.Column(db.String(20), nullable=True, index=True)  # positive, negative, neutral
    response_intent = db.Column(db.String(50), nullable=True)  # interested, not_interested, question, complaint, other
    conversation_count = db.Column(db.Integer, default=0)
    ai_confidence_score = db.Column(db.Float, nullable=True)  # 0-1 confidence in sentiment/intent classification
    
    # A/B testing fields
    message_variant = db.Column(db.String(1), nullable=True, index=True)  # A or B
    
    # Response content
    response_text = db.Column(db.Text, nullable=True)
    
    # Response metadata
    is_automated_response = db.Column(db.Boolean, default=False)
    response_channel = db.Column(db.String(20), default='sms')  # sms, email, etc.
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign_membership = db.relationship('CampaignMembership', backref='response', uselist=False)
    contact = db.relationship('Contact', backref='campaign_responses')
    campaign = db.relationship('Campaign', backref='responses')
    
    # Composite indexes for performance
    __table_args__ = (
        db.Index('ix_campaign_responses_campaign_variant', 'campaign_id', 'message_variant'),
        db.Index('ix_campaign_responses_campaign_sentiment', 'campaign_id', 'response_sentiment'),
    )
    
    def __repr__(self):
        return f'<CampaignResponse {self.id}: Campaign {self.campaign_id}, Contact {self.contact_id}>'
    
    @property
    def response_time_hours(self) -> Optional[float]:
        """Get response time in hours"""
        if self.response_time_seconds:
            return self.response_time_seconds / 3600.0
        return None
    
    @property
    def response_time_display(self) -> str:
        """Get human-readable response time"""
        if not self.response_time_seconds:
            return "No response"
        
        hours = self.response_time_seconds // 3600
        minutes = (self.response_time_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    @property
    def is_positive_response(self) -> bool:
        """Check if this is a positive response"""
        return self.response_sentiment == 'positive'
    
    @property
    def is_interested(self) -> bool:
        """Check if contact is interested"""
        return self.response_intent == 'interested'
    
    @property
    def has_responded(self) -> bool:
        """Check if contact has responded"""
        return self.first_response_at is not None
    
    def calculate_response_time(self) -> None:
        """Calculate and set response time in seconds"""
        if self.message_sent_at and self.first_response_at:
            delta = self.first_response_at - self.message_sent_at
            self.response_time_seconds = int(delta.total_seconds())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'contact_id': self.contact_id,
            'campaign_membership_id': self.campaign_membership_id,
            'message_sent_at': self.message_sent_at.isoformat() if self.message_sent_at else None,
            'first_response_at': self.first_response_at.isoformat() if self.first_response_at else None,
            'response_time_seconds': self.response_time_seconds,
            'response_time_display': self.response_time_display,
            'response_sentiment': self.response_sentiment,
            'response_intent': self.response_intent,
            'conversation_count': self.conversation_count,
            'ai_confidence_score': float(self.ai_confidence_score) if self.ai_confidence_score else None,
            'message_variant': self.message_variant,
            'is_automated_response': self.is_automated_response,
            'response_channel': self.response_channel,
            'has_responded': self.has_responded,
            'is_positive_response': self.is_positive_response,
            'is_interested': self.is_interested,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# --- P4-03: Conversion Tracking System Models ---
class ConversionEvent(db.Model):
    """Track conversion events for analytics and attribution analysis"""
    __tablename__ = 'conversion_events'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Core relationships
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True, index=True)
    
    # Conversion details
    conversion_type = db.Column(db.String(50), nullable=False, index=True)  # 'purchase', 'appointment_booked', 'quote_requested', 'lead_qualified', 'custom'
    conversion_value = db.Column(db.Numeric(12, 2), nullable=True)  # Monetary value of conversion
    currency = db.Column(db.String(3), nullable=False, default='USD')  # ISO currency code
    
    # Attribution tracking
    attribution_model = db.Column(db.String(20), nullable=True)  # 'first_touch', 'last_touch', 'linear', 'time_decay'
    attribution_weights = db.Column(db.JSON, nullable=True)  # Campaign attribution weights
    attribution_window_days = db.Column(db.Integer, nullable=True, default=30)  # Attribution window
    
    # Source tracking
    source_campaign_membership_id = db.Column(db.Integer, db.ForeignKey('campaign_membership.id'), nullable=True)
    source_activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)  # Triggering activity
    
    # Conversion timing
    converted_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)
    first_touch_at = db.Column(db.DateTime, nullable=True)  # First touchpoint timestamp
    last_touch_at = db.Column(db.DateTime, nullable=True)   # Last touchpoint before conversion
    
    # Metadata and context
    conversion_metadata = db.Column(db.JSON, nullable=True)  # Additional conversion data
    customer_journey_stage = db.Column(db.String(20), nullable=True)  # 'prospect', 'lead', 'opportunity', 'customer'
    
    # Quality metrics
    confidence_score = db.Column(db.Numeric(4, 3), nullable=True)  # 0-1 confidence in attribution
    data_source = db.Column(db.String(50), nullable=True, default='manual')  # 'manual', 'api', 'webhook', 'import'
    
    # Validation and status
    is_validated = db.Column(db.Boolean, default=False)  # Whether conversion has been validated
    validation_notes = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = db.relationship('Contact', backref='conversion_events')
    campaign = db.relationship('Campaign', backref='conversion_events')
    source_membership = db.relationship('CampaignMembership', backref='triggered_conversions')
    source_activity = db.relationship('Activity', backref='triggered_conversions')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_conversion_events_contact_campaign', 'contact_id', 'campaign_id'),
        db.Index('idx_conversion_events_type_value', 'conversion_type', 'conversion_value'),
        db.Index('idx_conversion_events_converted_at', 'converted_at'),
        db.Index('idx_conversion_events_attribution', 'attribution_model', 'converted_at'),
    )
    
    def __repr__(self):
        return f'<ConversionEvent {self.id}: {self.conversion_type} ${self.conversion_value} Contact:{self.contact_id}>'
    
    @property
    def time_to_conversion_hours(self) -> Optional[float]:
        """Calculate hours from first touch to conversion"""
        if self.first_touch_at and self.converted_at:
            delta = self.converted_at - self.first_touch_at
            return delta.total_seconds() / 3600.0
        return None
    
    @property
    def is_high_value(self, threshold: Decimal = Decimal('100.00')) -> bool:
        """Check if conversion is above high-value threshold"""
        return self.conversion_value and self.conversion_value >= threshold
    
    @property
    def has_attribution(self) -> bool:
        """Check if conversion has attribution data"""
        return self.attribution_weights is not None and len(self.attribution_weights) > 0
    
    def to_dict(self) -> dict:
        """Convert conversion to dictionary for API responses"""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'campaign_id': self.campaign_id,
            'conversion_type': self.conversion_type,
            'conversion_value': float(self.conversion_value) if self.conversion_value else None,
            'currency': self.currency,
            'attribution_model': self.attribution_model,
            'attribution_weights': self.attribution_weights,
            'converted_at': self.converted_at.isoformat() if self.converted_at else None,
            'time_to_conversion_hours': self.time_to_conversion_hours,
            'is_high_value': self.is_high_value,
            'has_attribution': self.has_attribution,
            'conversion_metadata': self.conversion_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
# --- P4-04: Advanced ROI Calculation System Models ---
class CampaignCost(db.Model):
    """Track all campaign expenses for ROI calculation"""
    __tablename__ = 'campaign_costs'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Core relationships
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False, index=True)
    
    # Cost details
    cost_type = db.Column(db.String(20), nullable=False, index=True)  # 'sms', 'labor', 'tools', 'overhead', 'other'
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # Cost amount
    currency = db.Column(db.String(3), nullable=False, default='USD')  # ISO currency code
    description = db.Column(db.Text, nullable=True)  # Description of the cost
    cost_date = db.Column(db.Date, nullable=False, index=True)  # When the cost was incurred
    
    # Cost allocation for shared expenses
    is_shared = db.Column(db.Boolean, default=False)  # Whether cost is shared across campaigns
    allocation_method = db.Column(db.String(20), nullable=True)  # 'equal', 'weighted', 'performance_based'
    allocation_details = db.Column(db.JSON, nullable=True)  # Details of allocation (e.g., campaign weights)
    
    # Audit fields
    created_by = db.Column(db.String(100), nullable=True)  # Who created this cost entry
    approved_by = db.Column(db.String(100), nullable=True)  # Who approved the cost
    approval_date = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign = db.relationship('Campaign', backref='costs')
    
    # Indexes and constraints
    __table_args__ = (
        db.CheckConstraint('amount >= 0', name='ck_campaign_costs_amount_positive'),
        db.Index('idx_campaign_costs_campaign_type', 'campaign_id', 'cost_type'),
        db.Index('idx_campaign_costs_date_range', 'campaign_id', 'cost_date'),
    )
    
    def __repr__(self):
        return f'<CampaignCost {self.id}: {self.cost_type} ${self.amount} for Campaign {self.campaign_id}>'
    
    @property
    def is_operational(self) -> bool:
        """Check if this is an operational cost"""
        return self.cost_type in ['labor', 'overhead']
    
    @property
    def is_variable(self) -> bool:
        """Check if this is a variable cost"""
        return self.cost_type in ['sms', 'tools']
    
    def to_dict(self) -> dict:
        """Convert cost to dictionary for API responses"""
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'cost_type': self.cost_type,
            'amount': float(self.amount),
            'currency': self.currency,
            'description': self.description,
            'cost_date': self.cost_date.isoformat() if self.cost_date else None,
            'is_shared': self.is_shared,
            'allocation_method': self.allocation_method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class CustomerLifetimeValue(db.Model):
    """Track customer lifetime value metrics for ROI analysis"""
    __tablename__ = 'customer_lifetime_values'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Core relationships
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False, index=True)
    
    # Calculation details
    calculation_date = db.Column(db.Date, nullable=False, index=True)  # When LTV was calculated
    
    # Historical metrics
    total_revenue = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # Total revenue from customer
    total_purchases = db.Column(db.Integer, nullable=False, default=0)  # Number of purchases
    average_order_value = db.Column(db.Numeric(10, 2), nullable=True)  # Average purchase amount
    purchase_frequency = db.Column(db.Numeric(6, 3), nullable=True)  # Purchases per month
    customer_lifespan_days = db.Column(db.Integer, nullable=True)  # Days since first purchase
    
    # Predictive metrics
    predicted_ltv = db.Column(db.Numeric(12, 2), nullable=True)  # Predicted lifetime value
    confidence_score = db.Column(db.Numeric(4, 3), nullable=True)  # 0-1 confidence in prediction
    prediction_method = db.Column(db.String(50), nullable=True)  # 'historical', 'cohort', 'ml_model'
    prediction_horizon_months = db.Column(db.Integer, nullable=True, default=24)  # Prediction timeframe
    
    # Cohort analysis
    cohort_month = db.Column(db.Date, nullable=True, index=True)  # Month customer was acquired
    cohort_segment = db.Column(db.String(50), nullable=True)  # Customer segment for analysis
    
    # Retention metrics
    retention_probability = db.Column(db.Numeric(4, 3), nullable=True)  # 0-1 probability of retention
    churn_probability = db.Column(db.Numeric(4, 3), nullable=True)  # 0-1 probability of churn
    last_purchase_date = db.Column(db.Date, nullable=True)
    days_since_last_purchase = db.Column(db.Integer, nullable=True)
    
    # Value segmentation
    value_tier = db.Column(db.String(20), nullable=True)  # 'high', 'medium', 'low'
    percentile_rank = db.Column(db.Numeric(5, 2), nullable=True)  # Percentile among all customers
    
    # Metadata
    calculation_metadata = db.Column(db.JSON, nullable=True)  # Additional calculation details
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = db.relationship('Contact', backref='lifetime_values')
    
    # Indexes and constraints
    __table_args__ = (
        db.UniqueConstraint('contact_id', 'calculation_date', name='unique_contact_ltv_date'),
        db.CheckConstraint('total_revenue >= 0', name='ck_ltv_revenue_positive'),
        db.CheckConstraint('total_purchases >= 0', name='ck_ltv_purchases_positive'),
        db.CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='ck_ltv_confidence_range'),
        db.Index('idx_customer_ltv_contact_date', 'contact_id', 'calculation_date'),
        db.Index('idx_customer_ltv_cohort', 'cohort_month', 'value_tier'),
        db.Index('idx_customer_ltv_value', 'predicted_ltv', 'total_revenue'),
    )
    
    def __repr__(self):
        return f'<CustomerLifetimeValue {self.id}: Contact {self.contact_id} LTV ${self.predicted_ltv}>'
    
    @property
    def is_high_value(self, threshold: Decimal = Decimal('1000.00')) -> bool:
        """Check if customer is high value"""
        return self.predicted_ltv and self.predicted_ltv >= threshold
    
    @property
    def is_at_risk(self, days_threshold: int = 90) -> bool:
        """Check if customer is at risk of churning"""
        if self.days_since_last_purchase and self.days_since_last_purchase > days_threshold:
            return True
        if self.churn_probability and self.churn_probability > 0.5:
            return True
        return False
    
    @property
    def months_since_acquisition(self) -> Optional[int]:
        """Calculate months since customer acquisition"""
        if self.cohort_month and self.calculation_date:
            delta = self.calculation_date - self.cohort_month
            return delta.days // 30
        return None
    
    def to_dict(self) -> dict:
        """Convert LTV to dictionary for API responses"""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'calculation_date': self.calculation_date.isoformat() if self.calculation_date else None,
            'total_revenue': float(self.total_revenue) if self.total_revenue else 0,
            'total_purchases': self.total_purchases,
            'average_order_value': float(self.average_order_value) if self.average_order_value else None,
            'purchase_frequency': float(self.purchase_frequency) if self.purchase_frequency else None,
            'customer_lifespan_days': self.customer_lifespan_days,
            'predicted_ltv': float(self.predicted_ltv) if self.predicted_ltv else None,
            'confidence_score': float(self.confidence_score) if self.confidence_score else None,
            'cohort_month': self.cohort_month.isoformat() if self.cohort_month else None,
            'value_tier': self.value_tier,
            'is_high_value': self.is_high_value,
            'is_at_risk': self.is_at_risk,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ROIAnalysis(db.Model):
    """Store calculated ROI metrics for campaigns and segments"""
    __tablename__ = 'roi_analyses'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Core relationships (nullable for aggregate analyses)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True, index=True)
    
    # Analysis details
    analysis_date = db.Column(db.Date, nullable=False, index=True)  # Date of analysis
    analysis_type = db.Column(db.String(20), nullable=False, index=True)  # 'campaign', 'segment', 'channel', 'cohort'
    analysis_period_start = db.Column(db.Date, nullable=True)  # Start of analysis period
    analysis_period_end = db.Column(db.Date, nullable=True)  # End of analysis period
    
    # Financial metrics
    total_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # Total campaign costs
    total_revenue = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # Total revenue generated
    gross_profit = db.Column(db.Numeric(12, 2), nullable=True)  # Revenue - COGS
    net_profit = db.Column(db.Numeric(12, 2), nullable=True)  # Revenue - All costs
    
    # ROI metrics
    roi_percentage = db.Column(db.Numeric(10, 2), nullable=True)  # ((Revenue - Cost) / Cost) * 100
    roas = db.Column(db.Numeric(10, 2), nullable=True)  # Return on Ad Spend (Revenue / Ad Spend)
    profit_margin = db.Column(db.Numeric(6, 2), nullable=True)  # (Net Profit / Revenue) * 100
    
    # Customer acquisition metrics
    cac = db.Column(db.Numeric(10, 2), nullable=True)  # Customer Acquisition Cost
    new_customers_acquired = db.Column(db.Integer, nullable=True, default=0)
    ltv_cac_ratio = db.Column(db.Numeric(8, 2), nullable=True)  # LTV / CAC ratio
    
    # Payback and break-even
    payback_period_days = db.Column(db.Integer, nullable=True)  # Days to recover investment
    break_even_date = db.Column(db.Date, nullable=True)  # When campaign broke even
    break_even_customers = db.Column(db.Integer, nullable=True)  # Number of customers to break even
    
    # Performance metrics
    conversion_rate = db.Column(db.Numeric(6, 3), nullable=True)  # Percentage of contacts converted
    average_order_value = db.Column(db.Numeric(10, 2), nullable=True)
    customer_retention_rate = db.Column(db.Numeric(6, 3), nullable=True)  # Percentage retained
    
    # Segmentation details (for segment analysis)
    segment_criteria = db.Column(db.JSON, nullable=True)  # Criteria used for segmentation
    segment_size = db.Column(db.Integer, nullable=True)  # Number of contacts in segment
    
    # Flexible metadata storage
    analysis_metadata = db.Column(db.JSON, nullable=True)  # Additional metrics and details
    
    # Data quality
    data_completeness = db.Column(db.Numeric(4, 3), nullable=True)  # 0-1 completeness score
    confidence_level = db.Column(db.Numeric(4, 3), nullable=True)  # 0-1 confidence in calculations
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign = db.relationship('Campaign', backref='roi_analyses')
    
    # Indexes and constraints
    __table_args__ = (
        db.CheckConstraint('total_cost >= 0', name='ck_roi_cost_positive'),
        db.CheckConstraint('total_revenue >= 0', name='ck_roi_revenue_positive'),
        db.CheckConstraint('roi_percentage IS NULL OR roi_percentage >= -100', name='ck_roi_percentage_min'),
        db.CheckConstraint('roas IS NULL OR roas >= 0', name='ck_roi_roas_positive'),
        db.Index('idx_roi_analysis_campaign_date', 'campaign_id', 'analysis_date'),
        db.Index('idx_roi_analysis_type_date', 'analysis_type', 'analysis_date'),
        db.Index('idx_roi_analysis_roi', 'roi_percentage', 'roas'),
        db.Index('idx_roi_analysis_performance', 'campaign_id', 'roi_percentage', 'total_revenue'),
    )
    
    def __repr__(self):
        return f'<ROIAnalysis {self.id}: {self.analysis_type} ROI {self.roi_percentage}%>'
    
    @property
    def is_profitable(self) -> bool:
        """Check if analysis shows profitability"""
        return self.net_profit and self.net_profit > 0
    
    @property
    def roi_multiplier(self) -> Optional[float]:
        """Get ROI as a multiplier (e.g., 2.5x)"""
        if self.roi_percentage:
            return 1 + (float(self.roi_percentage) / 100)
        return None
    
    @property
    def is_high_performing(self, roi_threshold: Decimal = Decimal('100')) -> bool:
        """Check if this is a high-performing campaign/segment"""
        return self.roi_percentage and self.roi_percentage >= roi_threshold
    
    @property
    def efficiency_rating(self) -> str:
        """Rate efficiency based on ROI and ROAS"""
        if not self.roi_percentage:
            return 'unknown'
        
        roi = float(self.roi_percentage)
        if roi >= 200:
            return 'excellent'
        elif roi >= 100:
            return 'good'
        elif roi >= 50:
            return 'fair'
        elif roi >= 0:
            return 'poor'
        else:
            return 'negative'
    
    def calculate_roi(self) -> None:
        """Calculate ROI percentage from cost and revenue"""
        if self.total_cost and self.total_cost > 0:
            roi = ((self.total_revenue - self.total_cost) / self.total_cost) * 100
            self.roi_percentage = Decimal(str(round(roi, 2)))
    
    def calculate_roas(self) -> None:
        """Calculate Return on Ad Spend"""
        if self.total_cost and self.total_cost > 0:
            roas = self.total_revenue / self.total_cost
            self.roas = Decimal(str(round(roas, 2)))
    
    def to_dict(self) -> dict:
        """Convert ROI analysis to dictionary for API responses"""
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'analysis_date': self.analysis_date.isoformat() if self.analysis_date else None,
            'analysis_type': self.analysis_type,
            'total_cost': float(self.total_cost) if self.total_cost else 0,
            'total_revenue': float(self.total_revenue) if self.total_revenue else 0,
            'gross_profit': float(self.gross_profit) if self.gross_profit else None,
            'net_profit': float(self.net_profit) if self.net_profit else None,
            'roi_percentage': float(self.roi_percentage) if self.roi_percentage else None,
            'roi_multiplier': self.roi_multiplier,
            'roas': float(self.roas) if self.roas else None,
            'cac': float(self.cac) if self.cac else None,
            'ltv_cac_ratio': float(self.ltv_cac_ratio) if self.ltv_cac_ratio else None,
            'payback_period_days': self.payback_period_days,
            'break_even_date': self.break_even_date.isoformat() if self.break_even_date else None,
            'is_profitable': self.is_profitable,
            'is_high_performing': self.is_high_performing,
            'efficiency_rating': self.efficiency_rating,
            'metadata': self.analysis_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
