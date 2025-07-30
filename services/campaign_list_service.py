"""
Campaign List Service - Manage campaign lists and contact selection
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_, or_, not_
from crm_database import db, Contact, CampaignList, CampaignListMember, CSVImport, Activity, ContactFlag


class CampaignListService:
    
    def create_list(self, name: str, description: str = None, 
                   filter_criteria: Dict = None, is_dynamic: bool = False,
                   created_by: str = None) -> CampaignList:
        """Create a new campaign list"""
        campaign_list = CampaignList(
            name=name,
            description=description,
            filter_criteria=filter_criteria,
            is_dynamic=is_dynamic,
            created_by=created_by
        )
        db.session.add(campaign_list)
        db.session.commit()
        
        # If dynamic, populate it based on criteria
        if is_dynamic and filter_criteria:
            self.refresh_dynamic_list(campaign_list.id)
        
        return campaign_list
    
    def add_contacts_to_list(self, list_id: int, contact_ids: List[int], 
                            added_by: str = None) -> Dict[str, int]:
        """Add multiple contacts to a list"""
        results = {'added': 0, 'already_exists': 0, 'errors': 0}
        
        for contact_id in contact_ids:
            try:
                # Check if already in list
                existing = CampaignListMember.query.filter_by(
                    list_id=list_id, 
                    contact_id=contact_id
                ).first()
                
                if existing:
                    if existing.status == 'removed':
                        # Reactivate removed member
                        existing.status = 'active'
                        existing.added_at = datetime.utcnow()
                        results['added'] += 1
                    else:
                        results['already_exists'] += 1
                else:
                    # Add new member
                    member = CampaignListMember(
                        list_id=list_id,
                        contact_id=contact_id,
                        added_by=added_by
                    )
                    db.session.add(member)
                    results['added'] += 1
                    
            except Exception as e:
                results['errors'] += 1
        
        db.session.commit()
        return results
    
    def remove_contacts_from_list(self, list_id: int, contact_ids: List[int]) -> int:
        """Remove contacts from a list (soft delete)"""
        count = CampaignListMember.query.filter(
            CampaignListMember.list_id == list_id,
            CampaignListMember.contact_id.in_(contact_ids),
            CampaignListMember.status == 'active'
        ).update({'status': 'removed'}, synchronize_session=False)
        
        db.session.commit()
        return count
    
    def get_list_contacts(self, list_id: int, include_removed: bool = False) -> List[Contact]:
        """Get all contacts in a list"""
        query = db.session.query(Contact).join(CampaignListMember).filter(
            CampaignListMember.list_id == list_id
        )
        
        if not include_removed:
            query = query.filter(CampaignListMember.status == 'active')
        
        return query.all()
    
    def get_list_stats(self, list_id: int) -> Dict[str, int]:
        """Get statistics for a campaign list"""
        total = CampaignListMember.query.filter_by(list_id=list_id).count()
        active = CampaignListMember.query.filter_by(
            list_id=list_id, 
            status='active'
        ).count()
        
        # Get contact stats
        contacts = self.get_list_contacts(list_id)
        
        return {
            'total_members': total,
            'active_members': active,
            'removed_members': total - active,
            'with_email': sum(1 for c in contacts if c.email),
            'with_phone': sum(1 for c in contacts if c.phone)
        }
    
    def find_contacts_by_criteria(self, criteria: Dict) -> List[Contact]:
        """Find contacts based on filter criteria"""
        query = Contact.query
        
        # CSV Import filter
        if 'csv_import_id' in criteria:
            query = query.filter_by(csv_import_id=criteria['csv_import_id'])
        
        if 'import_source' in criteria:
            query = query.filter_by(import_source=criteria['import_source'])
        
        # Date range filters
        if 'imported_after' in criteria:
            query = query.filter(Contact.imported_at >= criteria['imported_after'])
        
        if 'imported_before' in criteria:
            query = query.filter(Contact.imported_at <= criteria['imported_before'])
        
        # Contact history filters
        if 'no_recent_contact' in criteria:
            days = criteria.get('days_since_contact', 30)
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Subquery to find contacts with recent activity
            recent_contacts = db.session.query(Activity.contact_id).filter(
                Activity.created_at > cutoff_date,
                Activity.direction == 'outgoing'
            ).subquery()
            
            query = query.filter(~Contact.id.in_(recent_contacts))
        
        # Flag filters
        if 'exclude_opted_out' in criteria and criteria['exclude_opted_out']:
            opted_out = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.flag_type == 'opted_out',
                or_(ContactFlag.expires_at.is_(None), 
                    ContactFlag.expires_at > datetime.utcnow())
            ).subquery()
            
            query = query.filter(~Contact.id.in_(opted_out))
        
        # Metadata filters
        if 'has_metadata' in criteria:
            for key in criteria['has_metadata']:
                query = query.filter(Contact.contact_metadata.has_key(key))
        
        return query.all()
    
    def refresh_dynamic_list(self, list_id: int) -> Dict[str, int]:
        """Refresh a dynamic list based on its filter criteria"""
        campaign_list = CampaignList.query.get(list_id)
        if not campaign_list or not campaign_list.is_dynamic:
            return {'error': 'List not found or not dynamic'}
        
        # Get current members
        current_members = set(
            m.contact_id for m in CampaignListMember.query.filter_by(
                list_id=list_id, 
                status='active'
            ).all()
        )
        
        # Find contacts matching criteria
        matching_contacts = self.find_contacts_by_criteria(campaign_list.filter_criteria or {})
        matching_ids = set(c.id for c in matching_contacts)
        
        # Add new matches
        to_add = matching_ids - current_members
        for contact_id in to_add:
            member = CampaignListMember(
                list_id=list_id,
                contact_id=contact_id,
                added_by='system_dynamic'
            )
            db.session.add(member)
        
        # Remove non-matches
        to_remove = current_members - matching_ids
        if to_remove:
            CampaignListMember.query.filter(
                CampaignListMember.list_id == list_id,
                CampaignListMember.contact_id.in_(to_remove)
            ).update({'status': 'removed'}, synchronize_session=False)
        
        campaign_list.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'added': len(to_add),
            'removed': len(to_remove),
            'total': len(matching_ids)
        }
    
    def get_all_lists(self) -> List[CampaignList]:
        """Get all campaign lists"""
        return CampaignList.query.order_by(CampaignList.created_at.desc()).all()
    
    def duplicate_list(self, list_id: int, new_name: str, created_by: str = None) -> CampaignList:
        """Create a copy of an existing list"""
        source_list = CampaignList.query.get(list_id)
        if not source_list:
            return None
        
        # Create new list
        new_list = CampaignList(
            name=new_name,
            description=f"Copy of {source_list.name}",
            filter_criteria=source_list.filter_criteria,
            is_dynamic=False,  # Copies are static by default
            created_by=created_by
        )
        db.session.add(new_list)
        db.session.flush()
        
        # Copy active members
        members = CampaignListMember.query.filter_by(
            list_id=list_id, 
            status='active'
        ).all()
        
        for member in members:
            new_member = CampaignListMember(
                list_id=new_list.id,
                contact_id=member.contact_id,
                added_by=created_by or member.added_by
            )
            db.session.add(new_member)
        
        db.session.commit()
        return new_list