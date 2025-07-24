import csv
import argparse
import os

def reformat_contacts_for_openphone(input_file_path, output_file_path):
    """
    Reads a CSV export, reformats it for OpenPhone, and saves it to a new file.
    It creates separate rows for primary and secondary contacts if both have phone numbers.
    If phone numbers are identical, only the primary contact is created.

    Args:
        input_file_path (str): The path to the source CSV file.
        output_file_path (str): The path where the formatted CSV will be saved.
    """
    output_headers = ['First name', 'Last name', 'Address', 'Email', 'Phone number', 'Role']
    processed_contacts = []

    try:
        with open(input_file_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            for row in reader:
                # --- 1. Extract Shared and Individual Data ---
                mail_address = row.get('Mail Address', '').strip()
                mail_city = row.get('Mail City', '').strip()
                mail_state = row.get('Mail State', '').strip()
                mail_zip = row.get('Mail ZIP', '').strip()

                primary_name_raw = row.get('Primary Name', '').strip()
                primary_phone = row.get('Primary Mobile Phone1', '').strip()
                primary_email = row.get('Primary Email1', '').strip()

                secondary_name_raw = row.get('Secondary Name', '').strip()
                secondary_phone = row.get('Secondary Mobile Phone1', '').strip()
                secondary_email = row.get('Secondary Email1', '').strip()

                # --- 2. Handle Duplicate Phone Numbers ---
                # If both contacts have the same phone number, we only want the primary.
                # We achieve this by clearing the secondary phone number, which prevents
                # the secondary contact from being created in the step below.
                if primary_phone and primary_phone == secondary_phone:
                    secondary_phone = ''

                # --- 3. Create Shared Address ---
                full_address = f"{mail_address.title()}, {mail_city.title()}, {mail_state.upper()} {mail_zip}"

                # --- 4. Process Primary Contact ---
                if primary_name_raw and primary_phone:
                    formatted_name = primary_name_raw.title()
                    name_parts = formatted_name.split()
                    first_name, last_name = (" ".join(name_parts[:-1]), name_parts[-1]) if len(name_parts) > 1 else (name_parts[0], "")
                    
                    processed_contacts.append({
                        'First name': first_name,
                        'Last name': last_name,
                        'Address': full_address,
                        'Email': primary_email,
                        'Phone number': primary_phone,
                        'Role': 'homeowner'
                    })

                # --- 5. Process Secondary Contact ---
                if secondary_name_raw and secondary_phone:
                    formatted_name = secondary_name_raw.title()
                    name_parts = formatted_name.split()
                    first_name, last_name = (" ".join(name_parts[:-1]), name_parts[-1]) if len(name_parts) > 1 else (name_parts[0], "")
                    
                    processed_contacts.append({
                        'First name': first_name,
                        'Last name': last_name,
                        'Address': full_address,
                        'Email': secondary_email,
                        'Phone number': secondary_phone,
                        'Role': 'homeowner'
                    })

    except FileNotFoundError:
        print(f"Error: The file '{input_file_path}' was not found.")
        return
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return

    # --- 6. Write Output File ---
    if not processed_contacts:
        print("No contacts with phone numbers found to write.")
        return
        
    try:
        with open(output_file_path, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_headers)
            writer.writeheader()
            writer.writerows(processed_contacts)
        print(f"Successfully created '{output_file_path}' with {len(processed_contacts)} contacts.")
    except Exception as e:
        print(f"An error occurred while writing the file: {e}")


# --- How to use the script ---
# This script is run from the command line (terminal).
#
# Basic usage (input file is required):
# python your_script_name.py path/to/your/input.csv
#
# Specifying an output file (optional):
# python your_script_name.py path/to/your/input.csv -o path/to/your/output.csv

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Reformat a CSV of contacts for uploading to OpenPhone."
    )
    parser.add_argument(
        "input_file", 
        help="The path to the source CSV file."
    )
    parser.add_argument(
        "-o", "--output", 
        dest="output_file",
        default="openphone_contacts.csv",
        help="The path for the formatted output CSV file. Defaults to 'openphone_contacts.csv'."
    )
    args = parser.parse_args()
    reformat_contacts_for_openphone(args.input_file, args.output_file)
