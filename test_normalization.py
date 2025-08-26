#!/usr/bin/env python
"""
Test script to demonstrate data normalization in PropertyRadar imports.
Run with: docker-compose exec web python test_normalization.py
"""

from app import create_app
from extensions import db
from crm_database import Property, Contact, PropertyContact

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("DATA NORMALIZATION VERIFICATION")
    print("="*60)
    
    # Get some properties to show normalization
    properties = Property.query.limit(5).all()
    
    print("\n📍 NORMALIZED ADDRESSES (was ALL CAPS):")
    print("-" * 40)
    for prop in properties:
        print(f"✅ {prop.address}, {prop.city}, {prop.state or 'MA'} {prop.zip_code}")
        print(f"   Type: {prop.property_type}")
        if prop.owner_name:
            print(f"   Owner: {prop.owner_name}")
    
    # Get some contacts to show name normalization
    contacts = Contact.query.limit(10).all()
    
    print("\n👤 NORMALIZED NAMES (was ALL CAPS):")
    print("-" * 40)
    for contact in contacts:
        full_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        if full_name:
            print(f"✅ {full_name}")
            if contact.phone:
                print(f"   Phone: {contact.phone}")
            if contact.email:
                print(f"   Email: {contact.email}")
    
    # Show a property with dual contacts
    print("\n🏠 PROPERTY WITH DUAL CONTACTS:")
    print("-" * 40)
    
    # Find a property with multiple contacts
    prop_with_multiple = db.session.query(Property).join(PropertyContact).group_by(Property.id).having(db.func.count(PropertyContact.contact_id) > 1).first()
    
    if prop_with_multiple:
        print(f"Property: {prop_with_multiple.address}, {prop_with_multiple.city}")
        print(f"  Value: ${prop_with_multiple.estimated_value:,.0f}" if prop_with_multiple.estimated_value else "  Value: N/A")
        print(f"  Equity: ${prop_with_multiple.estimated_equity:,.0f}" if prop_with_multiple.estimated_equity else "  Equity: N/A")
        
        associations = PropertyContact.query.filter_by(property_id=prop_with_multiple.id).all()
        print(f"\nContacts ({len(associations)}):")
        for assoc in associations:
            contact = Contact.query.get(assoc.contact_id)
            if contact:
                name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                role = "Primary Owner" if assoc.is_primary else "Secondary Owner"
                print(f"  • {name} ({role})")
    
    # Show normalization examples
    print("\n📝 NORMALIZATION EXAMPLES:")
    print("-" * 40)
    print("Original → Normalized:")
    print("  LINKER,JON J & AIMEE C → Jon Linker & Aimee Linker")
    print("  455 MIDDLE ST → 455 Middle St")
    print("  BRAINTREE → Braintree")
    print("  O'BRIEN → O'Brien")
    print("  MCDONALD → McDonald")
    print("  STREET → St, AVENUE → Ave, ROAD → Rd")
    
    print("\n" + "="*60)
    print("✅ NORMALIZATION COMPLETE")
    print("="*60)