#!/usr/bin/env python
"""Test script to verify all service initializations for problem routes"""

import sys
from app import create_app

def test_service_initialization():
    """Test that all services can be initialized properly"""
    app = create_app()
    
    with app.app_context():
        print("Testing service registry initialization...")
        
        # Test all the problematic services
        services_to_test = [
            'conversation',
            'campaign_list', 
            'auth',
            'openphone_sync',
            'campaign',
            'quickbooks_sync',
            'property'
        ]
        
        results = {}
        
        for service_name in services_to_test:
            try:
                service = app.services.get(service_name)
                if service:
                    results[service_name] = "✓ SUCCESS"
                    print(f"✓ {service_name}: Initialized successfully")
                else:
                    results[service_name] = "✗ FAILED - Service not found"
                    print(f"✗ {service_name}: Service not found in registry")
            except Exception as e:
                results[service_name] = f"✗ FAILED - {str(e)}"
                print(f"✗ {service_name}: Error - {str(e)}")
        
        print("\n" + "="*50)
        print("SUMMARY:")
        print("="*50)
        
        for service_name, result in results.items():
            print(f"{service_name:20} {result}")
        
        # Check if all services passed
        all_passed = all("SUCCESS" in r for r in results.values())
        
        if all_passed:
            print("\n✓ All services initialized successfully!")
            return 0
        else:
            print("\n✗ Some services failed to initialize")
            return 1

if __name__ == "__main__":
    sys.exit(test_service_initialization())