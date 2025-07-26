from extensions import db
from crm_database import Quote, QuoteLineItem

class QuoteService:
    def __init__(self):
        # --- THIS IS THE FIX ---
        self.session = db.session
        # --- END FIX ---

    def get_all_quotes(self):
        return Quote.query.order_by(Quote.id.desc()).all()

    def get_quote_by_id(self, quote_id):
        return self.session.get(Quote, quote_id)

    # --- FIX START ---
    # The create_quote and update_quote methods have been completely rewritten
    # to correctly handle the line items sent from the form.
    def create_quote(self, data):
        try:
            new_quote = Quote(
                job_id=data['job_id'],
                status=data.get('status', 'Draft'),
                amount=0  # Start with 0, will calculate from line items
            )
            db.session.add(new_quote)
            
            total_amount = 0
            if 'line_items' in data:
                for item_data in data['line_items']:
                    quantity = float(item_data.get('quantity', 0))
                    price = float(item_data.get('price', 0))
                    total_amount += quantity * price
                    
                    line_item = QuoteLineItem(
                        quote=new_quote,
                        product_service_id=item_data.get('product_service_id') or None,
                        description=item_data['description'],
                        quantity=quantity,
                        price=price
                    )
                    db.session.add(line_item)
            
            new_quote.amount = total_amount
            db.session.commit()
            return new_quote
        except Exception as e:
            db.session.rollback()
            print(f"Error creating quote: {e}") # For debugging
            return None

    def update_quote(self, quote_id, data):
        try:
            quote = self.get_quote_by_id(quote_id)
            if not quote:
                return None

            quote.job_id = data.get('job_id', quote.job_id)
            quote.status = data.get('status', quote.status)

            total_amount = 0
            incoming_item_ids = {str(item['id']) for item in data.get('line_items', []) if item.get('id')}

            # Delete line items that are no longer present
            for existing_item in list(quote.line_items):
                if str(existing_item.id) not in incoming_item_ids:
                    db.session.delete(existing_item)

            # Update existing items and add new ones
            if 'line_items' in data:
                for item_data in data['line_items']:
                    quantity = float(item_data.get('quantity', 0))
                    price = float(item_data.get('price', 0))
                    total_amount += quantity * price
                    item_id = item_data.get('id')

                    if item_id: # Existing item
                        line_item = QuoteLineItem.query.get(item_id)
                        if line_item:
                            line_item.product_service_id = item_data.get('product_service_id') or None
                            line_item.description = item_data['description']
                            line_item.quantity = quantity
                            line_item.price = price
                    else: # New item
                        new_line_item = QuoteLineItem(
                            quote_id=quote.id,
                            product_service_id=item_data.get('product_service_id') or None,
                            description=item_data['description'],
                            quantity=quantity,
                            price=price
                        )
                        db.session.add(new_line_item)
            
            quote.amount = total_amount
            db.session.commit()
            return quote
        except Exception as e:
            db.session.rollback()
            print(f"Error updating quote: {e}") # For debugging
            return None
    # --- FIX END ---

    def delete_quote(self, quote_id):
        quote = self.get_quote_by_id(quote_id)
        if quote:
            # Manually delete line items to be safe
            for item in quote.line_items:
                db.session.delete(item)
            db.session.delete(quote)
            db.session.commit()
        return quote
