# crm_database.py

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

# --- Core CRM Models ---

class Contact(Base):
    """Represents a person in your CRM."""
    __tablename__ = 'contacts'

    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    contact_type = Column(String) # e.g., 'homeowner', 'realtor', 'property_manager', 'inspector', 'builder'
    
    # Granular Status Fields
    contact_status = Column(String, default='new_lead') # e.g., 'new_lead', 'contacted', 'active', 'do_not_contact', 'archived'
    customer_status = Column(String, default='not_customer') # e.g., 'not_customer', 'quoted', 'job_completed', 'repeat_customer'
    payment_status = Column(String, default='no_payment_due') # e.g., 'no_payment_due', 'payment_pending', 'payment_collected', 'overdue'

    notes = Column(Text) # General notes about the contact
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    contact_details = relationship("ContactDetail", back_populates="contact", cascade="all, delete-orphan")
    properties = relationship("Property", secondary="contact_property", back_populates="contacts", overlaps="contact_property_links")
    contact_property_links = relationship("ContactProperty", back_populates="contact", cascade="all, delete-orphan", overlaps="properties") 
    campaign_contacts = relationship("CampaignContact", back_populates="contact", cascade="all, delete-orphan")
    contact_sources = relationship("ContactSource", back_populates="contact", cascade="all, delete-orphan")
    
    # New Relationships for operational entities
    jobs = relationship("Job", back_populates="primary_contact")
    appointments = relationship("Appointment", back_populates="contact")
    quotes = relationship("Quote", back_populates="contact")
    invoices = relationship("Invoice", back_populates="contact")

    def __repr__(self):
        return f"<Contact(id={self.id}, name='{self.first_name} {self.last_name}', type='{self.contact_type}')>"

class ContactDetail(Base):
    """Stores multiple phone numbers and emails for a contact."""
    __tablename__ = 'contact_details'

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=False)
    type = Column(String, nullable=False) # 'phone' or 'email'
    value = Column(String, nullable=False) # The actual phone number (E.164) or email address
    label = Column(String) # e.g., 'mobile', 'office', 'personal', 'primary', 'secondary'
    status = Column(String, default='active') # e.g., 'active', 'undeliverable', 'opted_out', 'verified'
    last_attempt_date = Column(DateTime) # Last time we tried to contact via this detail
    last_successful_date = Column(DateTime) # Last time contact was successful via this detail
    delivery_status = Column(String) # For SMS: 'sent', 'delivered', 'undelivered', 'failed'; For Email: 'sent', 'opened', 'clicked', 'bounced'

    contact = relationship("Contact", back_populates="contact_details")

    def __repr__(self):
        return f"<ContactDetail(id={self.id}, type='{self.type}', value='{self.value}', label='{self.label}')>"

class Property(Base):
    """Represents a property."""
    __tablename__ = 'properties'

    id = Column(Integer, primary_key=True)
    apn = Column(String, unique=True, nullable=False) # Assessor's Parcel Number - robust unique ID
    address = Column(String)
    city = Column(String)
    zip_code = Column(String) # Renamed to avoid conflict with zip() function
    subdivision = Column(String)
    latitude = Column(Float) # Changed to Float for numerical storage
    longitude = Column(Float) # Changed to Float for numerical storage
    year_built = Column(Integer)
    purchase_date = Column(DateTime)
    purchase_months_since = Column(Integer)
    sq_ft = Column(Integer)
    beds = Column(Integer)
    baths = Column(Integer)
    est_value = Column(Integer)
    est_equity_dollars = Column(Integer)
    est_equity_percent = Column(Float) # Changed to Float for percentage
    high_equity = Column(Boolean)
    owner_occupied = Column(Boolean)
    listed_for_sale = Column(Boolean)
    listing_status = Column(String)
    foreclosure = Column(Boolean)
    mail_address = Column(String)
    mail_city = Column(String)
    mail_state = Column(String)
    mail_zip = Column(String)
    property_radar_id = Column(String, unique=True) # PropertyRadar's internal ID if available
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    contacts = relationship("Contact", secondary="contact_property", back_populates="properties", overlaps="contact_property_links")
    contact_property_links = relationship("ContactProperty", back_populates="property", cascade="all, delete-orphan", overlaps="contacts")
    jobs = relationship("Job", back_populates="property")
    appointments = relationship("Appointment", back_populates="property")
    quotes = relationship("Quote", back_populates="property")
    invoices = relationship("Invoice", back_populates="property")

    def __repr__(self):
        return f"<Property(id={self.id}, address='{self.address}, {self.city}')>"

