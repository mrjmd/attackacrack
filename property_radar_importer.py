import csv
from crm_manager import CrmManager

class PropertyRadarImporter:
    def __init__(self, crm_manager: CrmManager):
        """
        Initializes the importer with a CrmManager instance.
        """
        self.crm_manager = crm_manager

    def import_data(self, filepath):
        """
        Imports data from a Property Radar CSV file.
        Creates a contact and a property, then links them.
        """
        try:
            with open(filepath, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # 1. Create the contact
                    new_contact = self.crm_manager.add_contact(
                        first_name=row.get('Owner First Name'),
                        last_name=row.get('Owner Last Name'),
                        email=row.get('Owner Email'),
                        phone=row.get('Owner Phone')
                    )
                    
                    # 2. Create the property and link it to the new contact
                    if new_contact:
                        self.crm_manager.add_property(
                            address=row.get('Address'),
                            contact_id=new_contact.id
                        )
            print(f"Successfully imported properties from {filepath}")
        except FileNotFoundError:
            print(f"Error: The file {filepath} was not found.")
        except Exception as e:
            print(f"An error occurred during Property Radar import: {e}")
