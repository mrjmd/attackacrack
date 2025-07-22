# crm_manager.py

import requests
import os
from dotenv import load_dotenv
from crm_database import setup_database, Contact, ContactDetail, Property, ContactProperty, Campaign, CampaignContact, PropertyRadarQuery, ContactSource, Job, Appointment, Quote, Invoice
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from sqlalchemy import or_, and_
from datetime import datetime, timedelta
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.utils import parsedate_to_datetime

load_dotenv()

OPENPHONE_API_KEY = os.getenv("OPENPHONE_API_KEY")
OPENPHONE_BASE_URL = "https://api.openphone.com/v1"
OPENPHONE_PHONE_NUMBER = os.getenv("OPENPHONE_PHONE_NUMBER")

_Session_for_testing = sessionmaker(bind=setup_database().bind)

# --- Core CRM Functions ---
def add_contact(session, first_name, last_name, contact_type, phone_numbers=None, emails=None, notes=None):
    try:
        new_contact = Contact(
            first_name=first_name,
            last_name=last_name,
            contact_type=contact_type,
            contact_status='new_lead',
            notes=notes
        )
        session.add(new_contact)
        session.flush()
        if phone_numbers:
            for num_info in phone_numbers:
                detail = ContactDetail(contact=new_contact, type='phone', value=num_info['value'], label=num_info.get('label'))
                session.add(detail)
        if emails:
            for email_info in emails:
                detail = ContactDetail(contact=new_contact, type='email', value=email_info['value'], label=email_info.get('label'))
                session.add(detail)
        session.commit()
        return new_contact
    except Exception as e:
        session.rollback()
        print(f"Error adding contact: {e}")
        return None

def get_contact_by_id(session, contact_id):
    return session.query(Contact).options(
        joinedload(Contact.contact_details),
        joinedload(Contact.properties),
        joinedload(Contact.contact_property_links),
        joinedload(Contact.jobs),
        joinedload(Contact.appointments),
        joinedload(Contact.quotes),
        joinedload(Contact.invoices),
        joinedload(Contact.campaign_contacts).joinedload(CampaignContact.campaign),
        joinedload(Contact.contact_sources).joinedload(ContactSource.property_radar_query)
    ).get(contact_id)

def list_contacts(session, contact_type=None, contact_status=None, customer_status=None, payment_status=None,
                  has_open_estimates=False, has_unpaid_invoices=False, search_name=None):
    query = session.query(Contact)
    if contact_type and contact_type != 'All':
        query = query.filter(Contact.contact_type == contact_type)
    if contact_status and contact_status != 'All':
        query = query.filter(Contact.contact_status == contact_status)
    if customer_status and customer_status != 'All':
        query = query.filter(Contact.customer_status == customer_status)
    if payment_status and payment_status != 'All':
        query = query.filter(Contact.payment_status == payment_status)
    if has_open_estimates:
        query = query.join(Contact.quotes).filter(Quote.status.in_(['draft', 'sent']))
    if has_unpaid_invoices:
        query = query.join(Contact.invoices).filter(Invoice.status.in_(['issued', 'partially_paid', 'overdue']))
    if search_name:
        search_pattern = f"%{search_name}%"
        query = query.filter(or_(Contact.first_name.ilike(search_pattern), Contact.last_name.ilike(search_pattern)))
    return query.options(joinedload(Contact.contact_details)).all()

# --- NEW FUNCTION FOR CUSTOMERS PAGE ---
def list_customers(session, search_name=None):
    """
    Lists contacts who are considered customers.
    A customer has a status of 'quoted', 'job_completed', or 'repeat_customer'.
    """
    customer_statuses = ['quoted', 'job_completed', 'repeat_customer']
    query = session.query(Contact).filter(Contact.customer_status.in_(customer_statuses))

    if search_name:
        search_pattern = f"%{search_name}%"
        query = query.filter(or_(
            Contact.first_name.ilike(search_pattern),
            Contact.last_name.ilike(search_pattern)
        ))

    query = query.options(joinedload(Contact.contact_details))
    return query.order_by(Contact.last_name, Contact.first_name).all()


def update_contact(session, contact_id, first_name=None, last_name=None, contact_type=None,
                   new_contact_status=None, new_customer_status=None, new_payment_status=None,
                   notes=None):
    try:
        contact = session.get(Contact, contact_id)
        if contact:
            if first_name is not None: contact.first_name = first_name
            if last_name is not None: contact.last_name = last_name
            if contact_type is not None: contact.contact_type = contact_type
            if new_contact_status is not None: contact.contact_status = new_contact_status
            if new_customer_status is not None: contact.customer_status = new_customer_status
            if new_payment_status is not None: contact.payment_status = new_payment_status
            if notes is not None: contact.notes = notes
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error updating contact: {e}")
        return False

