
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import csv
from app import create_app
from extensions import db
from crm_database import ProductService

def run_seed():
    """
    Reads the QuickBooks products and services CSV and populates the
    product_service table in the database.
    """
    logger.info("--- Starting Product & Service Seeding ---")
    
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
                        logger.info(f"Skipping '{name}' due to invalid price: '{price_str}'")
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
                logger.info(f"--- Seeding Complete ---")
                logger.info(f"Added {products_added} new products/services to the database.")

        except FileNotFoundError:
            logger.info(f"ERROR: The file '{csv_filename}' was not found. Please make sure it's in the root directory.")
        except Exception as e:
            logger.info(f"An error occurred during seeding: {e}")
            db.session.rollback()

if __name__ == '__main__':
    run_seed()
