from crm_database import Contact, ContactFlag, Conversation, Activity, db
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_, func, exists
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

class ContactService:
    def __init__(self):
        self.session = db.session
    
    def get_contacts_page(
        self,
        search_query: str = '',
        filter_type: str = 'all',
        sort_by: str = 'name',
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """Get paginated contacts with filters and search"""
        query = Contact.query
        
        # Apply search
        if search_query:
            query = query.filter(
                or_(
                    Contact.first_name.ilike(f'%{search_query}%'),
                    Contact.last_name.ilike(f'%{search_query}%'),
                    Contact.phone.ilike(f'%{search_query}%'),
                    Contact.email.ilike(f'%{search_query}%'),
                    Contact.company.ilike(f'%{search_query}%')
                )
            )
        
        # Apply filters
        if filter_type == 'has_phone':
            query = query.filter(Contact.phone.isnot(None))
        elif filter_type == 'has_email':
            query = query.filter(Contact.email.isnot(None))
        elif filter_type == 'has_conversation':
            query = query.filter(
                exists().where(Conversation.contact_id == Contact.id)
            )
        elif filter_type == 'no_conversation':
            query = query.filter(
                ~exists().where(Conversation.contact_id == Contact.id)
            )
        elif filter_type == 'opted_out':
            query = query.filter(
                exists().where(
                    and_(
                        ContactFlag.contact_id == Contact.id,
                        ContactFlag.flag_type == 'opted_out'
                    )
                )
            )
        elif filter_type == 'recent_activity':
            # Contacts with activity in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            query = query.join(Conversation).filter(
                Conversation.last_activity_at >= thirty_days_ago
            )
        
        # Apply sorting
        if sort_by == 'name':
            query = query.order_by(Contact.last_name, Contact.first_name)
        elif sort_by == 'created':
            query = query.order_by(Contact.created_at.desc())
        elif sort_by == 'recent_activity':
            query = query.outerjoin(Conversation).group_by(Contact.id).order_by(
                func.max(Conversation.last_activity_at).desc().nullslast()
            )
        
        # Get total count
        total_count = query.count()
        
        # Paginate
        contacts = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Enhance contacts with metadata
        enhanced_contacts = self._enhance_contacts(contacts)
        
        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page
        
        return {
            'contacts': enhanced_contacts,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    
    def _enhance_contacts(self, contacts: List[Contact]) -> List[Dict[str, Any]]:
        """Add metadata to contacts"""
        if not contacts:
            return []
        
        contact_ids = [c.id for c in contacts]
        
        # Get conversation counts
        conv_counts = db.session.query(
            Conversation.contact_id,
            func.count(Activity.id).label('message_count'),
            func.max(Activity.created_at).label('last_activity')
        ).join(
            Activity, Activity.conversation_id == Conversation.id
        ).filter(
            Conversation.contact_id.in_(contact_ids)
        ).group_by(
            Conversation.contact_id
        ).all()
        
        conv_map = {cc[0]: {'message_count': cc[1], 'last_activity': cc[2]} for cc in conv_counts}
        
        # Get flags
        flags = ContactFlag.query.filter(
            ContactFlag.contact_id.in_(contact_ids)
        ).all()
        
        flag_map = {}
        for flag in flags:
            if flag.contact_id not in flag_map:
                flag_map[flag.contact_id] = []
            flag_map[flag.contact_id].append(flag.flag_type)
        
        # Build enhanced list
        enhanced = []
        for contact in contacts:
            conv_data = conv_map.get(contact.id, {'message_count': 0, 'last_activity': None})
            enhanced.append({
                'contact': contact,
                'message_count': conv_data['message_count'],
                'last_activity': conv_data['last_activity'],
                'flags': flag_map.get(contact.id, []),
                'has_conversation': contact.id in conv_map
            })
        
        return enhanced
    
    def bulk_action(self, action: str, contact_ids: List[int], **kwargs) -> Tuple[bool, str]:
        """Perform bulk actions on contacts"""
        if not contact_ids:
            return False, "No contacts selected"
        
        try:
            if action == 'delete':
                Contact.query.filter(Contact.id.in_(contact_ids)).delete(synchronize_session=False)
                db.session.commit()
                return True, f"Deleted {len(contact_ids)} contacts"
            
            elif action == 'flag':
                flag_type = kwargs.get('flag_type', 'opted_out')
                for contact_id in contact_ids:
                    existing = ContactFlag.query.filter_by(
                        contact_id=contact_id,
                        flag_type=flag_type
                    ).first()
                    if not existing:
                        flag = ContactFlag(
                            contact_id=contact_id,
                            flag_type=flag_type,
                            flagged_at=datetime.now()
                        )
                        db.session.add(flag)
                db.session.commit()
                return True, f"Flagged {len(contact_ids)} contacts as {flag_type}"
            
            elif action == 'unflag':
                flag_type = kwargs.get('flag_type', 'opted_out')
                ContactFlag.query.filter(
                    ContactFlag.contact_id.in_(contact_ids),
                    ContactFlag.flag_type == flag_type
                ).delete(synchronize_session=False)
                db.session.commit()
                return True, f"Removed {flag_type} flag from {len(contact_ids)} contacts"
            
            elif action == 'export':
                # Export logic would go here
                return True, "Export functionality not yet implemented"
            
            else:
                return False, f"Unknown action: {action}"
                
        except Exception as e:
            db.session.rollback()
            return False, f"Error: {str(e)}"

    def add_contact(self, first_name, last_name, email=None, phone=None): # Changed kwargs to explicit args
        try:
            new_contact = Contact(first_name=first_name, last_name=last_name, email=email, phone=phone)
            self.session.add(new_contact)
            self.session.commit()
            return new_contact
        except IntegrityError:
            self.session.rollback()
            # Handle cases where email or phone might already exist if unique constraint is violated
            return None # Or raise a more specific error

    def get_all_contacts(self):
        return self.session.query(Contact).all()
    
    def search_contacts(self, query: str, limit: int = 20) -> List[Contact]:
        """Quick search for contacts"""
        return Contact.query.filter(
            or_(
                Contact.first_name.ilike(f'%{query}%'),
                Contact.last_name.ilike(f'%{query}%'),
                Contact.phone.ilike(f'%{query}%'),
                Contact.email.ilike(f'%{query}%')
            )
        ).limit(limit).all()

    def get_contact_by_id(self, contact_id):
        # Refactored: Using Session.get() instead of Query.get()
        return self.session.get(Contact, contact_id)

    def get_contact_by_phone(self, phone_number):
        """Finds a contact by their phone number."""
        if not phone_number:
            return None
        return self.session.query(Contact).filter_by(phone=phone_number).first()

    def update_contact(self, contact, **kwargs):
        # Accept either a Contact object or an ID
        if isinstance(contact, int):
            contact = self.session.get(Contact, contact)
            if not contact:
                return None
        
        for key, value in kwargs.items():
            setattr(contact, key, value)
        self.session.commit()
        return contact

    def delete_contact(self, contact):
        # Accept either a Contact object or an ID
        if isinstance(contact, int):
            contact = self.session.get(Contact, contact)
            if not contact:
                return False
        
        self.session.delete(contact)
        self.session.commit()
        return True