class ContactProperty(Base):
    """Association table for many-to-many relationship between Contact and Property."""
    __tablename__ = 'contact_property'

    contact_id = Column(Integer, ForeignKey('contacts.id'), primary_key=True)
    property_id = Column(Integer, ForeignKey('properties.id'), primary_key=True)
    role = Column(String) # e.g., 'primary_owner', 'secondary_owner', 'realtor', 'property_manager'

    # New: Relationships back to the parent objects from the association object
    contact = relationship("Contact", back_populates="contact_property_links", overlaps="contact_property_links,properties")
    property = relationship("Property", back_populates="contact_property_links", overlaps="contacts,contact_property_links")

    def __repr__(self):
        return f"<ContactProperty(contact_id={self.contact_id}, property_id={self.property_id}, role='{self.role}')>"

# --- Campaign & Tracking Models ---

class Campaign(Base):
    """Represents a messaging campaign (SMS or Email)."""
    __tablename__ = 'campaigns'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False) # 'sms' or 'email'
    status = Column(String, default='draft') # 'draft', 'active', 'paused', 'completed'
    message_template = Column(Text) # For SMS: the message body; For Email: subject + body (or just reference to SmartLead template ID)
    scheduled_time = Column(DateTime) # When the campaign is scheduled to start
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    campaign_contacts = relationship("CampaignContact", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Campaign(id={self.id}, name='{self.name}', type='{self.type}')>"

class CampaignContact(Base):
    """Tracks a contact's status within a specific campaign."""
    __tablename__ = 'campaign_contacts'

    campaign_id = Column(Integer, ForeignKey('campaigns.id'), primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'), primary_key=True)
    message_status = Column(String, default='pending') # e.g., 'pending', 'sent', 'delivered', 'undelivered', 'replied', 'opted_out', 'bounced', 'opened', 'clicked'
    sent_at = Column(DateTime)
    last_status_update_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    external_message_id = Column(String) # ID from OpenPhone/SmartLead for individual message

    campaign = relationship("Campaign", back_populates="campaign_contacts")
    contact = relationship("Contact", back_populates="campaign_contacts")

    def __repr__(self):
        return f"<CampaignContact(campaign_id={self.campaign_id}, contact_id={self.contact_id}, status='{self.message_status}')>"

# --- Data Source Tracking ---

class PropertyRadarQuery(Base):
    """Logs parameters of PropertyRadar queries."""
    __tablename__ = 'property_radar_queries'

    id = Column(Integer, primary_key=True)
    query_params = Column(JSON) # Store the exact JSON query parameters
    query_date = Column(DateTime, default=datetime.now)
    description = Column(String) # User-friendly description of the query
    total_results = Column(Integer) # Number of results from this query
    new_contacts_added = Column(Integer, default=0)
    existing_contacts_updated = Column(Integer, default=0)

    contact_sources = relationship(
        "ContactSource",
        primaryjoin="and_(PropertyRadarQuery.id == ContactSource.source_id, ContactSource.source_type == 'PropertyRadar_Query')",
        foreign_keys="[ContactSource.source_id]",
        back_populates="property_radar_query"
    )

    def __repr__(self):
        return f"<PropertyRadarQuery(id={self.id}, description='{self.description}')>"

class ContactSource(Base):
    """Links a contact to its origin (e.g., a PropertyRadar query, a CSV import)."""
    __tablename__ = 'contact_sources'

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=False)
    source_type = Column(String, nullable=False) # 'PropertyRadar_Query', 'CSV_Import', 'Manual_Entry'
    
    source_id = Column(Integer, ForeignKey('property_radar_queries.id', ondelete='SET NULL'))
    
    import_date = Column(DateTime, default=datetime.now)
    original_data = Column(JSON) # Store raw data from import for debugging/reference

    contact = relationship("Contact", back_populates="contact_sources")
    property_radar_query = relationship(
        "PropertyRadarQuery",
        primaryjoin="and_(ContactSource.source_id == PropertyRadarQuery.id, ContactSource.source_type == 'PropertyRadar_Query')",
        foreign_keys=[source_id],
        back_populates="contact_sources"
    )

    def __repr__(self):
        return f"<ContactSource(contact_id={self.contact_id}, type='{self.source_type}', source_id={self.source_id})>"

# --- Operational Entities ---

class Job(Base):
    """Represents a specific job or project."""
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True)
    job_name = Column(String, nullable=False)
    description = Column(Text)
    
    property_id = Column(Integer, ForeignKey('properties.id'), nullable=False)
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=False)
    
    job_status = Column(String, default='pending') # e.g., 'pending', 'in_progress', 'completed', 'cancelled', 'on_hold'
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    total_amount = Column(Float) # Total estimated or actual amount for the job
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    primary_contact = relationship("Contact", back_populates="jobs")
    property = relationship("Property", back_populates="jobs")
    
    appointments = relationship("Appointment", back_populates="job")
    quotes = relationship("Quote", back_populates="job")
    invoices = relationship("Invoice", back_populates="job")

    def __repr__(self):
        return f"<Job(id={self.id}, name='{self.job_name}', status='{self.job_status}')>"