def delete_contact(session, contact_id):
    try:
        contact = session.get(Contact, contact_id)
        if contact:
            session.delete(contact)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error deleting contact: {e}")
        return False

def add_property(session, apn, address, city, zip_code, **kwargs):
    try:
        existing_property = session.query(Property).filter_by(apn=apn).first()
        if existing_property:
            return existing_property
        new_property = Property(apn=apn, address=address, city=city, zip_code=zip_code, **kwargs)
        session.add(new_property)
        session.commit()
        return new_property
    except Exception as e:
        session.rollback()
        print(f"Error adding property: {e}")
        return None

def get_property_by_id(session, property_id):
    return session.query(Property).options(
        joinedload(Property.contacts),
        joinedload(Property.contact_property_links),
        joinedload(Property.jobs),
        joinedload(Property.appointments),
        joinedload(Property.quotes),
        joinedload(Property.invoices)
    ).get(property_id)

def list_properties(session, city=None, zip_code=None, min_value=None, has_foreclosure=False):
    query = session.query(Property)
    if city: query = query.filter(Property.city.ilike(f'%{city}%'))
    if zip_code: query = query.filter(Property.zip_code == zip_code)
    if min_value is not None: query = query.filter(Property.est_value >= min_value)
    if has_foreclosure: query = query.filter(Property.foreclosure == True)
    return query.all()

def update_property(session, property_id, **kwargs):
    try:
        prop = session.get(Property, property_id)
        if prop:
            for key, value in kwargs.items():
                if hasattr(prop, key):
                    setattr(prop, key, value)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error updating property: {e}")
        return False

def delete_property(session, property_id):
    try:
        prop = session.get(Property, property_id)
        if prop:
            session.delete(prop)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error deleting property: {e}")
        return False

def link_contact_to_property(session, contact_id, property_id, role):
    try:
        contact = session.get(Contact, contact_id)
        prop = session.get(Property, property_id)
        if not contact or not prop: return False
        existing_link = session.query(ContactProperty).filter_by(contact_id=contact_id, property_id=property_id).first()
        if existing_link:
            existing_link.role = role
        else:
            session.add(ContactProperty(contact_id=contact.id, property_id=prop.id, role=role))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error linking contact to property: {e}")
        return False

def add_job(session, job_name, description, property_id, contact_id, total_amount, start_date=None, job_status='pending'):
    try:
        prop = session.get(Property, property_id)
        contact = session.get(Contact, contact_id)
        if not prop or not contact:
            return None
        new_job = Job(job_name=job_name, description=description, property=prop, primary_contact=contact, total_amount=total_amount, start_date=start_date, job_status=job_status)
        session.add(new_job)
        session.commit()
        return new_job
    except Exception as e:
        session.rollback()
        print(f"Error adding job: {e}")
        return None

def get_job_by_id(session, job_id):
    return session.query(Job).options(joinedload(Job.property), joinedload(Job.primary_contact), joinedload(Job.appointments), joinedload(Job.quotes), joinedload(Job.invoices)).get(job_id)

def list_jobs(session, job_status=None, search_name=None, contact_id=None, property_id=None):
    query = session.query(Job)
    if job_status and job_status != 'All':
        query = query.filter(Job.job_status == job_status)
    if search_name:
        query = query.filter(Job.job_name.ilike(f"%{search_name}%"))
    if contact_id:
        query = query.filter(Job.contact_id == contact_id)
    if property_id:
        query = query.filter(Job.property_id == property_id)
    return query.options(joinedload(Job.property), joinedload(Job.primary_contact)).all()

def update_job(session, job_id, **kwargs):
    try:
        job = session.get(Job, job_id)
        if job:
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error updating job: {e}")
        return False

def delete_job(session, job_id):
    try:
        job = session.get(Job, job_id)
        if job:
            session.delete(job)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error deleting job: {e}")
        return False

