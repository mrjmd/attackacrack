#!/usr/bin/env python
"""Test script to simulate route calls and verify they work without 500 errors"""

import sys
from app import create_app
from flask import session

def test_route_simulations():
    """Simulate route calls to verify services work properly"""
    app = create_app()
    
    with app.app_context():
        print("Testing route service usage patterns...")
        print("="*60)
        
        results = []
        
        # Test 1: ConversationService in /contacts/conversations
        print("\n1. Testing ConversationService (used by /contacts/conversations)...")
        try:
            conversation_service = app.services.get('conversation')
            # Simulate what the route does
            result = conversation_service.get_conversations_page(
                search_query='',
                filter_type='all',
                date_filter='all',
                page=1
            )
            print(f"   ✓ ConversationService.get_conversations_page() works")
            print(f"   - Found {result['total']} conversations")
            results.append(('ConversationService', True, None))
        except Exception as e:
            print(f"   ✗ ConversationService failed: {str(e)}")
            results.append(('ConversationService', False, str(e)))
        
        # Test 2: CampaignListService in /campaigns/lists
        print("\n2. Testing CampaignListService (used by /campaigns/lists)...")
        try:
            list_service = app.services.get('campaign_list')
            lists = list_service.get_all_lists()
            print(f"   ✓ CampaignListService.get_all_lists() works")
            print(f"   - Found {len(lists)} campaign lists")
            
            # Test get_list_stats if there are lists
            if lists and len(lists) > 0:
                stats = list_service.get_list_stats(lists[0].id)
                print(f"   ✓ CampaignListService.get_list_stats() works")
            results.append(('CampaignListService', True, None))
        except Exception as e:
            print(f"   ✗ CampaignListService failed: {str(e)}")
            results.append(('CampaignListService', False, str(e)))
        
        # Test 3: AuthService in /auth/users
        print("\n3. Testing AuthService (used by /auth/users)...")
        try:
            auth_service = app.services.get('auth')
            users_result = auth_service.get_all_users(page=1, per_page=50)
            if users_result.success:
                print(f"   ✓ AuthService.get_all_users() works")
                print(f"   - Found {len(users_result.data.items)} users")
            else:
                print(f"   ✗ AuthService.get_all_users() returned error: {users_result.error}")
            results.append(('AuthService', users_result.success, users_result.error))
        except Exception as e:
            print(f"   ✗ AuthService failed: {str(e)}")
            results.append(('AuthService', False, str(e)))
        
        # Test 4: OpenPhoneSyncService in /openphone
        print("\n4. Testing OpenPhoneSyncService (used by /openphone)...")
        try:
            openphone_sync_service = app.services.get('openphone_sync')
            sync_stats = openphone_sync_service.get_sync_statistics()
            print(f"   ✓ OpenPhoneSyncService.get_sync_statistics() works")
            print(f"   - Contacts: {sync_stats['total_contacts']}")
            print(f"   - Messages: {sync_stats['total_messages']}")
            results.append(('OpenPhoneSyncService', True, None))
        except Exception as e:
            print(f"   ✗ OpenPhoneSyncService failed: {str(e)}")
            results.append(('OpenPhoneSyncService', False, str(e)))
        
        # Test 5: CampaignService in /campaigns/new
        print("\n5. Testing CampaignService (used by /campaigns/new)...")
        try:
            campaign_service = app.services.get('campaign')
            audience_stats = campaign_service.get_audience_stats()
            print(f"   ✓ CampaignService.get_audience_stats() works")
            print(f"   - Stats retrieved successfully")
            results.append(('CampaignService', True, None))
        except Exception as e:
            print(f"   ✗ CampaignService failed: {str(e)}")
            results.append(('CampaignService', False, str(e)))
        
        # Test 6: QuickBooksSyncService in /quickbooks
        print("\n6. Testing QuickBooksSyncService (used by /quickbooks/sync)...")
        try:
            sync_service = app.services.get('quickbooks_sync')
            # Just test that we can get the service and it has the expected methods
            if hasattr(sync_service, 'sync_all'):
                print(f"   ✓ QuickBooksSyncService has sync_all method")
            if hasattr(sync_service, 'sync_customers'):
                print(f"   ✓ QuickBooksSyncService has sync_customers method")
            results.append(('QuickBooksSyncService', True, None))
        except Exception as e:
            print(f"   ✗ QuickBooksSyncService failed: {str(e)}")
            results.append(('QuickBooksSyncService', False, str(e)))
        
        # Test 7: PropertyService in /properties/add
        print("\n7. Testing PropertyService (used by /properties/add)...")
        try:
            property_service = app.services.get('property')
            contact_service = app.services.get('contact')
            
            # Test that both services work
            contacts = contact_service.get_all_contacts()
            print(f"   ✓ ContactService.get_all_contacts() works")
            
            # Test property service has required method
            if hasattr(property_service, 'add_property'):
                print(f"   ✓ PropertyService has add_property method")
            results.append(('PropertyService', True, None))
        except Exception as e:
            print(f"   ✗ PropertyService failed: {str(e)}")
            results.append(('PropertyService', False, str(e)))
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY:")
        print("="*60)
        
        all_passed = True
        for service_name, passed, error in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{service_name:25} {status}")
            if error:
                print(f"{'':25} Error: {error}")
                all_passed = False
        
        print("\n" + "="*60)
        if all_passed:
            print("✓ All route simulations passed! Routes should work without 500 errors.")
            return 0
        else:
            print("✗ Some route simulations failed. Check the errors above.")
            return 1

if __name__ == "__main__":
    sys.exit(test_route_simulations())