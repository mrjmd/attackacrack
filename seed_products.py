import csv
from app import create_app
from extensions import db
from crm_database import ProductService

def run_seed():
    """
    Reads the QuickBooks products and services CSV and populates the
    product_service table in the database.
    """
    print("--- Starting Product & Service Seeding ---")
    
    app = create_app()
    
    with app.app_context():
        # The name of the CSV file you uploaded
        csv_filename = 'ProductsServicesList_Attack_A_Crack_7_24_2025.csv'
        
        try:
            with open(csv_filename, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                products_added = 0
                for row in reader:
                    name = row.get('Product/Service Name')
                    price_str = row.get('Price')
                    description = row.get('Sales Description')

                    if not name or not price_str:
                        continue

                    try:
                        price = float(price_str)
                    except (ValueError, TypeError):
                        print(f"Skipping '{name}' due to invalid price: '{price_str}'")
                        continue

                    # Check if this product already exists
                    exists = db.session.query(ProductService).filter_by(name=name).first()
                    if not exists:
                        new_product = ProductService(
                            name=name,
                            description=description,
                            price=price
                        )
                        db.session.add(new_product)
                        products_added += 1
                
                db.session.commit()
                print(f"--- Seeding Complete ---")
                print(f"Added {products_added} new products/services to the database.")

        except FileNotFoundError:
            print(f"ERROR: The file '{csv_filename}' was not found. Please make sure it's in the root directory.")
        except Exception as e:
            print(f"An error occurred during seeding: {e}")
            db.session.rollback()

if __name__ == '__main__':
    run_seed()