def add_appointment(session, contact_id, appointment_type, scheduled_time, property_id=None, job_id=None, status='scheduled', notes=None):
    try:
        contact = session.get(Contact, contact_id)
        if not contact: return None
        prop = session.get(Property, property_id) if property_id else None
        if job_id is None:
            job, _ = find_or_create_job(session, contact_id, property_id)
            job_id = job.id if job else None
        else:
            job = session.get(Job, job_id)
            if not job: return None
        new_appt = Appointment(contact=contact, property=prop, job_id=job_id, appointment_type=appointment_type, scheduled_time=scheduled_time, status=status, notes=notes)
        session.add(new_appt)
        session.commit()
        return new_appt
    except Exception as e:
        session.rollback()
        print(f"Error adding appointment: {e}")
        return None

def get_appointment_by_id(session, appointment_id):
    return session.query(Appointment).options(joinedload(Appointment.contact), joinedload(Appointment.property), joinedload(Appointment.job)).get(appointment_id)

def list_appointments(session, status=None, appointment_type=None, contact_id=None, property_id=None, job_id=None):
    query = session.query(Appointment)
    if status and status != 'All': query = query.filter(Appointment.status == status)
    if appointment_type and appointment_type != 'All': query = query.filter(Appointment.appointment_type == appointment_type)
    if contact_id: query = query.filter(Appointment.contact_id == contact_id)
    if property_id: query = query.filter(Appointment.property_id == property_id)
    if job_id: query = query.filter(Appointment.job_id == job_id)
    return query.options(joinedload(Appointment.contact), joinedload(Appointment.property), joinedload(Appointment.job)).all()

def update_appointment(session, appointment_id, **kwargs):
    try:
        appt = session.get(Appointment, appointment_id)
        if appt:
            for key, value in kwargs.items():
                if hasattr(appt, key):
                    setattr(appt, key, value)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error updating appointment: {e}")
        return False

def delete_appointment(session, appointment_id):
    try:
        appt = session.get(Appointment, appointment_id)
        if appt:
            session.delete(appt)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error deleting appointment: {e}")
        return False

def add_quote(session, contact_id, quote_number, amount, status='draft', property_id=None, job_id=None, sent_date=None, accepted_date=None, valid_until=None, details=None):
    try:
        contact = session.get(Contact, contact_id)
        if not contact: return None
        prop = session.get(Property, property_id) if property_id else None
        if job_id is None:
            job, _ = find_or_create_job(session, contact_id, property_id)
            job_id = job.id if job else None
        else:
            job = session.get(Job, job_id)
            if not job: return None
        new_quote = Quote(contact=contact, quote_number=quote_number, amount=amount, status=status, property=prop, job_id=job_id, sent_date=sent_date, accepted_date=accepted_date, valid_until=valid_until, details=details)
        session.add(new_quote)
        session.commit()
        return new_quote
    except Exception as e:
        session.rollback()
        print(f"Error adding quote: {e}")
        return None

def get_quote_by_id(session, quote_id):
    return session.query(Quote).options(joinedload(Quote.contact), joinedload(Quote.property), joinedload(Quote.job), joinedload(Quote.invoice)).get(quote_id)

def list_quotes(session, status=None, contact_id=None, property_id=None, job_id=None):
    query = session.query(Quote)
    if status and status != 'All': query = query.filter(Quote.status == status)
    if contact_id: query = query.filter(Quote.contact_id == contact_id)
    if property_id: query = query.filter(Quote.property_id == property_id)
    if job_id: query = query.filter(Quote.job_id == job_id)
    return query.options(joinedload(Quote.contact), joinedload(Quote.property), joinedload(Quote.job)).all()

def update_quote(session, quote_id, **kwargs):
    try:
        quote = session.get(Quote, quote_id)
        if quote:
            for key, value in kwargs.items():
                if hasattr(quote, key):
                    setattr(quote, key, value)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error updating quote: {e}")
        return False

def delete_quote(session, quote_id):
    try:
        quote = session.get(Quote, quote_id)
        if quote:
            session.delete(quote)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error deleting quote: {e}")
        return False

def add_invoice(session, contact_id, invoice_number, amount, issue_date, status='issued', property_id=None, job_id=None, quote_id=None, due_date=None, paid_date=None, payment_method=None, details=None):
    try:
        contact = session.get(Contact, contact_id)
        if not contact: return None
        prop = session.get(Property, property_id) if property_id else None
        quote = session.get(Quote, quote_id) if quote_id else None
        if job_id is None:
            job, _ = find_or_create_job(session, contact_id, property_id)
            job_id = job.id if job else None
        else:
            job = session.get(Job, job_id)
            if not job: return None
        new_invoice = Invoice(contact=contact, property=prop, job_id=job_id, quote=quote, invoice_number=invoice_number, amount=amount, issue_date=issue_date, status=status, due_date=due_date, paid_date=paid_date, payment_method=payment_method, details=details)
        session.add(new_invoice)
        session.commit()
        return new_invoice
    except Exception as e:
        session.rollback()
        print(f"Error adding invoice: {e}")
        return None

