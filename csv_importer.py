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
            print(f"Successfully imported contacts from {filepath}")
        except FileNotFoundError:
            print(f"Error: The file {filepath} was not found.")
        except Exception as e:
            print(f"An error occurred during CSV import: {e}")
