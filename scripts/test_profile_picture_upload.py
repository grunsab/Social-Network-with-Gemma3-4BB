#!/usr/bin/env python
"""
Integration test for profile picture upload functionality
"""

import os
import sys
import requests
import json
import time
from urllib.parse import urljoin

BASE_URL = "http://localhost:5000"

def login(username, password):
    """Log in to the application and return session cookies"""
    login_url = urljoin(BASE_URL, "/api/v1/auth/login")
    response = requests.post(
        login_url,
        json={"username": username, "password": password}
    )
    
    if response.status_code != 200:
        print(f"Login failed: {response.status_code}")
        print(response.text)
        return None
    
    return response.cookies

def get_profile(session_cookies):
    """Get user profile"""
    profile_url = urljoin(BASE_URL, "/api/v1/profiles/me")
    response = requests.get(profile_url, cookies=session_cookies)
    
    if response.status_code != 200:
        print(f"Failed to get profile: {response.status_code}")
        print(response.text)
        return None
    
    return response.json()

def upload_profile_picture(session_cookies, image_path):
    """Upload a profile picture"""
    if not os.path.exists(image_path):
        print(f"Image file not found: {image_path}")
        return False
    
    upload_url = urljoin(BASE_URL, "/api/v1/profiles/upload_picture")
    
    with open(image_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(upload_url, cookies=session_cookies, files=files)
    
    if response.status_code != 200:
        print(f"Failed to upload profile picture: {response.status_code}")
        print(response.text)
        return False
    
    data = response.json()
    print(f"Profile picture uploaded successfully: {data.get('profile_picture')}")
    return True

def verify_profile_picture_updated(session_cookies, previous_url):
    """Verify that the profile picture URL has changed"""
    profile = get_profile(session_cookies)
    if not profile:
        return False
    
    new_url = profile.get('user', {}).get('profile_picture')
    if not new_url:
        print("No profile picture URL found in profile")
        return False
    
    if new_url == previous_url:
        print("Profile picture URL not updated")
        return False
    
    print(f"Profile picture updated from {previous_url} to {new_url}")
    return True

def main():
    # Get credentials from arguments or prompt
    if len(sys.argv) < 3:
        username = input("Username: ")
        password = input("Password: ")
    else:
        username = sys.argv[1]
        password = sys.argv[2]
    
    # Get image path from arguments or use default
    if len(sys.argv) >= 4:
        image_path = sys.argv[3]
    else:
        # Use the cypress test image
        image_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "frontend", "cypress", "fixtures", "test-profile.jpg"
        )
        
        # If that doesn't exist, try the default-profile.png
        if not os.path.exists(image_path):
            image_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "frontend", "public", "default-profile.png"
            )
    
    # Login
    session_cookies = login(username, password)
    if not session_cookies:
        sys.exit(1)
    
    # Get initial profile to check current picture URL
    profile = get_profile(session_cookies)
    if not profile:
        sys.exit(1)
    
    previous_url = profile.get('user', {}).get('profile_picture', 'None')
    print(f"Current profile picture: {previous_url}")
    
    # Upload new profile picture
    if not upload_profile_picture(session_cookies, image_path):
        sys.exit(1)
    
    # Wait a moment for the server to process
    time.sleep(1)
    
    # Verify that the profile picture URL has changed
    if not verify_profile_picture_updated(session_cookies, previous_url):
        sys.exit(1)
    
    print("Profile picture upload test completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