def get_invoice_by_id(session, invoice_id):
    return session.query(Invoice).options(joinedload(Invoice.contact), joinedload(Invoice.property), joinedload(Invoice.job), joinedload(Invoice.quote)).get(invoice_id)

def list_invoices(session, status=None, contact_id=None, property_id=None, job_id=None, quote_id=None):
    query = session.query(Invoice)
    if status and status != 'All': query = query.filter(Invoice.status == status)
    if contact_id: query = query.filter(Invoice.contact_id == contact_id)
    if property_id: query = query.filter(Invoice.property_id == property_id)
    if job_id: query = query.filter(Invoice.job_id == job_id)
    if quote_id: query = query.filter(Invoice.quote_id == quote_id)
    return query.options(joinedload(Invoice.contact), joinedload(Invoice.property), joinedload(Invoice.job), joinedload(Invoice.quote)).all()

def update_invoice(session, invoice_id, **kwargs):
    try:
        invoice = session.get(Invoice, invoice_id)
        if invoice:
            for key, value in kwargs.items():
                if hasattr(invoice, key):
                    setattr(invoice, key, value)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error updating invoice: {e}")
        return False

def delete_invoice(session, invoice_id):
    try:
        invoice = session.get(Invoice, invoice_id)
        if invoice:
            session.delete(invoice)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Error deleting invoice: {e}")
        return False

def convert_quote_to_invoice(session, quote_id):
    try:
        quote = session.get(Quote, quote_id)
        if not quote or quote.status != 'accepted' or quote.invoice:
            return False, "Quote not found, not accepted, or already invoiced."
        latest_invoice = session.query(Invoice).order_by(Invoice.id.desc()).first()
        new_invoice_number_int = int(latest_invoice.invoice_number.split('-')[-1]) + 1 if latest_invoice and '-' in latest_invoice.invoice_number else 1
        new_invoice_number = f"INV-{datetime.now().year}-{new_invoice_number_int:04d}"
        new_invoice = Invoice(contact=quote.contact, property=quote.property, job=quote.job, quote=quote, invoice_number=new_invoice_number, amount=quote.amount, issue_date=datetime.now(), due_date=datetime.now() + timedelta(days=30), status='issued', details=f"Invoice for Quote {quote.quote_number}: {quote.details}")
        session.add(new_invoice)
        quote.status = 'invoiced'
        session.commit()
        return True, new_invoice
    except Exception as e:
        session.rollback()
        print(f"Error converting quote to invoice: {e}")
        return False, str(e)

def find_or_create_job(session, contact_id, property_id=None):
    contact = session.get(Contact, contact_id)
    if not contact: return None, "Contact not found."
    query = session.query(Job).outerjoin(Invoice, Job.id == Invoice.job_id).filter(Job.contact_id == contact_id, Job.job_status.in_(['pending', 'in_progress', 'on_hold']), or_(Invoice.status != 'paid', Invoice.id == None)).order_by(Job.created_at.desc())
    if property_id:
        query = query.filter(Job.property_id == property_id)
    existing_job = query.first()
    if existing_job:
        return existing_job, "Linked to existing job."
    else:
        job_name = f"Job for {contact.first_name} {contact.last_name}"
        if property_id and (prop := session.get(Property, property_id)):
            job_name += f" at {prop.address}"
        new_job = add_job(session, job_name=job_name, description="Auto-created job.", property_id=property_id, contact_id=contact_id, total_amount=0.00)
        return (new_job, "New job created.") if new_job else (None, "Failed to create new job.")


