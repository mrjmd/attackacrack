import hmac
import hashlib
import base64
from functools import wraps
from flask import Blueprint, jsonify, request, current_app, abort
from flask_login import login_required
from services.contact_service import ContactService
from services.message_service import MessageService
from services.ai_service import AIService
from crm_database import Activity # Import Activity

api_bp = Blueprint('api', __name__)

@api_bp.route('/debug-session')
def debug_session():
    """Debug endpoint to check session and request info"""
    from flask import session, request
    from flask_login import current_user
    
    return jsonify({
        'is_authenticated': current_user.is_authenticated,
        'user_id': current_user.id if current_user.is_authenticated else None,
        'session_data': dict(session),
        'scheme': request.scheme,
        'is_secure': request.is_secure,
        'host': request.host,
        'headers': dict(request.headers),
        'cookies_received': dict(request.cookies)
    })

@api_bp.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    health_status = {
        'status': 'healthy',
        'service': 'attackacrack-crm',
        'database': 'unknown',
        'redis': 'unknown'
    }
    
    try:
        # Check database connection
        from extensions import db
        db.session.execute('SELECT 1')
        health_status['database'] = 'connected'
    except Exception as e:
        health_status['database'] = f'error: {str(e)}'
        health_status['status'] = 'degraded'
    
    try:
        # Check Redis connection (optional)
        import os
        if os.environ.get('REDIS_URL'):
            from celery_worker import celery
            celery.backend.get('health_check_test')
            health_status['redis'] = 'connected'
        else:
            health_status['redis'] = 'not configured'
    except Exception as e:
        health_status['redis'] = f'error: {str(e)}'
        # Don't fail health check for Redis issues
    
    # Return 200 if database is connected (minimum requirement)
    if health_status['database'] == 'connected':
        return jsonify(health_status), 200
    else:
        return jsonify(health_status), 503

def verify_openphone_signature(f):
    """Decorator to verify webhook signature."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signing_key = current_app.config.get('OPENPHONE_WEBHOOK_SIGNING_KEY')
        if not signing_key:
            current_app.logger.error("Webhook signing key is not configured.")
            abort(500)

        # OpenPhone uses 'openphone-signature' header with format: hmac;version;timestamp;signature
        signature_header = request.headers.get('openphone-signature')
        if not signature_header:
            current_app.logger.error("No openphone-signature header found")
            abort(403)

        # Parse OpenPhone signature format: hmac;version;timestamp;signature
        try:
            parts = signature_header.split(';')
            if len(parts) != 4 or parts[0] != 'hmac':
                current_app.logger.error(f"Invalid signature format: {signature_header}")
                abort(403)
            
            version, timestamp, received_signature = parts[1], parts[2], parts[3]
            current_app.logger.info(f"OpenPhone signature - Version: {version}, Timestamp: {timestamp}")
        except Exception as e:
            current_app.logger.error(f"Error parsing signature: {e}")
            abort(403)

        # Implement OpenPhone signature verification per their documentation:
        # Compute the data covered by the signature as bytes: timestamp.raw_payload
        signed_data_bytes = b''.join([timestamp.encode(), b'.', request.data])
        
        # Convert the base64-encoded signing key to bytes
        try:
            signing_key_bytes = base64.b64decode(signing_key)
        except Exception as e:
            current_app.logger.error(f"Failed to decode signing key: {e}")
            abort(500)
        
        # Compute the SHA256 HMAC digest
        hmac_object = hmac.new(signing_key_bytes, signed_data_bytes, 'sha256')
        expected_signature_b64 = base64.b64encode(hmac_object.digest()).decode()
        
        current_app.logger.info(f"OpenPhone signature verification:")
        current_app.logger.info(f"  Timestamp: {timestamp}")
        current_app.logger.info(f"  Raw payload length: {len(request.data)} bytes")
        current_app.logger.info(f"  Signed data: {signed_data_bytes[:100]}...")
        current_app.logger.info(f"  Expected: {expected_signature_b64}")
        current_app.logger.info(f"  Received: {received_signature}")
        
        if not hmac.compare_digest(expected_signature_b64, received_signature):
            current_app.logger.error("OpenPhone signature verification failed")
            abort(403)
        else:
            current_app.logger.info("✅ OpenPhone signature verified successfully!")
        
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/contacts')
@login_required
def get_contacts():
    contact_service = ContactService()
    contacts = contact_service.get_all_contacts()
    contact_list = [{'id': c.id, 'first_name': c.first_name, 'last_name': c.last_name, 'email': c.email, 'phone': c.phone} for c in contacts]
    return jsonify(contact_list)

@api_bp.route('/messages/latest_conversations')
@login_required
def get_latest_conversations():
    message_service = MessageService()
    # Refresh session to get latest data from webhooks
    message_service.session.expire_all()
    latest_conversations = message_service.get_latest_conversations_from_db(limit=10)
    conversations_json = []
    for conv in latest_conversations:
        last_activity = conv.activities[-1] if conv.activities else None
        conversations_json.append({
            'contact_id': conv.contact.id,
            'contact_name': conv.contact.first_name,
            'contact_number': conv.contact.phone,
            'latest_message_body': last_activity.body if last_activity else "No recent activity"
        })
    return jsonify(conversations_json)

# --- THIS IS THE FIX ---
@api_bp.route('/contacts/<int:contact_id>/messages')
@login_required
def get_contact_messages(contact_id):
    """
    Provides a JSON list of all activities for a specific contact.
    """
    message_service = MessageService()
    # Use the new, correct service method
    activities = message_service.get_activities_for_contact(contact_id)
    # Format the data into the JSON structure the frontend expects
    messages_json = [
        {
            'body': act.body,
            'direction': act.direction,
            'timestamp': act.created_at.strftime('%b %d, %I:%M %p')
        }
        for act in activities
    ]
    return jsonify(messages_json)
# --- END FIX ---

@api_bp.route('/appointments/generate_summary/<int:contact_id>')
@login_required
def generate_appointment_summary(contact_id):
    message_service = MessageService()
    ai_service = AIService()
    
    activities = message_service.get_activities_for_contact(contact_id)
    summary = ai_service.summarize_conversation_for_appointment(activities)
    
    return jsonify({'summary': summary})

@api_bp.route('/webhooks/openphone', methods=['POST'])
@verify_openphone_signature
def openphone_webhook():
    from services.openphone_webhook_service import OpenPhoneWebhookService
    
    webhook_service = OpenPhoneWebhookService()
    data = request.json
    current_app.logger.info(f"Received valid webhook: {data}")
    
    try:
        result = webhook_service.process_webhook(data)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
