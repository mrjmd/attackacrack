import csv
from crm_manager import CrmManager

class CsvImporter:
    def __init__(self, crm_manager: CrmManager):
        """
        Initializes the importer with a CrmManager instance.
        """
        self.crm_manager = crm_manager

    def import_data(self, filepath):
        """
        Imports contact data from a CSV file.
        Assumes CSV has columns: 'first_name', 'last_name', 'email', 'phone'
        """
        try:
            with open(filepath, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Use the CrmManager to add the contact
                    self.crm_manager.add_contact(
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

