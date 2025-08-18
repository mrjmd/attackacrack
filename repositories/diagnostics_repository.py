"""
DiagnosticsRepository - Data access layer for system diagnostics
Handles database connectivity checks, model counts, and system health queries

This repository is specialized and doesn't inherit from BaseRepository
because it performs system-level queries rather than CRUD operations on a specific model.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from datetime import datetime

from crm_database import Contact, Conversation, Activity, Campaign, Todo

logger = logging.getLogger(__name__)


class DiagnosticsRepository:
    """
    Repository for system diagnostics and health checks.
    
    This repository handles:
    - Database connectivity verification
    - Model count queries
    - Database statistics
    - Connection pool monitoring
    """
    
    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
    
    # Database Connectivity Methods
    
    def check_database_connection(self) -> bool:
        """
        Check if database connection is working.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            self.session.execute(text('SELECT 1'))
            logger.debug("Database connection test successful")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_connection_error_details(self) -> Optional[str]:
        """
        Get detailed connection error information.
        
        Returns:
            Error message if connection fails, None if successful
        """
        try:
            self.session.execute(text('SELECT 1'))
            return None  # No error
        except SQLAlchemyError as e:
            error_msg = str(e)
            logger.error(f"Database connection error details: {error_msg}")
            return error_msg
    
    # Model Count Methods
    
    def get_contact_count(self) -> int:
        """
        Get total number of contacts.
        
        Returns:
            Count of contacts, 0 on error
        """
        try:
            count = self.session.query(Contact).count()
            logger.debug(f"Contact count: {count}")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error getting contact count: {e}")
            return 0
    
    def get_conversation_count(self) -> int:
        """
        Get total number of conversations.
        
        Returns:
            Count of conversations, 0 on error
        """
        try:
            count = self.session.query(Conversation).count()
            logger.debug(f"Conversation count: {count}")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error getting conversation count: {e}")
            return 0
    
    def get_activity_count(self) -> int:
        """
        Get total number of activities.
        
        Returns:
            Count of activities, 0 on error
        """
        try:
            count = self.session.query(Activity).count()
            logger.debug(f"Activity count: {count}")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error getting activity count: {e}")
            return 0
    
    def get_campaign_count(self) -> int:
        """
        Get total number of campaigns.
        
        Returns:
            Count of campaigns, 0 on error
        """
        try:
            count = self.session.query(Campaign).count()
            logger.debug(f"Campaign count: {count}")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error getting campaign count: {e}")
            return 0
    
    def get_todo_count(self) -> int:
        """
        Get total number of todos.
        
        Returns:
            Count of todos, 0 on error
        """
        try:
            count = self.session.query(Todo).count()
            logger.debug(f"Todo count: {count}")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error getting todo count: {e}")
            return 0
    
    def get_all_model_counts(self) -> Dict[str, int]:
        """
        Get counts for all models at once.
        
        Returns:
            Dictionary with model counts
        """
        counts = {
            'contacts': self.get_contact_count(),
            'conversations': self.get_conversation_count(),
            'activities': self.get_activity_count(),
            'campaigns': self.get_campaign_count(),
            'todos': self.get_todo_count()
        }
        
        logger.debug(f"All model counts: {counts}")
        return counts
    
    # Advanced Database Statistics
    
    def get_database_size_info(self) -> Dict[str, Any]:
        """
        Get database size information.
        
        Returns:
            Dictionary with size information
        """
        try:
            # This is PostgreSQL specific - adjust for other databases
            result = self.session.execute(text("""
                SELECT pg_database_size(current_database()) as size_bytes
            """))
            size_bytes = result.scalar()
            
            return {
                'size_bytes': size_bytes,
                'size_mb': round(size_bytes / 1024 / 1024, 2) if size_bytes else 0
            }
        except SQLAlchemyError as e:
            logger.error(f"Error getting database size: {e}")
            return {'size_bytes': 0, 'size_mb': 0}
    
    def get_table_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get table-level statistics.
        
        Returns:
            Dictionary with table statistics
        """
        try:
            # PostgreSQL specific query
            result = self.session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins + n_tup_upd + n_tup_del as total_operations,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY total_operations DESC
            """))
            
            stats = {}
            for row in result.fetchall():
                schema, table, operations, size_bytes = row
                stats[table] = {
                    'row_count': operations,  # Approximation
                    'size_bytes': size_bytes
                }
            
            return stats
        except SQLAlchemyError as e:
            logger.error(f"Error getting table statistics: {e}")
            return {}
    
    def get_connection_pool_stats(self) -> Dict[str, Any]:
        """
        Get database connection pool statistics.
        
        Returns:
            Dictionary with connection pool stats
        """
        try:
            engine = self.session.get_bind()
            pool = engine.pool
            
            return {
                'pool_size': pool.size(),
                'checked_in': pool.checked_in(),
                'checked_out': pool.checked_out(),
                'overflow': pool.overflow(),
                'invalid': getattr(pool, 'invalid', lambda: 0)()
            }
        except (AttributeError, SQLAlchemyError) as e:
            logger.error(f"Error getting connection pool stats: {e}")
            return {}
    
    # Comprehensive Health Check
    
    def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dictionary with health check results
        """
        health_check = {
            'timestamp': datetime.utcnow().isoformat(),
            'database_connected': False,
            'model_counts': {},
            'connection_pool': {},
            'database_size': {}
        }
        
        # Test database connection
        if self.check_database_connection():
            health_check['database_connected'] = True
            
            # Get model counts if connection is good
            try:
                health_check['model_counts'] = self.get_all_model_counts()
                health_check['connection_pool'] = self.get_connection_pool_stats()
                health_check['database_size'] = self.get_database_size_info()
            except Exception as e:
                logger.error(f"Error during health check: {e}")
                health_check['model_counts'] = {}
        else:
            # Include error details if connection failed
            error = self.get_connection_error_details()
            if error:
                health_check['error'] = error
        
        return health_check
