#!/usr/bin/env python3
"""
Targeted CSV Contact Enrichment
Only updates contacts that have phone numbers as names (from OpenPhone import)
"""


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import json
import re
from datetime import datetime
from pathlib import Path

def targeted_enrichment():
    """Update only contacts with phone numbers as names"""
    from app import create_app
    from crm_database import Contact
    from extensions import db
    
    app = create_app()
    
    with app.app_context():
        logger.info("🎯 Targeted CSV Contact Enrichment")
        logger.info("="*50)
        
        # Find the most recent enrichment file
        enrichment_dir = Path('./enrichment_data')
        json_files = list(enrichment_dir.glob('merged_contacts_*.json'))
        
        if not json_files:
            logger.info("❌ No enrichment data files found!")
            return False
        
        # Get the most recent file
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        logger.info(f"📂 Using: {latest_file.name}")
        
        # Load enrichment data
        with open(latest_file, 'r') as f:
            enrichment_data = json.load(f)
        
        logger.info(f"📊 Loaded {len(enrichment_data):,} enriched contacts")
        
        # Find contacts that need enrichment (have phone numbers as names)
        contacts_needing_enrichment = Contact.query.filter(
            Contact.first_name.like('%+1%')
        ).all()
        
        logger.info(f"🔍 Found {len(contacts_needing_enrichment):,} contacts needing enrichment")
        
        # Track statistics
        stats = {
            'contacts_processed': 0,
            'contacts_updated': 0,
            'first_name_updated': 0,
            'last_name_updated': 0,
            'email_updated': 0
        }
        
        # Process each contact that needs enrichment
        for contact in contacts_needing_enrichment:
            stats['contacts_processed'] += 1
            
            # Check if we have enrichment data for this phone number
            enrichment = enrichment_data.get(contact.phone)
            if enrichment:
                contact_updated = False
                
                # Update first_name if we have better data (truncate to 50 chars)
                enriched_first = enrichment.get('first_name', '').strip()[:50]
                if enriched_first and enriched_first != contact.first_name:
                    contact.first_name = enriched_first
                    stats['first_name_updated'] += 1
                    contact_updated = True
                
                # Update last_name if we have better data (truncate to 50 chars)
                enriched_last = enrichment.get('last_name', '').strip()[:50]
                if enriched_last and enriched_last != contact.last_name:
                    contact.last_name = enriched_last
                    stats['last_name_updated'] += 1
                    contact_updated = True
                
                # Update email if missing and we have one (but check for duplicates)
                enriched_email = enrichment.get('email', '').strip()
                if enriched_email and not contact.email:
                    # Check if this email already exists
                    existing_email = Contact.query.filter_by(email=enriched_email).first()
                    if not existing_email:
                        contact.email = enriched_email
                        stats['email_updated'] += 1
                        contact_updated = True
                
                if contact_updated:
                    stats['contacts_updated'] += 1
                    
                # Commit every 50 updates
                if stats['contacts_processed'] % 50 == 0:
                    try:
                        db.session.commit()
                        logger.info(f"   📦 Processed {stats['contacts_processed']:,} contacts...")
                    except Exception as e:
                        logger.info(f"   ⚠️  Error committing batch: {e}")
                        db.session.rollback()
        
        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            logger.info(f"⚠️  Final commit error: {e}")
            db.session.rollback()
        
        # Print results
        logger.info("\n" + "="*50)
        logger.info("✅ TARGETED ENRICHMENT COMPLETE")
        logger.info("="*50)
        
        logger.info(f"\n📊 Results:")
        logger.info(f"   Contacts processed: {stats['contacts_processed']:,}")
        logger.info(f"   Contacts updated: {stats['contacts_updated']:,}")
        logger.info(f"   First names updated: {stats['first_name_updated']:,}")
        logger.info(f"   Last names updated: {stats['last_name_updated']:,}")
        logger.info(f"   Emails added: {stats['email_updated']:,}")
        
        # Show sample of updated contacts
        logger.info(f"\n📋 Sample updated contacts:")
        updated_contacts = Contact.query.filter(
            ~Contact.first_name.like('%+1%')
        ).limit(5).all()
        
        for contact in updated_contacts:
            logger.info(f"   {contact.first_name} {contact.last_name} - {contact.phone}")
        
        total_contacts = Contact.query.count()
        enriched_count = Contact.query.filter(
            ~Contact.first_name.like('%+1%')
        ).count()
        
        logger.info(f"\n📊 Final Database State:")
        logger.info(f"   Total contacts: {total_contacts:,}")
        logger.info(f"   Contacts with real names: {enriched_count:,}")
        
        logger.info(f"\n🎯 Enrichment complete! Ready for text campaigns.")
        logger.info("="*50)
        
        return True

if __name__ == "__main__":
    targeted_enrichment()