# --- IntegrationManager Class ---
class IntegrationManager:
    def __init__(self):
        self.google_creds = None
        self.openphone_api_key = os.getenv("OPENPHONE_API_KEY")
        self.token_file = 'token.pickle'
        self.openphone_key_file = 'openphone.key'
        self.load_credentials()

    def load_credentials(self):
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                self.google_creds = pickle.load(token)
        if os.path.exists(self.openphone_key_file):
            with open(self.openphone_key_file, 'r') as f:
                self.openphone_api_key = f.read().strip()

    def save_google_credentials(self, creds):
        self.google_creds = creds
        with open(self.token_file, 'wb') as token:
            pickle.dump(self.google_creds, token)

    def save_openphone_key(self, api_key):
        self.openphone_api_key = api_key
        with open(self.openphone_key_file, 'w') as f:
            f.write(api_key)

    def is_google_authenticated(self):
        return self.google_creds and self.google_creds.valid

    def is_openphone_configured(self):
        return self.openphone_api_key is not None

    def get_google_auth_flow(self):
        if not os.path.exists('client_secret.json'):
            raise FileNotFoundError("CRITICAL: 'client_secret.json' not found.")
        flow = Flow.from_client_secrets_file(
            'client_secret.json',
            scopes=['https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/gmail.readonly'],
            redirect_uri='https://127.0.0.1:5000/oauth2callback'
        )
        return flow

    def get_calendar_events(self):
        if not self.is_google_authenticated(): return None
        try:
            service = build('calendar', 'v3', credentials=self.google_creds)
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary', timeMin=now,
                maxResults=5, singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted_time = start_dt.strftime('%b %d, %I:%M %p')
                attendees = event.get('attendees', [])
                with_str = ', '.join([a.get('email') for a in attendees if not a.get('resource')])
                formatted_events.append({'title': event['summary'], 'time': formatted_time, 'with': with_str})
            return formatted_events
        except Exception as e:
            print(f"--- ERROR fetching calendar events: {e} ---")
            return []

    def get_recent_emails(self):
        if not self.is_google_authenticated(): return None
        try:
            service = build('gmail', 'v1', credentials=self.google_creds)
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=5).execute()
            messages = results.get('messages', [])
            formatted_emails = []
            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                headers = msg_data['payload']['headers']
                subject = next((i['value'] for i in headers if i['name'] == 'Subject'), 'No Subject')
                sender = next((i['value'] for i in headers if i['name'] == 'From'), 'Unknown')
                date_str = next((i['value'] for i in headers if i['name'] == 'Date'), None)
                time_ago = 'Recent'
                if date_str:
                    try:
                        dt = parsedate_to_datetime(date_str)
                        delta = datetime.now(dt.tzinfo) - dt
                        if delta.days > 0: time_ago = f"{delta.days}d ago"
                        elif delta.seconds > 3600: time_ago = f"{delta.seconds // 3600}h ago"
                        else: time_ago = f"{delta.seconds // 60}m ago"
                    except: pass
                formatted_emails.append({'from': sender, 'subject': subject, 'snippet': msg_data['snippet'], 'time': time_ago})
            return formatted_emails
        except Exception as e:
            print(f"--- ERROR fetching emails: {e} ---")
            return []

    def get_recent_texts(self):
        if not self.is_openphone_configured():
            print("--- DEBUG: OpenPhone not configured. ---")
            return None
        try:
            url = f"{OPENPHONE_BASE_URL}/conversations?limit=5"
            headers = {"Authorization": self.openphone_api_key}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            conversations_data = data.get('data', [])
            
            formatted_texts = []
            for convo in conversations_data:
                last_activity_id = convo.get('lastActivityId')
                snippet = "No message body found." # Default snippet

                if last_activity_id:
                    try:
                        message_url = f"{OPENPHONE_BASE_URL}/messages/{last_activity_id}"
                        message_response = requests.get(message_url, headers=headers)
                        message_response.raise_for_status()
                        message_data = message_response.json()
                        # CORRECTED: The message body is in data -> text
                        snippet = message_data.get('data', {}).get('text', 'No message body')
                    except requests.exceptions.RequestException as me:
                        print(f"--- WARN: Could not fetch message detail for {last_activity_id}: {me} ---")

                from_number = 'Unknown'
                if convo.get('participants'):
                    for p in convo['participants']:
                        if p != OPENPHONE_PHONE_NUMBER:
                            from_number = p
                            break

                time_ago = 'Recent'
                timestamp_str = convo.get('lastActivityAt')
                if timestamp_str:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    delta = datetime.now(dt.tzinfo) - dt
                    if delta.days > 0: time_ago = f"{delta.days}d ago"
                    elif delta.seconds > 3600: time_ago = f"{delta.seconds // 3600}h ago"
                    else: time_ago = f"{delta.seconds // 60}m ago"
                
                formatted_texts.append({'from': from_number, 'snippet': snippet, 'time': time_ago})
            return formatted_texts
        except requests.exceptions.RequestException as e:
            print(f"--- ERROR fetching texts from OpenPhone: {e} ---")
            if hasattr(e, 'response') and e.response is not None:
                print(f"OpenPhone API Error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            print(f"--- An unexpected error occurred while processing texts: {e} ---")
            return []
