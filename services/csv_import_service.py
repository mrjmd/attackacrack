"""
CSV Import Service - Enhanced CSV import with smart column detection and list management
"""

import csv
import os
import re
from datetime import datetime
from utils.datetime_utils import utc_now
from typing import List, Dict, Optional, Tuple
from werkzeug.datastructures import FileStorage
# Model imports removed - using repositories only
from services.contact_service_refactored import ContactService
from repositories.csv_import_repository import CSVImportRepository
from repositories.contact_csv_import_repository import ContactCSVImportRepository
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository


class CSVImportService:
    """
    CSV Import Service using Repository Pattern
    
    Manages CSV file imports with proper separation of concerns:
    - Uses repositories for all database operations
    - Handles bulk operations efficiently
    - Manages transactions through repository pattern
    """
    
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
    
    def __init__(self, 
                 csv_import_repository: CSVImportRepository,
                 contact_csv_import_repository: ContactCSVImportRepository,
                 campaign_list_repository: CampaignListRepository,
                 campaign_list_member_repository: CampaignListMemberRepository,
                 contact_repository: ContactRepository,
                 contact_service: ContactService):
        """
        Initialize CSV Import Service with repository dependencies.
        
        Args:
            csv_import_repository: Repository for CSV import records
            contact_csv_import_repository: Repository for contact-import associations
            campaign_list_repository: Repository for campaign lists
            campaign_list_member_repository: Repository for campaign list members
            contact_repository: Repository for contacts
            contact_service: Contact service for business logic
        """
        self.csv_import_repository = csv_import_repository
        self.contact_csv_import_repository = contact_csv_import_repository
        self.campaign_list_repository = campaign_list_repository
        self.campaign_list_member_repository = campaign_list_member_repository
        self.contact_repository = contact_repository
        self.contact_service = contact_service
    
    def detect_format(self, headers: List[str], filename: str) -> Optional[str]:
        """Detect CSV format based on headers and filename"""
        
        # Check filename patterns first (if filename provided)
        if filename:
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
        
        # Validate meaningful digits in the original phone number part
        if len(digits) >= 10:
            # Check the main 10-digit phone number part (excluding country code)
            phone_part = digits[-10:] if len(digits) == 11 else digits
            if phone_part == '0' * 10:  # Reject all zeros
                return None
            if len(set(phone_part)) <= 1:  # Reject all same digit
                return None
        
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
        # Process the CSV
        results = {
            'total_rows': 0,
            'successful': 0,
            'failed': 0,
            'errors': [],
            'duplicates': 0,
            'contacts_created': []
        }
        
        csv_import = None
        campaign_list = None
        temp_path = None
        
        try:
            # Save the uploaded file temporarily
            filename = file.filename
            temp_path = f"/tmp/{filename}"
            file.save(temp_path)
            
            # Create import record using repository
            csv_import = self.csv_import_repository.create(
                filename=filename,
                imported_at=utc_now(),
                imported_by=imported_by,
                import_type='contacts',
                import_metadata={}
            )
            
            # Create campaign list if requested using repository
            if create_list:
                list_name = list_name or f"Import: {filename} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                campaign_list = self.campaign_list_repository.create(
                    name=list_name,
                    description=f"Contacts imported from {filename}",
                    created_by=imported_by,
                    filter_criteria={'csv_import_id': csv_import.id}
                )
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
                        
                        # Check if contact already exists using repository
                        existing = self.contact_repository.find_by_phone(normalized_phone)
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
                            # Create new contact using repository
                            contact = self.contact_repository.create(
                                first_name=mapped_row.get('first_name', ''),
                                last_name=mapped_row.get('last_name', ''),
                                email=mapped_row.get('email'),
                                phone=normalized_phone,
                                csv_import_id=csv_import.id,
                                import_source=filename,
                                imported_at=utc_now(),
                                contact_metadata=self._extract_metadata_from_mapped(mapped_row)
                            )
                            results['contacts_created'].append(contact.id)
                            is_new = True
                        
                        # Create association between contact and CSV import using repository
                        if not self.contact_csv_import_repository.exists_for_contact_and_import(
                            contact.id, csv_import.id
                        ):
                            self.contact_csv_import_repository.create(
                                contact_id=contact.id,
                                csv_import_id=csv_import.id,
                                is_new=is_new,
                                data_updated=data_updated if data_updated else None
                            )
                        
                        # Add to campaign list using repository
                        if campaign_list:
                            existing_member = self.campaign_list_member_repository.find_by_list_and_contact(
                                campaign_list.id, contact.id
                            )
                            
                            if not existing_member:
                                self.campaign_list_member_repository.create(
                                    list_id=campaign_list.id,
                                    contact_id=contact.id,
                                    added_by=imported_by
                                )
                            elif existing_member.status == 'removed':
                                # Reactivate if previously removed using repository
                                self.campaign_list_member_repository.update(
                                    existing_member,
                                    status='active',
                                    added_at=utc_now()
                                )
                        
                        results['successful'] += 1
                        
                        # Commit periodically through repositories
                        if results['successful'] % 100 == 0:
                            try:
                                # Repositories handle their own session management
                                # No direct session commits needed
                                pass
                            except Exception as commit_error:
                                results['errors'].append(f"Commit error at row {row_num}: {str(commit_error)}")
                        
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")
                        # Repository pattern handles rollback automatically
                        # No manual session management needed
        
        except Exception as e:
            results['errors'].append(f"File processing error: {str(e)}")
            # Repository pattern handles error recovery automatically
        
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        
        # Update import record using repository
        metadata = {
            'errors': results['errors'][:10],  # Store first 10 errors
            'duplicates': results['duplicates'],
            'new_contacts': len(results['contacts_created']),
            'enriched_contacts': results['duplicates']  # All duplicates were enriched
        }
        
        # Final update with error handling
        if csv_import:
            try:
                self.csv_import_repository.update_import_status(
                    csv_import.id,
                    results['total_rows'],
                    results['successful'],
                    results['failed'],
                    metadata
                )
            except Exception as final_error:
                results['errors'].append(f"Final update error: {str(final_error)}")
                # Repository pattern handles error recovery
        
        results['import_id'] = csv_import.id if csv_import else None
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
    
    def get_import_history(self, limit: int = 10) -> List[Dict]:
        """Get recent import history using repository"""
        return self.csv_import_repository.get_recent_imports(limit=limit)
    
    def get_contacts_by_import(self, import_id: int) -> List[Dict]:
        """Get all contacts from a specific import using repository"""
        contact_associations = self.contact_csv_import_repository.get_contacts_by_import_with_details(import_id)
        return [contact for contact, association in contact_associations]
    
    def import_csv(self, file: FileStorage, 
                   list_name: Optional[str] = None,
                   enrichment_mode: Optional[str] = None) -> Dict[str, any]:
        """
        Import contacts from CSV file (wrapper for import_contacts with route-expected response format)
        
        This method wraps import_contacts to provide a simplified response format
        expected by the route handlers. For PropertyRadar files, delegates to specialized service.
        
        Args:
            file: The uploaded CSV file
            list_name: Optional name for the campaign list
            enrichment_mode: Optional enrichment mode (not used in current implementation)
            
        Returns:
            Dict with:
                - success: boolean indicating if any imports were successful
                - imported: number of successful imports
                - updated: number of existing contacts updated (duplicates)
                - errors: list of error messages
                - message: summary message of the import
                - list_id: ID of created campaign list (if any)
        """
        try:
            # Check if this is a PropertyRadar CSV that needs special handling
            import csv
            import io
            
            # Read file content to detect format
            file.seek(0)
            file_content = file.read()
            
            # Try to decode the content
            try:
                if isinstance(file_content, bytes):
                    content_str = file_content.decode('utf-8', errors='ignore')
                else:
                    content_str = file_content
            except Exception:
                # Fall back to basic import if we can't read the file
                file.seek(0)
                return self._basic_import_csv(file, list_name)
            
            # Parse headers to detect format
            csv_reader = csv.reader(io.StringIO(content_str))
            headers = next(csv_reader, [])
            
            # Reset file pointer for actual import
            file.seek(0)
            
            # Check if this is a PropertyRadar CSV
            is_propertyradar = False
            if headers:
                # Check for PropertyRadar specific headers
                propertyradar_indicators = [
                    'Primary First Name', 'Primary Last Name', 'Primary Mobile Phone1',
                    'Secondary Name', 'Secondary Mobile Phone1',
                    'APN', 'Est Value', 'Est Equity', 'Owner Occ?'
                ]
                matches = sum(1 for indicator in propertyradar_indicators if indicator in headers)
                if matches >= 4:  # If we match at least 4 PropertyRadar fields
                    is_propertyradar = True
                
                # Also check filename
                filename = getattr(file, 'filename', '')
                if filename and ('propertyradar' in filename.lower() or 
                               'cleaned_data_phone' in filename.lower()):
                    is_propertyradar = True
            
            # Delegate to PropertyRadar service if detected
            if is_propertyradar:
                try:
                    # Import the PropertyRadar service (delayed import to avoid circular dependencies)
                    from services.propertyradar_import_service import PropertyRadarImportService
                    from repositories.property_repository import PropertyRepository
                    from flask import current_app
                    
                    # Get or create PropertyRadar service instance
                    if hasattr(current_app, 'services') and current_app.services:
                        # Try to get from service registry
                        propertyradar_service = current_app.services.get('propertyradar_import', None)
                        
                        if not propertyradar_service:
                            # Create new instance with dependencies
                            property_repo = PropertyRepository(current_app.db.session)
                            contact_repo = self.contact_repository
                            propertyradar_service = PropertyRadarImportService(
                                property_repository=property_repo,
                                contact_repository=contact_repo
                            )
                    else:
                        # Fallback: create with basic dependencies
                        from extensions import db
                        property_repo = PropertyRepository(db.session)
                        propertyradar_service = PropertyRadarImportService(
                            property_repository=property_repo,
                            contact_repository=self.contact_repository
                        )
                    
                    # Import using PropertyRadar service
                    result = propertyradar_service.import_propertyradar_csv(file, list_name)
                    
                    # Transform Result object to expected format
                    if hasattr(result, 'is_success') and result.is_success():
                        data = result.value
                        return {
                            'success': True,
                            'imported': data.get('contacts_created', 0),
                            'updated': data.get('contacts_updated', 0),
                            'errors': data.get('errors', []),
                            'message': data.get('message', 'PropertyRadar import completed'),
                            'list_id': data.get('list_id')
                        }
                    else:
                        error_msg = str(result.error) if hasattr(result, 'error') else 'PropertyRadar import failed'
                        return {
                            'success': False,
                            'imported': 0,
                            'updated': 0,
                            'errors': [error_msg],
                            'message': error_msg,
                            'list_id': None
                        }
                except Exception as pr_error:
                    # Log the error but fall back to basic import
                    import logging
                    logging.warning(f"PropertyRadar import failed, falling back to basic: {str(pr_error)}")
                    # Fall back to basic import
                    file.seek(0)
                    return self._basic_import_csv(file, list_name)
            
            # Not PropertyRadar, use basic import
            return self._basic_import_csv(file, list_name)
            
        except Exception as e:
            # Handle any exceptions
            return {
                'success': False,
                'imported': 0,
                'updated': 0,
                'errors': [f"Import error: {str(e)}"],
                'message': f"Import failed: {str(e)}",
                'list_id': None
            }
    
    def _basic_import_csv(self, file: FileStorage, list_name: Optional[str] = None) -> Dict[str, any]:
        """Basic CSV import for non-PropertyRadar files"""
        try:
            # Call the existing import_contacts method
            result = self.import_contacts(
                file=file,
                list_name=list_name,
                create_list=True,  # Always create list (default behavior)
                imported_by=None  # Will be set by route if needed
            )
            
            # Transform the response to match route expectations
            imported = result.get('successful', 0)
            updated = result.get('duplicates', 0)
            errors = result.get('errors', [])
            failed_count = result.get('failed', 0)
            success = imported > 0  # True if any successful imports
            
            # Build message
            if success:
                message = f"Import completed successfully: {imported} imported, {updated} updated"
                if failed_count > 0:
                    message += f", {failed_count} failed"
            else:
                message = f"Import failed: {failed_count} errors"
            
            return {
                'success': success,
                'imported': imported,
                'updated': updated,
                'errors': errors,
                'message': message,
                'list_id': result.get('list_id')
            }
        except Exception as e:
            # Handle any exceptions from import_contacts
            return {
                'success': False,
                'imported': 0,
                'updated': 0,
                'errors': [f"Import error: {str(e)}"],
                'message': f"Import failed: {str(e)}",
                'list_id': None
            }