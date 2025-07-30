"""
CSV Import Service - Enhanced CSV import with tracking and list management
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from werkzeug.datastructures import FileStorage
from crm_database import db, Contact, CSVImport, CampaignList, CampaignListMember
from services.contact_service import ContactService


class CSVImportService:
    def __init__(self, contact_service: ContactService):
        self.contact_service = contact_service

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
            with open(temp_path, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                    results['total_rows'] += 1
                    
                    try:
                        # Check for required fields
                        if not row.get('phone'):
                            results['failed'] += 1
                            results['errors'].append(f"Row {row_num}: Missing phone number")
                            continue
                        
                        # Check if contact already exists
                        existing = Contact.query.filter_by(phone=row['phone']).first()
                        if existing:
                            results['duplicates'] += 1
                            contact = existing
                        else:
                            # Create new contact
                            contact = Contact(
                                first_name=row.get('first_name', ''),
                                last_name=row.get('last_name', ''),
                                email=row.get('email'),
                                phone=row['phone'],
                                csv_import_id=csv_import.id,
                                import_source=filename,
                                imported_at=datetime.utcnow(),
                                contact_metadata=self._extract_metadata(row)
                            )
                            db.session.add(contact)
                            db.session.flush()
                            results['contacts_created'].append(contact.id)
                        
                        # Add to campaign list if created
                        if campaign_list and not existing:
                            list_member = CampaignListMember(
                                list_id=campaign_list.id,
                                contact_id=contact.id,
                                added_by=imported_by
                            )
                            db.session.add(list_member)
                        
                        results['successful'] += 1
                        
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")
        
        except Exception as e:
            results['errors'].append(f"File processing error: {str(e)}")
        
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
            'duplicates': results['duplicates']
        }
        
        db.session.commit()
        
        results['import_id'] = csv_import.id
        results['list_id'] = campaign_list.id if campaign_list else None
        
        return results
    
    def _extract_metadata(self, row: Dict[str, str]) -> Dict[str, any]:
        """Extract additional metadata from CSV row"""
        # Remove standard fields and store the rest as metadata
        standard_fields = {'first_name', 'last_name', 'email', 'phone'}
        metadata = {k: v for k, v in row.items() if k not in standard_fields and v}
        return metadata if metadata else None
    
    def get_import_history(self, limit: int = 10) -> List[CSVImport]:
        """Get recent import history"""
        return CSVImport.query.order_by(CSVImport.imported_at.desc()).limit(limit).all()
    
    def get_contacts_by_import(self, import_id: int) -> List[Contact]:
        """Get all contacts from a specific import"""
        return Contact.query.filter_by(csv_import_id=import_id).all()