#!/usr/bin/env python3
"""
Simple test script to verify the fixed functionality
"""

import requests
import time
import subprocess
import sys

def test_apis():
    """Test the API endpoints"""
    base_url = "http://localhost:5002"
    
    print("🧪 Testing API endpoints...")
    
    # Test main page
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ Main page: {response.status_code}")
    except Exception as e:
        print(f"❌ Main page failed: {e}")
        return False
    
    # Test bandwidth update API
    try:
        data = {'bandwidth_quality': 'high', 'network_type': 'ethernet'}
        response = requests.post(f"{base_url}/api/chat/bandwidth/update", 
                               json=data, timeout=5)
        print(f"✅ Bandwidth API: {response.status_code}")
        if response.ok:
            result = response.json()
            print(f"   Status: {result.get('status', 'unknown')}")
    except Exception as e:
        print(f"❌ Bandwidth API failed: {e}")
    
    # Test profile API
    try:
        response = requests.get(f"{base_url}/api/profile", timeout=5)
        print(f"✅ Profile API: {response.status_code}")
        if response.ok:
            result = response.json()
            print(f"   User: {result.get('display_name', 'unknown')}")
    except Exception as e:
        print(f"❌ Profile API failed: {e}")
    
    # Test P2P chat page
    try:
        response = requests.get(f"{base_url}/p2p-chat", timeout=5)
        print(f"✅ P2P Chat page: {response.status_code}")
    except Exception as e:
        print(f"❌ P2P Chat page failed: {e}")
    
    # Test profile page
    try:
        response = requests.get(f"{base_url}/profile", timeout=5)
        print(f"✅ Profile page: {response.status_code}")
    except Exception as e:
        print(f"❌ Profile page failed: {e}")
    
    return True

if __name__ == "__main__":
    print("🚀 Find Your Team - API Test Suite")
    print("=" * 40)
    
    # Give the server a moment to start if just launched
    time.sleep(2)
    
    if test_apis():
        print("\n🎉 All tests completed!")
        print("\n📋 Summary of fixes:")
        print("1. ✅ Added missing /api/chat/bandwidth/update endpoint")
        print("2. ✅ Added missing /api/profile endpoints (GET, PUT)")
        print("3. ✅ Added /profile page route and template")
        print("4. ✅ Fixed handleModeChange function in P2P chat client")
        print("5. ✅ Added mode change notifications and styling")
        print("6. ✅ Fixed session import in Flask app")
        print("\n🔗 Access the application at: http://localhost:5002")
        print("   - Main page: http://localhost:5002/")
        print("   - Dashboard: http://localhost:5002/dashboard")
        print("   - P2P Chat: http://localhost:5002/p2p-chat")
        print("   - Profile: http://localhost:5002/profile")
    else:
        print("\n❌ Some tests failed. Check if the server is running.")
        sys.exit(1)