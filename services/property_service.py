from extensions import db
from crm_database import Property

class PropertyService:
    def __init__(self):
        self.session = db.session

    def add_property(self, **kwargs):
        new_property = Property(**kwargs)
        self.session.add(new_property)
        self.session.commit()
        return new_property

    def get_all_properties(self):
        return self.session.query(Property).all()

    def get_property_by_id(self, property_id):
        return self.session.query(Property).get(property_id)
    
    def update_property(self, property_obj, **kwargs):
        for key, value in kwargs.items():
            setattr(property_obj, key, value)
        self.session.commit()
        return property_obj

    def delete_property(self, property_obj):
        self.session.delete(property_obj)
        self.session.commit()
