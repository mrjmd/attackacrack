"""
CSVImportRepository - Data access layer for CSVImport entities
Isolates all database queries related to CSV imports
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy import or_, and_, func, desc, asc
from sqlalchemy.orm import Query
from sqlalchemy.exc import SQLAlchemyError
from repositories.base_repository import BaseRepository, SortOrder
from crm_database import CSVImport
import logging

logger = logging.getLogger(__name__)


class CSVImportRepository(BaseRepository[CSVImport]):
    """Repository for CSVImport data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, CSVImport)
    
    def search(self, query: str, fields: Optional[List[str]] = None, limit: Optional[int] = None) -> List[CSVImport]:
        """
        Search CSV imports by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: filename, imported_by)
            limit: Maximum number of results to return
            
        Returns:
            List of matching CSV imports
        """
        if not query:
            return []
        
        try:
            search_fields = fields or ['filename', 'imported_by']
            
            conditions = []
            for field in search_fields:
                if hasattr(CSVImport, field):
                    conditions.append(getattr(CSVImport, field).ilike(f'%{query}%'))
            
            if not conditions:
                return []
            
            query_obj = self.session.query(CSVImport).filter(or_(*conditions))
            if limit:
                query_obj = query_obj.limit(limit)
                
            return query_obj.all()
        except SQLAlchemyError as e:
            logger.error(f"Error searching CSV imports: {e}")
            return []
    
    def find_by_filename(self, filename: str) -> Optional[CSVImport]:
        """
        Find CSV import by filename.
        
        Args:
            filename: Filename to search for
            
        Returns:
            CSVImport or None
        """
        return self.find_one_by(filename=filename)
    
    def find_by_import_type(self, import_type: str) -> List[CSVImport]:
        """
        Find CSV imports by import type.
        
        Args:
            import_type: Type of import ('contacts', 'properties', etc.)
            
        Returns:
            List of CSV imports of the specified type
        """
        return self.find_by(import_type=import_type)
    
    def find_by_imported_by(self, imported_by: str) -> List[CSVImport]:
        """
        Find CSV imports by user who imported them.
        
        Args:
            imported_by: User identifier
            
        Returns:
            List of CSV imports by the user
        """
        return self.find_by(imported_by=imported_by)
    
    def get_recent_imports(self, limit: int = 10) -> List[CSVImport]:
        """
        Get recent CSV imports ordered by import date.
        
        Args:
            limit: Maximum number of imports to return
            
        Returns:
            List of recent CSV imports
        """
        try:
            return self.session.query(CSVImport).order_by(
                desc(CSVImport.imported_at)
            ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting recent imports: {e}")
            return []
    
    def get_imports_by_date_range(self, start_date: datetime, end_date: datetime) -> List[CSVImport]:
        """
        Get CSV imports within a date range.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            List of CSV imports in date range
        """
        try:
            return self.session.query(CSVImport).filter(
                CSVImport.imported_at >= start_date
            ).filter(
                CSVImport.imported_at <= end_date
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting imports by date range: {e}")
            return []
    
    def get_successful_imports(self) -> List[CSVImport]:
        """
        Get CSV imports with no failures.
        
        Returns:
            List of successful CSV imports
        """
        try:
            return self.session.query(CSVImport).filter(
                or_(
                    CSVImport.failed_imports == 0,
                    CSVImport.failed_imports.is_(None)
                )
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting successful imports: {e}")
            return []
    
    def get_failed_imports(self) -> List[CSVImport]:
        """
        Get CSV imports that had failures.
        
        Returns:
            List of CSV imports with failures
        """
        try:
            return self.session.query(CSVImport).filter(
                CSVImport.failed_imports > 0
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting failed imports: {e}")
            return []
    
    def get_import_stats_by_type(self) -> Dict[str, int]:
        """
        Get statistics of imports grouped by type.
        
        Returns:
            Dictionary with counts by import type and total
        """
        try:
            stats = self.session.query(
                CSVImport.import_type,
                func.count(CSVImport.id).label('count')
            ).filter(
                CSVImport.import_type.isnot(None)
            ).group_by(CSVImport.import_type).all()
            
            result = {import_type: count for import_type, count in stats}
            result['total'] = sum(result.values())
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error getting import stats by type: {e}")
            return {}
    
    def get_import_stats_by_user(self) -> Dict[str, int]:
        """
        Get statistics of imports grouped by user.
        
        Returns:
            Dictionary with counts by user and total
        """
        try:
            stats = self.session.query(
                CSVImport.imported_by,
                func.count(CSVImport.id).label('count')
            ).filter(
                CSVImport.imported_by.isnot(None)
            ).group_by(CSVImport.imported_by).all()
            
            result = {user: count for user, count in stats}
            result['total'] = sum(result.values())
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error getting import stats by user: {e}")
            return {}
    
    def update_import_status(self, import_id: int, total_rows: int, 
                           successful_imports: int, failed_imports: int, 
                           import_metadata: Dict[str, Any]) -> Optional[CSVImport]:
        """
        Update import status after processing.
        
        Args:
            import_id: CSV import ID
            total_rows: Total rows processed
            successful_imports: Number of successful imports
            failed_imports: Number of failed imports
            import_metadata: Additional metadata about the import
            
        Returns:
            Updated CSVImport or None if not found
        """
        csv_import = self.get_by_id(import_id)
        if csv_import:
            return self.update(
                csv_import,
                total_rows=total_rows,
                successful_imports=successful_imports,
                failed_imports=failed_imports,
                import_metadata=import_metadata
            )
        return None
    
    def mark_import_completed(self, import_id: int) -> Optional[CSVImport]:
        """
        Mark import as completed with current timestamp.
        Note: CSVImport model doesn't have completed_at field, so we update metadata instead.
        
        Args:
            import_id: CSV import ID
            
        Returns:
            Updated CSVImport or None if not found
        """
        csv_import = self.get_by_id(import_id)
        if csv_import:
            metadata = csv_import.import_metadata or {}
            metadata['completed_at'] = utc_now().isoformat()
            return self.update(
                csv_import,
                import_metadata=metadata
            )
        return None
    
    def get_incomplete_imports(self) -> List[CSVImport]:
        """
        Get imports that haven't been completed or processed.
        
        Returns:
            List of incomplete CSV imports
        """
        try:
            # Only check for total_rows being None since completed_at doesn't exist in model
            return self.session.query(CSVImport).filter(
                CSVImport.total_rows.is_(None)
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting incomplete imports: {e}")
            return []
    
    def find_duplicate_filename_imports(self, filename: str) -> List[CSVImport]:
        """
        Find all imports with the same filename.
        
        Args:
            filename: Filename to search for
            
        Returns:
            List of CSV imports with the same filename
        """
        try:
            return self.session.query(CSVImport).filter(
                CSVImport.filename == filename
            ).order_by(
                desc(CSVImport.imported_at)
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding duplicate filename imports: {e}")
            return []
    
    def get_total_imports_count(self) -> int:
        """
        Get total count of all imports.
        
        Returns:
            Total number of CSV imports
        """
        return self.count()
    
    def delete_old_imports(self, days: int = 90) -> int:
        """
        Delete imports older than specified number of days.
        
        Args:
            days: Number of days to keep imports
            
        Returns:
            Number of imports deleted
        """
        cutoff_date = utc_now() - timedelta(days=days)
        filters = {'imported_at': cutoff_date}  # This should be "less than" but base repo handles equality
        
        # Use a more direct approach for date comparison
        try:
            count = self.session.query(CSVImport).filter(
                CSVImport.imported_at < cutoff_date
            ).count()
            
            # Delete the records
            deleted = self.session.query(CSVImport).filter(
                CSVImport.imported_at < cutoff_date
            ).delete(synchronize_session=False)
            
            self.session.flush()
            return deleted
        except SQLAlchemyError as e:
            logger.error(f"Error deleting old imports: {e}")
            self.session.rollback()
            return 0
    
    def get_imports_with_errors(self) -> List[CSVImport]:
        """
        Get imports that had processing errors.
        
        Returns:
            List of CSV imports with errors in metadata
        """
        try:
            # For SQLite/PostgreSQL compatibility, check if metadata contains 'errors' key
            return self.session.query(CSVImport).filter(
                CSVImport.import_metadata.isnot(None)
            ).filter(
                func.json_extract(CSVImport.import_metadata, '$.errors').isnot(None)
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting imports with errors: {e}")
            return []
