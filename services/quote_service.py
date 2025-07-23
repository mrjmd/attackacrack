from extensions import db
from crm_database import Quote

class QuoteService:
    def __init__(self):
        self.session = db.session

    def add_quote(self, **kwargs):
        new_quote = Quote(**kwargs)
        self.session.add(new_quote)
        self.session.commit()
        return new_quote

    def get_all_quotes(self):
        return self.session.query(Quote).all()

    def get_quote_by_id(self, quote_id):
        return self.session.query(Quote).get(quote_id)
    
    def update_quote(self, quote, **kwargs):
        for key, value in kwargs.items():
            setattr(quote, key, value)
        self.session.commit()
        return quote

    def delete_quote(self, quote):
        self.session.delete(quote)
        self.session.commit()