class Appointment(Base):
    """Represents a scheduled appointment."""
    __tablename__ = 'appointments'

    id = Column(Integer, primary_key=True)
    
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id')) # Optional, but common
    job_id = Column(Integer, ForeignKey('jobs.id')) # Optional, if linked to a specific job
    
    appointment_type = Column(String) # e.g., 'initial_consult', 'estimate', 'job_start', 'follow_up', 'site_visit'
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String, default='scheduled') # e.g., 'scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled'
    notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    contact = relationship("Contact", back_populates="appointments")
    property = relationship("Property", back_populates="appointments")
    job = relationship("Job", back_populates="appointments")

    def __repr__(self):
        return f"<Appointment(id={self.id}, type='{self.appointment_type}', time='{self.scheduled_time}')>"

class Quote(Base):
    """Represents a quote or estimate provided."""
    __tablename__ = 'quotes'

    id = Column(Integer, primary_key=True)
    
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id')) # Optional
    job_id = Column(Integer, ForeignKey('jobs.id')) # Optional, if quote is for an existing job
    
    quote_number = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default='draft') # e.g., 'draft', 'sent', 'accepted', 'rejected', 'expired', 'invoiced'
    sent_date = Column(DateTime)
    accepted_date = Column(DateTime)
    valid_until = Column(DateTime)
    details = Column(Text) # Store quote details (e.g., line items, scope of work)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    contact = relationship("Contact", back_populates="quotes")
    property = relationship("Property", back_populates="quotes")
    job = relationship("Job", back_populates="quotes")
    
    # New: One-to-one relationship to Invoice
    invoice = relationship("Invoice", back_populates="quote", uselist=False) # uselist=False for one-to-one

    def __repr__(self):
        return f"<Quote(id={self.id}, number='{self.quote_number}', amount={self.amount}, status='{self.status}')>"

class Invoice(Base):
    """Represents an invoice for services rendered."""
    __tablename__ = 'invoices'

    id = Column(Integer, primary_key=True)
    
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id')) # Optional
    job_id = Column(Integer, ForeignKey('jobs.id')) # Optional, if invoice is for a specific job
    
    # New: Link to the Quote that this invoice was generated from
    quote_id = Column(Integer, ForeignKey('quotes.id'), unique=True, nullable=True) # Unique for one-to-one link
    
    invoice_number = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default='issued') # e.g., 'issued', 'paid', 'partially_paid', 'overdue', 'cancelled'
    issue_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime)
    paid_date = Column(DateTime)
    payment_method = Column(String) # e.g., 'credit_card', 'check', 'bank_transfer'
    details = Column(Text) # Store invoice line items or notes
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    contact = relationship("Contact", back_populates="invoices")
    property = relationship("Property", back_populates="invoices")
    job = relationship("Job", back_populates="invoices")
    
    # New: Relationship back to the Quote
    quote = relationship("Quote", back_populates="invoice")

    def __repr__(self):
        return f"<Invoice(id={self.id}, number='{self.invoice_number}', amount={self.amount}, status='{self.status}')>"


# --- Database Setup Function ---
def setup_database(db_path='crm.db'):
    """Initializes the SQLite database and creates tables."""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
