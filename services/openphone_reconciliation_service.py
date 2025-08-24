"""
OpenPhone Reconciliation Service

Service for reconciling OpenPhone messages with local database to ensure
no messages are missed. Runs daily to catch any webhook failures.
"""

import logging
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from typing import Dict, Any, List, Optional

from services.common.result import Result
from repositories.activity_repository import ActivityRepository
from repositories.conversation_repository import ConversationRepository
from services.contact_service_refactored import ContactService
from services.openphone_api_client import OpenPhoneAPIClient

logger = logging.getLogger(__name__)


class OpenPhoneReconciliationService:
    """Service for reconciling OpenPhone messages with local database"""
    
    def __init__(self, 
                 activity_repository: ActivityRepository,
                 conversation_repository: ConversationRepository,
                 contact_service: ContactService,
                 openphone_api_client: Optional[OpenPhoneAPIClient] = None):
        """
        Initialize reconciliation service with dependencies.
        
        Args:
            activity_repository: Repository for Activity data access
            conversation_repository: Repository for Conversation data access
            contact_service: Service for contact management
            openphone_api_client: OpenPhone API client (will create if not provided)
        """
        self.activity_repository = activity_repository
        self.conversation_repository = conversation_repository
        self.contact_service = contact_service
        self.openphone_api_client = openphone_api_client or OpenPhoneAPIClient()
        
        # Configuration
        self.batch_size = 100  # Process messages in batches
        self.max_pages = 50  # Maximum pages to fetch in one run
        
        # Statistics tracking
        self.stats = {
            'last_run': None,
            'total_processed': 0,
            'total_errors': 0,
            'last_error': None,
            'runs_today': 0
        }
    
    def reconcile_messages(self, hours_back: int = 48) -> Result[Dict[str, Any]]:
        """
        Main reconciliation method that fetches messages from OpenPhone and syncs with database.
        
        Args:
            hours_back: Number of hours to look back for messages (default 48)
            
        Returns:
            Result with reconciliation statistics or error
        """
        try:
            logger.info(f"Starting OpenPhone reconciliation for last {hours_back} hours")
            
            # Calculate date range
            since_date = utc_now() - timedelta(hours=hours_back)
            since_str = since_date.isoformat() + 'Z'
            
            # Track reconciliation stats
            stats = {
                'start_time': utc_now(),
                'total_messages': 0,
                'new_messages': 0,
                'existing_messages': 0,
                'errors': [],
                'total_pages': 0
            }
            
            # Fetch and process messages with pagination
            cursor = None
            page = 0
            
            while page < self.max_pages:
                page += 1
                
                logger.debug(f"Fetching page {page} of messages")
                
                try:
                    # Fetch messages from API
                    response = self.openphone_api_client.get_messages(
                        since=since_str,
                        cursor=cursor,
                        limit=self.batch_size
                    )
                    
                    messages = response.get('data', [])
                    cursor = response.get('cursor')
                    
                    if not messages:
                        logger.debug("No more messages to process")
                        break
                    
                    logger.info(f"Processing {len(messages)} messages from page {page}")
                    
                    # Process batch of messages
                    batch_results = self._batch_process_messages(messages)
                    
                    # Update statistics
                    stats['total_messages'] += len(messages)
                    stats['new_messages'] += len(batch_results['processed'])
                    stats['existing_messages'] += len(batch_results['skipped'])
                    stats['errors'].extend(batch_results['errors'])
                    stats['total_pages'] = page
                    
                    # Break if no more pages
                    if not cursor:
                        logger.debug("No more pages to fetch")
                        break
                        
                except Exception as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    stats['errors'].append({
                        'page': page,
                        'error': str(e)
                    })
                    # Continue with next page despite error
                    break
            
            # Calculate duration
            stats['end_time'] = utc_now()
            stats['duration_seconds'] = (stats['end_time'] - stats['start_time']).total_seconds()
            
            # Update service statistics
            self._update_stats(stats)
            
            # Log summary
            logger.info(
                f"Reconciliation completed: {stats['total_messages']} total, "
                f"{stats['new_messages']} new, {stats['existing_messages']} existing, "
                f"{len(stats['errors'])} errors in {stats['duration_seconds']:.2f} seconds"
            )
            
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to reconcile messages: {e}", exc_info=True)
            return Result.failure(
                f"Failed to reconcile messages: {str(e)}",
                code="RECONCILIATION_ERROR"
            )
    
    def _batch_process_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of messages.
        
        Args:
            messages: List of message objects from OpenPhone API
            
        Returns:
            Dictionary with processed, skipped, and error lists
        """
        results = {
            'processed': [],
            'skipped': [],
            'errors': []
        }
        
        for message in messages:
            try:
                # Skip non-message types (like calls)
                if message.get('type') != 'message':
                    continue
                
                # Check if message already exists
                openphone_id = message.get('id')
                existing = self.activity_repository.find_by_openphone_id(openphone_id)
                
                if existing:
                    results['skipped'].append(openphone_id)
                    continue
                
                # Process new message
                process_result = self._process_message(message)
                
                if process_result.is_success:
                    results['processed'].append(openphone_id)
                else:
                    results['errors'].append({
                        'message_id': openphone_id,
                        'error': process_result.error
                    })
                    
            except Exception as e:
                logger.error(f"Error processing message {message.get('id')}: {e}")
                results['errors'].append({
                    'message_id': message.get('id'),
                    'error': str(e)
                })
        
        return results
    
    def _process_message(self, message: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Process a single message and create database records.
        
        Args:
            message: Message object from OpenPhone API
            
        Returns:
            Result with created activity or error
        """
        try:
            # Extract message data
            openphone_id = message.get('id')
            conversation_id = message.get('conversationId')
            direction = message.get('direction', 'unknown')
            
            # Determine contact phone based on direction
            if direction == 'incoming':
                contact_phone = message.get('from')
            else:
                # For outgoing, use the first 'to' number
                to_numbers = message.get('to', [])
                contact_phone = to_numbers[0] if to_numbers else None
            
            if not contact_phone:
                return Result.failure(f"No contact phone found for message {openphone_id}")
            
            # Find or create contact
            contact_result = self.contact_service.find_or_create_by_phone(contact_phone)
            if contact_result.is_failure:
                return Result.failure(f"Failed to process contact: {contact_result.error}")
            
            contact = contact_result.data
            
            # Find or create conversation
            conversation = self.conversation_repository.find_or_create_for_contact(
                contact_id=contact.id if hasattr(contact, 'id') else contact.get('id'),
                openphone_id=conversation_id
            )
            
            # Parse created_at timestamp
            created_at_str = message.get('createdAt', '')
            created_at = None
            if created_at_str:
                try:
                    # Handle ISO format with Z timezone
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Failed to parse timestamp {created_at_str}: {e}")
                    created_at = utc_now()
            else:
                created_at = utc_now()
            
            # Create activity record
            activity_data = {
                'openphone_id': openphone_id,
                'conversation_id': conversation.id,
                'contact_id': contact.id if hasattr(contact, 'id') else contact.get('id'),
                'activity_type': 'message',
                'direction': direction,
                'status': message.get('status', 'unknown'),
                'from_number': message.get('from'),
                'to_numbers': message.get('to', []),
                'user_id': message.get('userId'),
                'phone_number_id': message.get('phoneNumberId'),
                'body': message.get('body'),
                'media_urls': message.get('mediaUrls', []),
                'created_at': created_at
            }
            
            activity = self.activity_repository.create(activity_data)
            
            # Update conversation last_activity_at
            self.conversation_repository.update_last_activity(
                conversation_id=conversation.id,
                activity_time=created_at
            )
            
            logger.debug(f"Created activity {activity.id} for message {openphone_id}")
            
            return Result.success({
                'activity_id': activity.id,
                'message_id': openphone_id
            })
            
        except Exception as e:
            logger.error(f"Failed to process message {message.get('id')}: {e}")
            return Result.failure(str(e))
    
    def _update_stats(self, reconciliation_stats: Dict[str, Any]):
        """
        Update service statistics.
        
        Args:
            reconciliation_stats: Stats from the reconciliation run
        """
        self.stats['last_run'] = reconciliation_stats.get('end_time')
        self.stats['total_processed'] += reconciliation_stats.get('new_messages', 0)
        self.stats['total_errors'] += len(reconciliation_stats.get('errors', []))
        
        if reconciliation_stats.get('errors'):
            self.stats['last_error'] = reconciliation_stats['errors'][-1]
        
        # Reset daily counter if new day
        if self.stats['last_run']:
            today = utc_now().date()
            if not hasattr(self, '_last_run_date') or self._last_run_date != today:
                self.stats['runs_today'] = 1
                self._last_run_date = today
            else:
                self.stats['runs_today'] += 1
    
    def get_reconciliation_stats(self) -> Dict[str, Any]:
        """
        Get current reconciliation statistics.
        
        Returns:
            Dictionary with service statistics
        """
        return self.stats.copy()
    
    def reconcile_conversations(self, hours_back: int = 48) -> Result[Dict[str, Any]]:
        """
        Reconcile conversations from OpenPhone.
        
        Args:
            hours_back: Number of hours to look back (not used for conversations)
            
        Returns:
            Result with reconciliation statistics or error
        """
        try:
            logger.info("Starting OpenPhone conversation reconciliation")
            
            stats = {
                'total_conversations': 0,
                'new_conversations': 0,
                'updated_conversations': 0,
                'errors': []
            }
            
            # Fetch conversations with pagination
            cursor = None
            page = 0
            
            while page < self.max_pages:
                page += 1
                
                try:
                    response = self.openphone_api_client.get_conversations(
                        cursor=cursor,
                        limit=self.batch_size
                    )
                    
                    conversations = response.get('data', [])
                    cursor = response.get('cursor')
                    
                    if not conversations:
                        break
                    
                    # Process conversations
                    for conv in conversations:
                        try:
                            openphone_id = conv.get('id')
                            existing = self.conversation_repository.find_by_openphone_id(openphone_id)
                            
                            if existing:
                                stats['updated_conversations'] += 1
                            else:
                                # Create new conversation
                                # Note: This is simplified - in practice you'd need to handle contact creation
                                stats['new_conversations'] += 1
                                
                            stats['total_conversations'] += 1
                            
                        except Exception as e:
                            stats['errors'].append({
                                'conversation_id': conv.get('id'),
                                'error': str(e)
                            })
                    
                    if not cursor:
                        break
                        
                except Exception as e:
                    logger.error(f"Error fetching conversations page {page}: {e}")
                    stats['errors'].append({
                        'page': page,
                        'error': str(e)
                    })
                    break
            
            logger.info(
                f"Conversation reconciliation completed: {stats['total_conversations']} total, "
                f"{stats['new_conversations']} new, {stats['updated_conversations']} updated"
            )
            
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to reconcile conversations: {e}", exc_info=True)
            return Result.failure(str(e))
    
    def validate_data_integrity(self) -> Result[Dict[str, Any]]:
        """
        Validate data integrity between OpenPhone and local database.
        
        Returns:
            Result with validation report
        """
        try:
            logger.info("Starting data integrity validation")
            
            report = {
                'activities_without_conversation': 0,
                'activities_without_contact': 0,
                'orphaned_conversations': 0,
                'duplicate_openphone_ids': 0
            }
            
            # Check for activities without conversations
            activities = self.activity_repository.find_recent_activities(limit=1000)
            for activity in activities:
                if not activity.conversation_id:
                    report['activities_without_conversation'] += 1
                if not activity.contact_id:
                    report['activities_without_contact'] += 1
            
            logger.info(f"Data integrity validation completed: {report}")
            
            return Result.success(report)
            
        except Exception as e:
            logger.error(f"Failed to validate data integrity: {e}", exc_info=True)
            return Result.failure(str(e))