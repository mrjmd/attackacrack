# crm_database.py

from extensions import db
from datetime import datetime

# Define your database models using the single db instance
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True, unique=True)
    properties = db.relationship('Property', backref='contact', lazy=True, cascade="all, delete-orphan")
    appointments = db.relationship('Appointment', backref='contact', lazy=True, cascade="all, delete-orphan")
    # Add relationship to messages
    messages = db.relationship('Message', backref='contact', lazy=True, cascade="all, delete-orphan")

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    jobs = db.relationship('Job', backref='property', lazy=True, cascade="all, delete-orphan")

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Active')
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    quotes = db.relationship('Quote', backref='job', lazy=True, cascade="all, delete-orphan")
    invoices = db.relationship('Invoice', backref='job', lazy=True, cascade="all, delete-orphan")

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Draft')
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Draft') # e.g., Draft, Sent, Paid, Overdue
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)

# New Message Model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True, nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    body = db.Column(db.Text, nullable=True)
    direction = db.Column(db.String(10), nullable=False) # 'incoming' or 'outgoing'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    # We can add media URLs here later
    # media_url = db.Column(db.String(500), nullable=True)
