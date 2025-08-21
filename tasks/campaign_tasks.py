"""
Celery tasks for campaign processing
Handles background sending and queue processing
"""

from datetime import datetime
from celery_worker import celery
from flask import current_app
from app import create_app
from logging_config import get_logger

logger = get_logger(__name__)


@celery.task(bind=True)
def process_campaign_queue(self):
    """Process pending campaign sends"""
    try:
        # Get Flask app instance for Celery context
        app = create_app()
        
        with app.app_context():
            # Use service registry to get properly configured CampaignService
            campaign_service = current_app.services.get('campaign')
            if not campaign_service:
                raise ValueError("CampaignService not found in service registry")
                
            stats = campaign_service.process_campaign_queue()
        
        # Log results
        logger.info("Campaign queue processed", stats=stats)
        
        return {
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'stats': stats
        }
        
    except Exception as e:
        logger.error("Campaign queue processing failed", error=str(e))
        
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
        # Get Flask app instance for Celery context
        app = create_app()
        
        with app.app_context():
            # Use service registry to get properly configured CampaignService
            campaign_service = current_app.services.get('campaign')
            if not campaign_service:
                raise ValueError("CampaignService not found in service registry")
                
            is_opt_out = campaign_service.handle_opt_out(phone, message)
        
        if is_opt_out:
            logger.info("Processed opt-out request", phone=phone, message=message)
        
        return {
            'success': True,
            'is_opt_out': is_opt_out,
            'phone': phone,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Error processing opt-out", phone=phone, error=str(e))
        return {
            'success': False,
            'error': str(e),
            'phone': phone,
            'timestamp': datetime.utcnow().isoformat()
        }