"""
Opt-Out Audit Repository

Repository for managing opt-out audit trail records.
Provides data access methods for tracking opt-out/opt-in events.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from crm_database import OptOutAudit


class OptOutAuditRepository:
    """Repository for OptOutAudit entity operations"""
    
    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
    
    def create(self, **kwargs) -> OptOutAudit:
        """
        Create a new opt-out audit log entry.
        
        Args:
            **kwargs: Audit log attributes
            
        Returns:
            Created OptOutAudit instance
        """
        audit = OptOutAudit(**kwargs)
        self.session.add(audit)
        self.session.commit()
        self.session.refresh(audit)
        return audit
    
    def find_by_contact_id(self, contact_id: int) -> List[OptOutAudit]:
        """
        Find all audit logs for a specific contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            List of OptOutAudit records
        """
        return self.session.query(OptOutAudit)\
            .filter_by(contact_id=contact_id)\
            .order_by(desc(OptOutAudit.created_at))\
            .all()
    
    def find_since(self, since_date: datetime) -> List[OptOutAudit]:
        """
        Find all audit logs since a specific date.
        
        Args:
            since_date: Date to search from
            
        Returns:
            List of OptOutAudit records
        """
        return self.session.query(OptOutAudit)\
            .filter(OptOutAudit.created_at >= since_date)\
            .order_by(desc(OptOutAudit.created_at))\
            .all()
    
    def find_by_phone_number(self, phone_number: str) -> List[OptOutAudit]:
        """
        Find all audit logs for a specific phone number.
        
        Args:
            phone_number: Phone number to search
            
        Returns:
            List of OptOutAudit records
        """
        return self.session.query(OptOutAudit)\
            .filter_by(phone_number=phone_number)\
            .order_by(desc(OptOutAudit.created_at))\
            .all()
    
    def find_by_keyword(self, keyword: str) -> List[OptOutAudit]:
        """
        Find all audit logs that used a specific keyword.
        
        Args:
            keyword: Keyword to search for
            
        Returns:
            List of OptOutAudit records
        """
        return self.session.query(OptOutAudit)\
            .filter_by(keyword_used=keyword)\
            .order_by(desc(OptOutAudit.created_at))\
            .all()
    
    def find_by_method(self, method: str) -> List[OptOutAudit]:
        """
        Find all audit logs by opt-out method.
        
        Args:
            method: Opt-out method (e.g., 'sms_keyword', 'manual')
            
        Returns:
            List of OptOutAudit records
        """
        return self.session.query(OptOutAudit)\
            .filter_by(opt_out_method=method)\
            .order_by(desc(OptOutAudit.created_at))\
            .all()
    
    def find_all(self) -> List[OptOutAudit]:
        """
        Find all audit logs.
        
        Returns:
            List of all OptOutAudit records
        """
        return self.session.query(OptOutAudit)\
            .order_by(desc(OptOutAudit.created_at))\
            .all()
    
    def count_by_keyword(self) -> Dict[str, int]:
        """
        Count audit logs grouped by keyword.
        
        Returns:
            Dictionary mapping keywords to counts
        """
        results = self.session.query(
            OptOutAudit.keyword_used,
            func.count(OptOutAudit.id)
        ).group_by(OptOutAudit.keyword_used).all()
        
        return {keyword: count for keyword, count in results if keyword}
    
    def count_since(self, since_date: datetime) -> int:
        """
        Count audit logs since a specific date.
        
        Args:
            since_date: Date to count from
            
        Returns:
            Number of audit logs
        """
        return self.session.query(OptOutAudit)\
            .filter(OptOutAudit.created_at >= since_date)\
            .count()
    
    def get_latest_for_contact(self, contact_id: int) -> Optional[OptOutAudit]:
        """
        Get the most recent audit log for a contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Most recent OptOutAudit or None
        """
        return self.session.query(OptOutAudit)\
            .filter_by(contact_id=contact_id)\
            .order_by(desc(OptOutAudit.created_at))\
            .first()
    
    def delete_old_audits(self, older_than: datetime) -> int:
        """
        Delete audit logs older than a specific date.
        
        Args:
            older_than: Delete records older than this date
            
        Returns:
            Number of deleted records
        """
        count = self.session.query(OptOutAudit)\
            .filter(OptOutAudit.created_at < older_than)\
            .delete()
        self.session.commit()
        return count