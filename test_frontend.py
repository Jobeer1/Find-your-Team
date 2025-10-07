#!/usr/bin/env python3
"""
Simple test script to verify frontend functionality
"""

import requests
import time
import json

def test_routes():
    """Test that all routes are accessible"""
    base_url = "http://localhost:5001"
    
    routes_to_test = [
        "/",
        "/login", 
        "/signup",
        "/dashboard",
        "/lan-chat"
    ]
    
    print("Testing routes...")
    for route in routes_to_test:
        try:
            response = requests.get(f"{base_url}{route}", timeout=5)
            status = "✓" if response.status_code == 200 else "✗"
            print(f"{status} {route} - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"✗ {route} - Error: {e}")
    
def test_api_endpoints():
    """Test API endpoints"""
    base_url = "http://localhost:5001"
    
    # Test login
    print("\nTesting API endpoints...")
    try:
        login_data = {
            "email": "demo@findyourteam.com",
            "password": "demo123"
        }
        response = requests.post(f"{base_url}/api/login", json=login_data, timeout=5)
        status = "✓" if response.status_code == 200 else "✗"
        print(f"{status} /api/login - Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Login successful for: {data.get('user', {}).get('name', 'Unknown')}")
    except requests.exceptions.RequestException as e:
        print(f"✗ /api/login - Error: {e}")
    
    # Test chat endpoint
    try:
        chat_data = {
            "message": "Hello, I want to find my team!",
            "agent": "onboarding",
            "user_id": "test_user"
        }
        response = requests.post(f"{base_url}/api/chat", json=chat_data, timeout=10)
        status = "✓" if response.status_code in [200, 503] else "✗"  # 503 is expected in demo mode
        print(f"{status} /api/chat - Status: {response.status_code}")
        
        if response.status_code in [200, 503]:
            try:
                data = response.json()
                if 'message' in data:
                    print(f"  Chat response: {data['message'][:50]}...")
                elif 'demo_mode' in data:
                    print("  Demo mode detected - this is expected")
            except:
                pass
    except requests.exceptions.RequestException as e:
        print(f"✗ /api/chat - Error: {e}")

def main():
    print("Frontend Functionality Test")
    print("=" * 40)
    
    # Wait a moment for server to be ready
    print("Waiting for server to be ready...")
    time.sleep(2)
    
    test_routes()
    test_api_endpoints()
    
    print("\n" + "=" * 40)
    print("Test completed!")
    print("\nTo test manually:")
    print("1. Open http://localhost:5001 in your browser")
    print("2. Click 'Start Your Journey' button")
    print("3. Try logging in with demo@findyourteam.com / demo123")
    print("4. Test the chat interface in the dashboard")
    print("5. Try the LAN Chat feature")

if __name__ == "__main__":
    main()