
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import csv
from services.contact_service import ContactService
from services.property_service import PropertyService

class PropertyRadarImporter:
    def __init__(self, contact_service: ContactService, property_service: PropertyService):
        """
        Initializes the importer with ContactService and PropertyService instances.
        """
        self.contact_service = contact_service
        self.property_service = property_service

    def import_data(self, filepath):
        """
        Imports data from a Property Radar CSV file.
        Creates a contact and a property, then links them.
        """
        try:
            with open(filepath, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # 1. Create the contact using the ContactService
                    new_contact = self.contact_service.add_contact(
                        first_name=row.get('Owner First Name'),
                        last_name=row.get('Owner Last Name'),
                        email=row.get('Owner Email'),
                        phone=row.get('Owner Phone')
                    )
                    
                    # 2. Create the property and link it to the new contact using the PropertyService
                    if new_contact:
                        self.property_service.add_property(
                            address=row.get('Address'),
                            contact_id=new_contact.id
                        )
            logger.info(f"Successfully imported properties from {filepath}")
        except FileNotFoundError:
            logger.info(f"Error: The file {filepath} was not found.")
        except Exception as e:
            logger.info(f"An error occurred during Property Radar import: {e}")
