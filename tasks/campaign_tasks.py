"""
Celery tasks for campaign processing
Handles background sending and queue processing
"""

from datetime import datetime
from celery_worker import celery
from services.campaign_service import CampaignService


@celery.task(bind=True)
def process_campaign_queue(self):
    """Process pending campaign sends"""
    try:
        campaign_service = CampaignService()
        stats = campaign_service.process_campaign_queue()
        
        # Log results
        print(f"Campaign queue processed: {stats}")
        
        return {
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'stats': stats
        }
        
    except Exception as e:
        print(f"Campaign queue processing failed: {str(e)}")
        
        # Retry up to 3 times with exponential backoff
        self.retry(countdown=60 * (2 ** self.request.retries), max_retries=3)
        
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task
def handle_incoming_message_opt_out(phone: str, message: str):
    """Handle potential opt-out from incoming message"""
    try:
        campaign_service = CampaignService()
        is_opt_out = campaign_service.handle_opt_out(phone, message)
        
        if is_opt_out:
            print(f"Processed opt-out request from {phone}: {message}")
        
        return {
            'success': True,
            'is_opt_out': is_opt_out,
            'phone': phone,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error processing opt-out for {phone}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'phone': phone,
            'timestamp': datetime.utcnow().isoformat()
        }