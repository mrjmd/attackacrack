from extensions import db
from crm_database import Quote, QuoteLineItem, ProductService

class QuoteService:
    def __init__(self):
        self.session = db.session

    def get_all_products_and_services(self):
        return self.session.query(ProductService).order_by(ProductService.name).all()

    def add_quote_with_line_items(self, job_id, line_items_data):
        """
        Creates a new quote and its associated line items.
        line_items_data is a list of dicts, e.g., 
        [{'product_id': 1, 'quantity': 2, 'price': 105.00, 'description': 'Custom desc'}, ...]
        """
        total_amount = sum(item['quantity'] * item['price'] for item in line_items_data)

        new_quote = Quote(
            job_id=job_id,
            amount=total_amount,
            status='Draft'
        )
        self.session.add(new_quote)
        self.session.flush() # Get the ID for the new quote

        for item_data in line_items_data:
            line_item = QuoteLineItem(
                quote_id=new_quote.id,
                product_service_id=item_data['product_id'],
                description=item_data['description'], # Save the custom description
                quantity=item_data['quantity'],
                price=item_data['price']
            )
            self.session.add(line_item)
        
        self.session.commit()
        return new_quote

    def get_all_quotes(self):
        return self.session.query(Quote).all()

    def get_quote_by_id(self, quote_id):
        return self.session.query(Quote).get(quote_id)
    
    def delete_quote(self, quote):
        self.session.delete(quote)
        self.session.commit()
