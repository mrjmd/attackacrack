#!/usr/bin/env python3
"""
Targeted CSV Contact Enrichment
Only updates contacts that have phone numbers as names (from OpenPhone import)
"""

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
        print("🎯 Targeted CSV Contact Enrichment")
        print("="*50)
        
        # Find the most recent enrichment file
        enrichment_dir = Path('./enrichment_data')
        json_files = list(enrichment_dir.glob('merged_contacts_*.json'))
        
        if not json_files:
            print("❌ No enrichment data files found!")
            return False
        
        # Get the most recent file
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        print(f"📂 Using: {latest_file.name}")
        
        # Load enrichment data
        with open(latest_file, 'r') as f:
            enrichment_data = json.load(f)
        
        print(f"📊 Loaded {len(enrichment_data):,} enriched contacts")
        
        # Find contacts that need enrichment (have phone numbers as names)
        contacts_needing_enrichment = Contact.query.filter(
            Contact.first_name.like('%+1%')
        ).all()
        
        print(f"🔍 Found {len(contacts_needing_enrichment):,} contacts needing enrichment")
        
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
                        print(f"   📦 Processed {stats['contacts_processed']:,} contacts...")
                    except Exception as e:
                        print(f"   ⚠️  Error committing batch: {e}")
                        db.session.rollback()
        
        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            print(f"⚠️  Final commit error: {e}")
            db.session.rollback()
        
        # Print results
        print("\n" + "="*50)
        print("✅ TARGETED ENRICHMENT COMPLETE")
        print("="*50)
        
        print(f"\n📊 Results:")
        print(f"   Contacts processed: {stats['contacts_processed']:,}")
        print(f"   Contacts updated: {stats['contacts_updated']:,}")
        print(f"   First names updated: {stats['first_name_updated']:,}")
        print(f"   Last names updated: {stats['last_name_updated']:,}")
        print(f"   Emails added: {stats['email_updated']:,}")
        
        # Show sample of updated contacts
        print(f"\n📋 Sample updated contacts:")
        updated_contacts = Contact.query.filter(
            ~Contact.first_name.like('%+1%')
        ).limit(5).all()
        
        for contact in updated_contacts:
            print(f"   {contact.first_name} {contact.last_name} - {contact.phone}")
        
        total_contacts = Contact.query.count()
        enriched_count = Contact.query.filter(
            ~Contact.first_name.like('%+1%')
        ).count()
        
        print(f"\n📊 Final Database State:")
        print(f"   Total contacts: {total_contacts:,}")
        print(f"   Contacts with real names: {enriched_count:,}")
        
        print(f"\n🎯 Enrichment complete! Ready for text campaigns.")
        print("="*50)
        
        return True

if __name__ == "__main__":
    targeted_enrichment()