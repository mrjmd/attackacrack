"""
Opt-Out Service

Comprehensive service for handling SMS opt-out and opt-in requests.
Manages keyword detection, flag creation, audit logging, and confirmation messages.
"""

import re
import logging
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from typing import List, Optional, Dict, Any

from services.common.result import Result
from repositories.contact_flag_repository import ContactFlagRepository
from repositories.opt_out_audit_repository import OptOutAuditRepository
from repositories.contact_repository import ContactRepository

logger = logging.getLogger(__name__)


class OptOutService:
    """Service for managing opt-out/opt-in processing"""
    
    # Opt-out keywords (case-insensitive) - these are exact matches or start of message
    OPT_OUT_KEYWORDS = [
        'stop', 'stop all', 'stopall', 'unsubscribe', 
        'optout', 'opt out', 'opt-out', 'remove me', 'delete me'
    ]
    
    # Additional keywords that need context checking
    CONTEXT_KEYWORDS = ['end', 'quit', 'cancel', 'remove', 'delete']
    
    # Opt-in keywords (case-insensitive)
    OPT_IN_KEYWORDS = [
        'start', 'subscribe', 'yes', 'unstop', 'resume', 'restart',
        'optin', 'opt in', 'opt-in'
    ]
    
    # Confirmation messages
    OPT_OUT_CONFIRMATION = "You've been unsubscribed. Reply START to resubscribe."
    OPT_IN_CONFIRMATION = "You've been resubscribed to messages. Reply STOP to unsubscribe."
    
    def __init__(self,
                 contact_flag_repository: ContactFlagRepository,
                 opt_out_audit_repository: OptOutAuditRepository,
                 sms_service: Any,  # SMS service for sending confirmations
                 contact_repository: ContactRepository):
        """
        Initialize with injected dependencies.
        
        Args:
            contact_flag_repository: Repository for contact flags
            opt_out_audit_repository: Repository for audit logs
            sms_service: Service for sending SMS messages
            contact_repository: Repository for contact operations
        """
        self.contact_flag_repository = contact_flag_repository
        self.opt_out_audit_repository = opt_out_audit_repository
        self.sms_service = sms_service
        self.contact_repository = contact_repository
    
    def contains_opt_out_keyword(self, message: Optional[str]) -> bool:
        """
        Check if a message contains opt-out keywords.
        
        Args:
            message: Message text to check
            
        Returns:
            True if opt-out keyword found, False otherwise
        """
        if not message:
            return False
        
        message_lower = message.lower().strip()
        
        # Check for exact matches first
        if message_lower in self.OPT_OUT_KEYWORDS:
            return True
        
        # Check if message starts with any keyword
        for keyword in self.OPT_OUT_KEYWORDS:
            if message_lower.startswith(keyword + ' ') or message_lower == keyword:
                return True
        
        # Check for key opt-out words/phrases anywhere in the message
        opt_out_phrases = ['unsubscribe', 'stop', 'optout', 'opt out', 'opt-out']
        for keyword in opt_out_phrases:
            if keyword in message_lower:
                # Make sure it's being used in opt-out context
                # Avoid false positives like "stop by" or "unsubscribe link"
                if keyword == 'stop':
                    false_contexts = ['stop by', 'stop at', 'stop in']
                elif keyword == 'unsubscribe':
                    false_contexts = ['unsubscribe link', 'to unsubscribe']
                else:
                    false_contexts = []
                
                if not any(ctx in message_lower for ctx in false_contexts):
                    return True
        
        # Check for context-sensitive keywords as whole words
        for keyword in self.CONTEXT_KEYWORDS:
            # Use word boundaries to avoid matching "stop" in "stopwatch"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_lower):
                # But exclude if it's clearly not an opt-out context
                if keyword in ['stop', 'end', 'quit', 'cancel']:
                    # Check for common false positive phrases
                    false_positives = [
                        f'{keyword} by',
                        f'will {keyword}',
                        f'to {keyword}',
                        f"don't {keyword}",
                        f"not {keyword}",
                        f"never {keyword}",
                        f'{keyword} the',  # "cancel the meeting", "end the project"
                        f'{keyword} my',   # "cancel my appointment"
                        f'{keyword} your', # "stop your work"
                        f'{keyword} our',  # "end our partnership"
                        f'{keyword} this', # "cancel this order"
                        f'{keyword} that'  # "stop that activity"
                    ]
                    if any(phrase in message_lower for phrase in false_positives):
                        continue
                return True
        
        return False
    
    def contains_opt_in_keyword(self, message: Optional[str]) -> bool:
        """
        Check if a message contains opt-in keywords.
        
        Args:
            message: Message text to check
            
        Returns:
            True if opt-in keyword found, False otherwise
        """
        if not message:
            return False
        
        message_lower = message.lower().strip()
        
        # Check for exact matches first
        if message_lower in self.OPT_IN_KEYWORDS:
            return True
        
        # Special case for "yes" - only exact match
        if message_lower == 'yes':
            return True
        
        # Check if message starts with keyword but exclude false positives
        for keyword in self.OPT_IN_KEYWORDS:
            if message_lower.startswith(keyword + ' ') or message_lower == keyword:
                # Check for false positives for these keywords
                if keyword in ['start', 'resume', 'subscribe']:
                    false_start_phrases = [
                        f'{keyword} next',
                        f'{keyword} tomorrow',
                        f'{keyword} later',
                        f'{keyword} the',
                        f'{keyword} my',
                        f'{keyword} your',
                        f'{keyword} work'
                    ]
                    if any(message_lower.startswith(phrase) for phrase in false_start_phrases):
                        continue
                return True
        
        # Check for keyword as a whole word
        for keyword in ['start', 'subscribe', 'resume']:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_lower):
                # Exclude false positives
                false_positives = [
                    f"let's {keyword}",
                    f'to {keyword}',
                    f'will {keyword}',
                    f'{keyword} the',
                    f'{keyword} next',
                    f'{keyword} tomorrow',
                    f'{keyword} later',
                    f'{keyword} work',
                    f'{keyword} my',
                    f'{keyword} your'
                ]
                if any(phrase in message_lower for phrase in false_positives):
                    continue
                return True
        
        return False
    
    def process_opt_out(self, contact: Any, message: str, source: str = 'sms_webhook') -> Result[Dict[str, Any]]:
        """
        Process an opt-out request for a contact.
        
        Args:
            contact: Contact object
            message: The message that triggered opt-out
            source: Source of the opt-out request
            
        Returns:
            Result with processing status
        """
        try:
            # Check if already opted out
            existing_flags = self.contact_flag_repository.find_active_flags(
                contact.id, flag_type='opted_out'
            )
            
            if existing_flags:
                logger.info(f"Contact {contact.id} already opted out")
                
                # Still send confirmation
                self._send_confirmation(contact.phone, self.OPT_OUT_CONFIRMATION)
                
                return Result.success({
                    'status': 'already_opted_out',
                    'contact_id': contact.id,
                    'flag_id': existing_flags[0].id
                })
            
            # Create opt-out flag
            flag = self.contact_flag_repository.create(
                contact_id=contact.id,
                flag_type='opted_out',
                flag_reason=f'Received opt-out message: {message[:100]}',
                applies_to='sms',
                created_by=source
            )
            
            # Extract keyword used
            keyword_used = self._extract_keyword(message, self.OPT_OUT_KEYWORDS)
            
            # Create audit log
            audit = self.opt_out_audit_repository.create(
                contact_id=contact.id,
                phone_number=contact.phone,
                contact_name=f"{contact.first_name} {contact.last_name}".strip() if hasattr(contact, 'first_name') else None,
                opt_out_method='sms_keyword',
                keyword_used=keyword_used,
                source=source,
                message_id=None  # Can be set if we have the message ID
            )
            
            # Send confirmation
            confirmation_sent = self._send_confirmation(contact.phone, self.OPT_OUT_CONFIRMATION)
            
            logger.info(f"Successfully processed opt-out for contact {contact.id}")
            
            return Result.success({
                'status': 'opted_out',
                'contact_id': contact.id,
                'flag_id': flag.id,
                'audit_id': audit.id,
                'confirmation_sent': confirmation_sent
            })
            
        except Exception as e:
            logger.error(f"Error processing opt-out: {e}", exc_info=True)
            return Result.failure(f"Failed to process opt-out: {str(e)}")
    
    def process_opt_in(self, contact: Any, message: str, source: str = 'sms_webhook') -> Result[Dict[str, Any]]:
        """
        Process an opt-in (resubscribe) request for a contact.
        
        Args:
            contact: Contact object
            message: The message that triggered opt-in
            source: Source of the opt-in request
            
        Returns:
            Result with processing status
        """
        try:
            # Check if currently opted out
            existing_flags = self.contact_flag_repository.find_active_flags(
                contact.id, flag_type='opted_out'
            )
            
            if not existing_flags:
                logger.info(f"Contact {contact.id} not currently opted out")
                
                # Still send confirmation
                self._send_confirmation(contact.phone, self.OPT_IN_CONFIRMATION)
                
                return Result.success({
                    'status': 'already_opted_in',
                    'contact_id': contact.id
                })
            
            # Expire the opt-out flag
            for flag in existing_flags:
                self.contact_flag_repository.expire_flag(flag.id)
            
            # Extract keyword used
            keyword_used = self._extract_keyword(message, self.OPT_IN_KEYWORDS)
            
            # Create audit log for opt-in
            audit = self.opt_out_audit_repository.create(
                contact_id=contact.id,
                phone_number=contact.phone,
                contact_name=f"{contact.first_name} {contact.last_name}".strip() if hasattr(contact, 'first_name') else None,
                opt_out_method='sms_opt_in',
                keyword_used=keyword_used,
                source=source
            )
            
            # Send confirmation
            confirmation_sent = self._send_confirmation(contact.phone, self.OPT_IN_CONFIRMATION)
            
            logger.info(f"Successfully processed opt-in for contact {contact.id}")
            
            return Result.success({
                'status': 'opted_in',
                'contact_id': contact.id,
                'expired_flags': len(existing_flags),
                'audit_id': audit.id,
                'confirmation_sent': confirmation_sent
            })
            
        except Exception as e:
            logger.error(f"Error processing opt-in: {e}", exc_info=True)
            return Result.failure(f"Failed to process opt-in: {str(e)}")
    
    def process_incoming_message(self, contact: Any, message_body: str, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Process an incoming message for opt-out/opt-in keywords.
        
        Args:
            contact: Contact object
            message_body: Message text
            webhook_data: Additional webhook data
            
        Returns:
            Result with action taken
        """
        try:
            # Check for opt-out first
            if self.contains_opt_out_keyword(message_body):
                result = self.process_opt_out(
                    contact=contact,
                    message=message_body,
                    source='sms_webhook'
                )
                if result.is_success:
                    result.data['action'] = 'opted_out'
                return result
            
            # Check for opt-in
            if self.contains_opt_in_keyword(message_body):
                result = self.process_opt_in(
                    contact=contact,
                    message=message_body,
                    source='sms_webhook'
                )
                if result.is_success:
                    result.data['action'] = 'opted_in'
                return result
            
            # No action needed
            return Result.success({
                'action': 'none',
                'contact_id': contact.id
            })
            
        except Exception as e:
            logger.error(f"Error processing incoming message: {e}", exc_info=True)
            return Result.failure(f"Failed to process message: {str(e)}")
    
    def get_opted_out_contact_ids(self) -> List[int]:
        """
        Get list of all opted-out contact IDs.
        
        Returns:
            List of contact IDs that are opted out
        """
        flags = self.contact_flag_repository.find_by_flag_type('opted_out', active_only=True)
        return [flag.contact_id for flag in flags]
    
    def filter_opted_out_contacts(self, contacts: List[Any]) -> List[Any]:
        """
        Filter a list of contacts to remove opted-out ones.
        
        Args:
            contacts: List of contact objects
            
        Returns:
            Filtered list without opted-out contacts
        """
        opted_out_ids = set(self.get_opted_out_contact_ids())
        return [c for c in contacts if c.id not in opted_out_ids]
    
    def is_contact_opted_out(self, contact: Any) -> bool:
        """
        Check if a specific contact is opted out.
        
        Args:
            contact: Contact object
            
        Returns:
            True if contact is opted out, False otherwise
        """
        flags = self.contact_flag_repository.find_active_flags(
            contact.id, flag_type='opted_out'
        )
        return len(flags) > 0
    
    def get_opt_out_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive opt-out statistics.
        
        Returns:
            Dictionary with opt-out statistics
        """
        # Get all audit logs
        all_audits = self.opt_out_audit_repository.find_all()
        
        # Get audits from last 30 days
        thirty_days_ago = utc_now() - timedelta(days=30)
        recent_count = self.opt_out_audit_repository.count_since(thirty_days_ago)
        
        # Get keyword breakdown
        keyword_counts = self.opt_out_audit_repository.count_by_keyword()
        
        # Find most common keyword
        most_common_keyword = None
        if keyword_counts:
            most_common_keyword = max(keyword_counts, key=keyword_counts.get)
        
        # Get current opted out count
        total_opted_out = self.contact_flag_repository.count_by_flag_type('opted_out')
        
        return {
            'total_opted_out': total_opted_out,
            'opt_outs_last_30_days': recent_count,
            'most_common_keyword': most_common_keyword,
            'keyword_breakdown': keyword_counts,
            'total_audit_logs': len(all_audits)
        }
    
    def get_recent_opt_outs(self, since: datetime) -> List[Dict[str, Any]]:
        """
        Get recent opt-out events.
        
        Args:
            since: Date to get opt-outs from
            
        Returns:
            List of opt-out event details
        """
        audits = self.opt_out_audit_repository.find_since(since)
        
        return [
            {
                'id': audit.id,
                'contact_id': audit.contact_id,
                'phone_number': audit.phone_number,
                'contact_name': audit.contact_name,
                'keyword_used': audit.keyword_used,
                'created_at': audit.created_at,
                'source': audit.source
            }
            for audit in audits
            if audit.opt_out_method == 'sms_keyword'  # Filter to actual opt-outs, not opt-ins
        ]
    
    def _send_confirmation(self, phone: str, message: str) -> bool:
        """
        Send confirmation message to contact.
        
        Args:
            phone: Phone number
            message: Confirmation message
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            result = self.sms_service.send_sms(
                to_phone=phone,
                message=message,
                is_system_message=True
            )
            return result.is_success if hasattr(result, 'is_success') else True
        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}")
            return False
    
    def _extract_keyword(self, message: str, keyword_list: List[str]) -> str:
        """
        Extract the actual keyword used from a message.
        
        Args:
            message: Message text
            keyword_list: List of possible keywords
            
        Returns:
            The keyword found or the first word of the message
        """
        if not message:
            return ''
        
        message_lower = message.lower().strip()
        
        # Check for exact matches
        for keyword in keyword_list:
            if message_lower == keyword or message_lower.startswith(keyword + ' '):
                return keyword.upper()
        
        # Return first word as keyword
        first_word = message_lower.split()[0] if message_lower.split() else message_lower
        return first_word.upper()