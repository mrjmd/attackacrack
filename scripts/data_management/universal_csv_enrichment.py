#!/usr/bin/env python3
"""
Universal CSV Contact Enrichment Script
Handles multiple CSV formats and enriches existing contacts in the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import csv
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class UniversalCSVEnricher:
    """Handles various CSV formats and enriches contacts in the database"""
    
    # Column mapping for different CSV formats
    COLUMN_MAPPINGS = {
        # Standard format (what our system expects)
        'standard': {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'phone': 'phone',
            'email': 'email',
            'company': 'company',
            'address': 'address'
        },
        # OpenPhone format
        'openphone': {
            'First name': 'first_name',
            'Last name': 'last_name',
            'Phone number': 'phone',
            'Email': 'email',
            'Address': 'address',
            'Role': 'role'
        },
        # Realtor.com format
        'realtor': {
            'First Name': 'first_name',
            'Last Name': 'last_name',
            'Phone': 'phone',
            'Company': 'company'
        },
        # Sotheby's format
        'sothebys': {
            'First Name': 'first_name',
            'Last Name': 'last_name',
            'Phone': 'phone',
            'Company': 'company'
        },
        # Vicente Realty format
        'vicente': {
            'First Name': 'first_name',
            'Last Name': 'last_name',
            'Email': 'email',
            'Phone': 'phone'
        },
        # Exit Realty formats
        'exit_cape': {
            'uk-text-muted': 'first_name',
            'lastname': 'last_name',
            'agent-card__tel': 'phone',
            'Exit Realty': 'company'
        },
        'exit_premier': {
            'mb-2': 'first_name',
            'lastname': 'last_name',
            'css-1dp0fhs-no-styles-2': 'phone',
            'company': 'company'
        },
        # Jack Conway format
        'jackconway': {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'phone_number_1': 'phone',
            'phone_number_2': 'phone2',
            'email': 'email',
            'location': 'location',
            'company': 'company'
        },
        # Lamacchia format
        'lamacchia': {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'phone': 'phone',
            'email': 'email',
            'company': 'company'
        },
        # Raveis format
        'raveis': {
            'First_name': 'first_name',
            'Last_name': 'last_name',
            'Cell': 'phone',
            'Title': 'title',
            'City': 'city',
            'Company': 'company'
        },
        # PropertyRadar format (cleaned_data_phone_split_names.csv)
        'propertyradar': {
            'Primary First Name': 'first_name',
            'Primary Last Name': 'last_name',
            'Primary Mobile Phone1': 'phone',
            'Primary Email1': 'email',
            'Secondary Name': 'secondary_name',
            'Secondary Mobile Phone1': 'secondary_phone',
            'Secondary Email1': 'secondary_email',
            'Address': 'property_address',
            'City': 'property_city',
            'ZIP': 'property_zip',
            'Mail Address': 'mail_address',
            'Mail City': 'mail_city',
            'Mail State': 'mail_state',
            'Mail ZIP': 'mail_zip',
            'Est Value': 'est_value',
            'Est Equity $': 'est_equity',
            'Owner Occ?': 'owner_occupied'
        }
    }
    
    def __init__(self):
        self.enrichment_data = defaultdict(dict)
        self.stats = {
            'files_processed': 0,
            'rows_processed': 0,
            'valid_contacts': 0,
            'duplicate_phones': 0,
            'invalid_phones': 0
        }
    
    def detect_format(self, headers: List[str], filename: str) -> Optional[str]:
        """Detect CSV format based on headers and filename"""
        
        # Check filename patterns first
        filename_lower = filename.lower()
        if 'openphone' in filename_lower:
            return 'openphone'
        elif 'realtor' in filename_lower:
            return 'realtor'
        elif 'sotheby' in filename_lower:
            return 'sothebys'
        elif 'vicente' in filename_lower:
            return 'vicente'
        elif 'exitcape' in filename_lower:
            return 'exit_cape'
        elif 'exitpremier' in filename_lower:
            return 'exit_premier'
        elif 'jackconway' in filename_lower:
            return 'jackconway'
        elif 'lamacchia' in filename_lower:
            return 'lamacchia'
        elif 'raveis' in filename_lower:
            return 'raveis'
        elif 'cleaned_data_phone' in filename_lower or 'propertyradar' in filename_lower:
            return 'propertyradar'
        
        # Check by header patterns
        headers_str = ','.join(headers)
        
        if 'First name' in headers and 'Phone number' in headers:
            return 'openphone'
        elif 'Primary First Name' in headers or 'Primary Mobile Phone1' in headers:
            return 'propertyradar'
        elif 'First_name' in headers:
            return 'raveis'
        elif 'uk-text-muted' in headers:
            return 'exit_cape'
        elif 'mb-2' in headers:
            return 'exit_premier'
        elif 'jsx-' in headers[0]:
            return 'realtor'
        elif all(h in headers for h in ['first_name', 'last_name']):
            if 'phone_number_1' in headers:
                return 'jackconway'
            else:
                return 'standard'
        elif 'First Name' in headers and 'Last Name' in headers:
            if 'Company' in headers:
                return 'sothebys'
            else:
                return 'vicente'
        
        return None
    
    def normalize_phone(self, phone: str) -> Optional[str]:
        """Normalize phone number to a consistent format"""
        if not phone:
            return None
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', str(phone))
        
        # Handle different lengths
        if len(digits) == 10:
            # Add US country code
            digits = '1' + digits
        elif len(digits) == 11 and digits[0] == '1':
            # Already has country code
            pass
        else:
            # Invalid length
            return None
        
        # Format as +1XXXXXXXXXX
        return f"+{digits}"
    
    def process_csv_file(self, filepath: str) -> int:
        """Process a single CSV file and extract enrichment data"""
        logger.info(f"Processing: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect delimiter
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(f, delimiter=delimiter)
                headers = reader.fieldnames
                
                # Detect format
                format_type = self.detect_format(headers, os.path.basename(filepath))
                
                if not format_type:
                    logger.warning(f"Could not detect format for {filepath}")
                    logger.warning(f"Headers: {headers}")
                    return 0
                
                logger.info(f"Detected format: {format_type}")
                mapping = self.COLUMN_MAPPINGS.get(format_type, {})
                
                rows_processed = 0
                for row in reader:
                    rows_processed += 1
                    
                    # Map columns
                    contact = {}
                    for csv_col, standard_col in mapping.items():
                        if csv_col in row:
                            value = row[csv_col]
                            if value and value.strip():
                                contact[standard_col] = value.strip()
                    
                    # Process primary contact
                    phone = contact.get('phone')
                    if phone:
                        normalized_phone = self.normalize_phone(phone)
                        if normalized_phone:
                            # Merge with existing data
                            if normalized_phone in self.enrichment_data:
                                self.stats['duplicate_phones'] += 1
                            
                            # Update enrichment data (newer data overwrites)
                            for key, value in contact.items():
                                if key != 'phone' and value:
                                    # Only update if we don't have this field or new value is longer/better
                                    existing = self.enrichment_data[normalized_phone].get(key)
                                    if not existing or len(str(value)) > len(str(existing)):
                                        self.enrichment_data[normalized_phone][key] = value
                            
                            self.stats['valid_contacts'] += 1
                        else:
                            self.stats['invalid_phones'] += 1
                    
                    # Process secondary contact for PropertyRadar format
                    if format_type == 'propertyradar':
                        secondary_phone = contact.get('secondary_phone')
                        if secondary_phone:
                            normalized_phone = self.normalize_phone(secondary_phone)
                            if normalized_phone:
                                # Parse secondary name
                                secondary_name = contact.get('secondary_name', '')
                                if secondary_name:
                                    name_parts = secondary_name.split()
                                    first_name = name_parts[0] if name_parts else ''
                                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                                    
                                    secondary_contact = {
                                        'first_name': first_name,
                                        'last_name': last_name,
                                        'email': contact.get('secondary_email', ''),
                                        'property_address': contact.get('property_address', ''),
                                        'property_city': contact.get('property_city', ''),
                                        'property_zip': contact.get('property_zip', '')
                                    }
                                    
                                    # Merge secondary contact
                                    for key, value in secondary_contact.items():
                                        if value:
                                            existing = self.enrichment_data[normalized_phone].get(key)
                                            if not existing:
                                                self.enrichment_data[normalized_phone][key] = value
                                    
                                    self.stats['valid_contacts'] += 1
                    
                    self.stats['rows_processed'] += 1
                
                self.stats['files_processed'] += 1
                logger.info(f"Processed {rows_processed} rows from {filepath}")
                return rows_processed
                
        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            return 0
    
    def process_all_csvs(self, directory: str):
        """Process all CSV files in a directory"""
        csv_files = list(Path(directory).glob('*.csv'))
        logger.info(f"Found {len(csv_files)} CSV files to process")
        
        for csv_file in csv_files:
            self.process_csv_file(str(csv_file))
        
        logger.info(f"\n=== Processing Summary ===")
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Total rows processed: {self.stats['rows_processed']}")
        logger.info(f"Valid contacts found: {self.stats['valid_contacts']}")
        logger.info(f"Duplicate phones merged: {self.stats['duplicate_phones']}")
        logger.info(f"Invalid phones skipped: {self.stats['invalid_phones']}")
        logger.info(f"Unique phone numbers: {len(self.enrichment_data)}")
    
    def save_enrichment_data(self, output_file: str):
        """Save enrichment data to JSON file"""
        # Convert defaultdict to regular dict for JSON serialization
        data_to_save = dict(self.enrichment_data)
        
        with open(output_file, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        
        logger.info(f"Saved enrichment data to {output_file}")
    
    def apply_enrichment_to_database(self, dry_run: bool = True):
        """Apply enrichment data to existing contacts in the database"""
        from app import create_app
        from crm_database import Contact
        from extensions import db
        
        app = create_app()
        
        with app.app_context():
            logger.info(f"\n=== Applying Enrichment to Database ===")
            logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
            
            stats = {
                'contacts_found': 0,
                'contacts_updated': 0,
                'first_names_updated': 0,
                'last_names_updated': 0,
                'emails_updated': 0,
                'metadata_updated': 0
            }
            
            # Process each phone number in enrichment data
            for phone, enrichment in self.enrichment_data.items():
                # Find contact by phone
                contact = Contact.query.filter_by(phone=phone).first()
                
                if contact:
                    stats['contacts_found'] += 1
                    updated = False
                    
                    # Update first name if missing or is phone number
                    if enrichment.get('first_name'):
                        if not contact.first_name or '+1' in contact.first_name:
                            if not dry_run:
                                contact.first_name = enrichment['first_name'][:50]
                            stats['first_names_updated'] += 1
                            updated = True
                    
                    # Update last name if missing
                    if enrichment.get('last_name'):
                        if not contact.last_name:
                            if not dry_run:
                                contact.last_name = enrichment['last_name'][:50]
                            stats['last_names_updated'] += 1
                            updated = True
                    
                    # Update email if missing
                    if enrichment.get('email'):
                        if not contact.email:
                            # Check for duplicate email
                            existing = Contact.query.filter_by(email=enrichment['email']).first()
                            if not existing:
                                if not dry_run:
                                    contact.email = enrichment['email']
                                stats['emails_updated'] += 1
                                updated = True
                    
                    # Add metadata
                    metadata_fields = ['company', 'title', 'location', 'city', 
                                     'property_address', 'property_city', 'property_zip',
                                     'mail_address', 'mail_city', 'mail_state', 'mail_zip',
                                     'est_value', 'est_equity', 'owner_occupied', 'role']
                    
                    metadata_to_add = {}
                    for field in metadata_fields:
                        if field in enrichment:
                            metadata_to_add[field] = enrichment[field]
                    
                    if metadata_to_add:
                        if not dry_run:
                            if contact.contact_metadata:
                                contact.contact_metadata.update(metadata_to_add)
                            else:
                                contact.contact_metadata = metadata_to_add
                        stats['metadata_updated'] += 1
                        updated = True
                    
                    if updated:
                        stats['contacts_updated'] += 1
                        
                        if not dry_run and stats['contacts_updated'] % 100 == 0:
                            db.session.commit()
                            logger.info(f"Committed {stats['contacts_updated']} updates...")
            
            if not dry_run:
                db.session.commit()
            
            logger.info(f"\n=== Enrichment Results ===")
            logger.info(f"Contacts found in database: {stats['contacts_found']}")
            logger.info(f"Contacts updated: {stats['contacts_updated']}")
            logger.info(f"First names updated: {stats['first_names_updated']}")
            logger.info(f"Last names updated: {stats['last_names_updated']}")
            logger.info(f"Emails added: {stats['emails_updated']}")
            logger.info(f"Metadata updated: {stats['metadata_updated']}")
            
            # Show sample of what would be updated
            if dry_run and stats['contacts_updated'] > 0:
                logger.info(f"\n=== Sample Updates (First 5) ===")
                count = 0
                for phone, enrichment in self.enrichment_data.items():
                    if count >= 5:
                        break
                    contact = Contact.query.filter_by(phone=phone).first()
                    if contact and (not contact.first_name or '+1' in contact.first_name):
                        logger.info(f"Phone: {phone}")
                        logger.info(f"  Current: {contact.first_name} {contact.last_name}")
                        logger.info(f"  Would update to: {enrichment.get('first_name', '')} {enrichment.get('last_name', '')}")
                        if enrichment.get('company'):
                            logger.info(f"  Company: {enrichment['company']}")
                        count += 1
            
            return stats


def main():
    """Main function to run the enrichment process"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Universal CSV Contact Enrichment')
    parser.add_argument('csv_directory', help='Directory containing CSV files')
    parser.add_argument('--output', default='enrichment_data.json', 
                       help='Output JSON file for enrichment data')
    parser.add_argument('--apply', action='store_true',
                       help='Apply enrichment to database')
    parser.add_argument('--live', action='store_true',
                       help='Run in live mode (actually update database)')
    
    args = parser.parse_args()
    
    # Create enricher instance
    enricher = UniversalCSVEnricher()
    
    # Process all CSV files
    enricher.process_all_csvs(args.csv_directory)
    
    # Save enrichment data
    enricher.save_enrichment_data(args.output)
    
    # Apply to database if requested
    if args.apply:
        dry_run = not args.live
        enricher.apply_enrichment_to_database(dry_run=dry_run)


if __name__ == '__main__':
    main()