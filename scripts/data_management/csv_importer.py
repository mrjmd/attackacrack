
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import csv
from services.contact_service import ContactService

class CsvImporter:
    def __init__(self, contact_service: ContactService):
        """
        Initializes the importer with a ContactService instance.
        """
        self.contact_service = contact_service

    def import_data(self, filepath):
        """
        Imports contact data from a CSV file.
        Assumes CSV has columns: 'first_name', 'last_name', 'email', 'phone'
        """
        try:
            with open(filepath, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Use the ContactService to add the contact
                    self.contact_service.add_contact(
                        first_name=row.get('first_name'),
                        last_name=row.get('last_name'),
                        email=row.get('email'),
                        phone=row.get('phone')
                    )
            logger.info(f"Successfully imported contacts from {filepath}")
        except FileNotFoundError:
            logger.info(f"Error: The file {filepath} was not found.")
        except Exception as e:
            logger.info(f"An error occurred during CSV import: {e}")
