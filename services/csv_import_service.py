"""
CSV Import Service - Enhanced CSV import with smart column detection and list management
"""

import csv
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from werkzeug.datastructures import FileStorage
from crm_database import db, Contact, CSVImport, CampaignList, CampaignListMember, ContactCSVImport
from services.contact_service import ContactService


class CSVImportService:
    # Column mapping for different CSV formats
    COLUMN_MAPPINGS = {
        # Standard format
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
        # PropertyRadar format
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
            'Mail ZIP': 'mail_zip'
        }
    }
    
    def __init__(self, contact_service: ContactService):
        self.contact_service = contact_service
    
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
        elif 'jsx-' in headers[0] if headers else False:
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
        elif 'phone' in headers or 'Phone' in headers:
            return 'standard'
        
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

    def import_contacts(self, file: FileStorage, 
                       list_name: Optional[str] = None,
                       create_list: bool = True,
                       imported_by: Optional[str] = None) -> Dict[str, any]:
        """
        Import contacts from CSV file with tracking and optional list creation
        
        Args:
            file: The uploaded CSV file
            list_name: Name for the campaign list (defaults to filename)
            create_list: Whether to create a campaign list for these contacts
            imported_by: User identifier who performed the import
            
        Returns:
            Dict with import results and statistics
        """
        # Save the uploaded file temporarily
        filename = file.filename
        temp_path = f"/tmp/{filename}"
        file.save(temp_path)
        
        # Create import record
        csv_import = CSVImport(
            filename=filename,
            imported_at=datetime.utcnow(),
            imported_by=imported_by,
            import_type='contacts',
            import_metadata={}
        )
        db.session.add(csv_import)
        db.session.flush()  # Get the ID
        
        # Create campaign list if requested
        campaign_list = None
        if create_list:
            list_name = list_name or f"Import: {filename} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            campaign_list = CampaignList(
                name=list_name,
                description=f"Contacts imported from {filename}",
                created_by=imported_by,
                filter_criteria={'csv_import_id': csv_import.id}
            )
            db.session.add(campaign_list)
            db.session.flush()
        
        # Process the CSV
        results = {
            'total_rows': 0,
            'successful': 0,
            'failed': 0,
            'errors': [],
            'duplicates': 0,
            'contacts_created': []
        }
        
        try:
            with open(temp_path, mode='r', encoding='utf-8', errors='ignore') as csvfile:
                # Try to detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                try:
                    delimiter = sniffer.sniff(sample).delimiter
                except:
                    delimiter = ','  # Default to comma
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                headers = reader.fieldnames
                
                # Detect format
                format_type = self.detect_format(headers, filename)
                
                # If no format detected, try standard column names
                if not format_type:
                    # Check for any phone-like column
                    phone_columns = [h for h in headers if 'phone' in h.lower() or 'cell' in h.lower() or 'mobile' in h.lower()]
                    if phone_columns:
                        format_type = 'standard'
                    else:
                        results['errors'].append(f"Could not detect CSV format. Headers: {headers[:10]}")
                        return results
                
                # Get column mapping for detected format
                mapping = self.COLUMN_MAPPINGS.get(format_type, self.COLUMN_MAPPINGS['standard'])
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                    results['total_rows'] += 1
                    
                    try:
                        # Map columns using detected format
                        mapped_row = {}
                        for csv_col, standard_col in mapping.items():
                            if csv_col in row:
                                value = row[csv_col]
                                if value and value.strip():
                                    mapped_row[standard_col] = value.strip()
                        
                        # Check for required phone field
                        phone = mapped_row.get('phone')
                        if not phone:
                            results['failed'] += 1
                            results['errors'].append(f"Row {row_num}: Missing phone number")
                            continue
                        
                        # Normalize phone number
                        normalized_phone = self.normalize_phone(phone)
                        if not normalized_phone:
                            results['failed'] += 1
                            results['errors'].append(f"Row {row_num}: Invalid phone number format: {phone}")
                            continue
                        
                        # Check if contact already exists
                        existing = Contact.query.filter_by(phone=normalized_phone).first()
                        data_updated = {}
                        
                        if existing:
                            results['duplicates'] += 1
                            contact = existing
                            
                            # Enrich existing contact data
                            if mapped_row.get('first_name'):
                                # Update if missing or is a phone number
                                if not existing.first_name or '+1' in existing.first_name:
                                    existing.first_name = mapped_row['first_name'][:50]
                                    data_updated['first_name'] = mapped_row['first_name']
                            
                            if mapped_row.get('last_name') and not existing.last_name:
                                existing.last_name = mapped_row['last_name'][:50]
                                data_updated['last_name'] = mapped_row['last_name']
                            
                            if mapped_row.get('email') and not existing.email:
                                existing.email = mapped_row['email']
                                data_updated['email'] = mapped_row['email']
                            
                            # Merge metadata - extract extra fields
                            new_metadata = self._extract_metadata_from_mapped(mapped_row)
                            if new_metadata:
                                if existing.contact_metadata:
                                    existing.contact_metadata.update(new_metadata)
                                else:
                                    existing.contact_metadata = new_metadata
                                data_updated['metadata'] = new_metadata
                            
                            is_new = False
                        else:
                            # Create new contact
                            contact = Contact(
                                first_name=mapped_row.get('first_name', ''),
                                last_name=mapped_row.get('last_name', ''),
                                email=mapped_row.get('email'),
                                phone=normalized_phone,
                                csv_import_id=csv_import.id,
                                import_source=filename,
                                imported_at=datetime.utcnow(),
                                contact_metadata=self._extract_metadata_from_mapped(mapped_row)
                            )
                            db.session.add(contact)
                            db.session.flush()
                            results['contacts_created'].append(contact.id)
                            is_new = True
                        
                        # Create association between contact and CSV import (check if already exists)
                        existing_import_record = ContactCSVImport.query.filter_by(
                            contact_id=contact.id,
                            csv_import_id=csv_import.id
                        ).first()
                        
                        if not existing_import_record:
                            contact_csv_import = ContactCSVImport(
                                contact_id=contact.id,
                                csv_import_id=csv_import.id,
                                is_new=is_new,
                                data_updated=data_updated if data_updated else None
                            )
                            db.session.add(contact_csv_import)
                        
                        # Add to campaign list (for both new and existing contacts)
                        if campaign_list:
                            # Check if already in list
                            existing_member = CampaignListMember.query.filter_by(
                                list_id=campaign_list.id,
                                contact_id=contact.id
                            ).first()
                            
                            if not existing_member:
                                list_member = CampaignListMember(
                                    list_id=campaign_list.id,
                                    contact_id=contact.id,
                                    added_by=imported_by
                                )
                                db.session.add(list_member)
                            elif existing_member.status == 'removed':
                                # Reactivate if previously removed
                                existing_member.status = 'active'
                                existing_member.added_at = datetime.utcnow()
                        
                        results['successful'] += 1
                        
                        # Commit periodically to avoid large transactions
                        if results['successful'] % 100 == 0:
                            try:
                                db.session.commit()
                            except Exception as commit_error:
                                db.session.rollback()
                                results['errors'].append(f"Commit error at row {row_num}: {str(commit_error)}")
                        
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")
                        # Rollback on error to prevent pending rollback state
                        db.session.rollback()
                        # Re-add the csv_import object since rollback cleared it
                        db.session.add(csv_import)
                        if campaign_list:
                            db.session.add(campaign_list)
        
        except Exception as e:
            results['errors'].append(f"File processing error: {str(e)}")
            # Ensure we rollback on any processing error
            db.session.rollback()
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        # Update import record
        csv_import.total_rows = results['total_rows']
        csv_import.successful_imports = results['successful']
        csv_import.failed_imports = results['failed']
        csv_import.import_metadata = {
            'errors': results['errors'][:10],  # Store first 10 errors
            'duplicates': results['duplicates'],
            'new_contacts': len(results['contacts_created']),
            'enriched_contacts': results['duplicates']  # All duplicates were enriched
        }
        
        # Final commit with error handling
        try:
            db.session.commit()
        except Exception as final_error:
            db.session.rollback()
            results['errors'].append(f"Final commit error: {str(final_error)}")
            # Try to at least save the import record
            try:
                db.session.add(csv_import)
                csv_import.import_metadata['commit_error'] = str(final_error)
                db.session.commit()
            except:
                pass
        
        results['import_id'] = csv_import.id
        results['list_id'] = campaign_list.id if campaign_list else None
        
        return results
    
    def _extract_metadata(self, row: Dict[str, str]) -> Dict[str, any]:
        """Extract additional metadata from original CSV row"""
        # Remove standard fields and store the rest as metadata
        standard_fields = {'first_name', 'last_name', 'email', 'phone', 
                          'First name', 'Last name', 'Email', 'Phone number', 'Phone'}
        metadata = {k: v for k, v in row.items() if k not in standard_fields and v}
        return metadata if metadata else None
    
    def _extract_metadata_from_mapped(self, mapped_row: Dict[str, str]) -> Dict[str, any]:
        """Extract additional metadata from mapped row"""
        # Store non-standard fields as metadata
        standard_fields = {'first_name', 'last_name', 'email', 'phone'}
        metadata_fields = ['company', 'title', 'location', 'city', 'role',
                          'property_address', 'property_city', 'property_zip',
                          'mail_address', 'mail_city', 'mail_state', 'mail_zip',
                          'address', 'secondary_name', 'secondary_phone', 'secondary_email']
        
        metadata = {}
        for field in metadata_fields:
            if field in mapped_row and mapped_row[field]:
                metadata[field] = mapped_row[field]
        
        return metadata if metadata else None
    
    def get_import_history(self, limit: int = 10) -> List[CSVImport]:
        """Get recent import history"""
        return CSVImport.query.order_by(CSVImport.imported_at.desc()).limit(limit).all()
    
    def get_contacts_by_import(self, import_id: int) -> List[Contact]:
        """Get all contacts from a specific import"""
        csv_import = CSVImport.query.get(import_id)
        if csv_import:
            return csv_import.contacts
        return []