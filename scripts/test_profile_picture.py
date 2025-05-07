#!/usr/bin/env python
"""
This script tests the profile picture upload functionality.
It creates a direct API call to update the profile picture URL.
"""

import requests
import sys
import os
import argparse
from urllib.parse import urlparse

def get_session_cookie():
    """Prompt for session cookie"""
    cookie = input("Enter your session cookie value: ")
    return cookie.strip()

def update_profile_picture(session_cookie, profile_picture_url):
    """Update profile picture via API call"""
    cookies = {"session": session_cookie}
    
    # Validate URL format
    try:
        result = urlparse(profile_picture_url)
        if not all([result.scheme, result.netloc]):
            print(f"Error: '{profile_picture_url}' is not a valid URL")
            return False
    except Exception:
        print(f"Error: Could not parse '{profile_picture_url}' as a URL")
        return False

    # Send PATCH request to update profile
    try:
        response = requests.patch(
            "http://localhost:5000/api/v1/profiles/me", 
            json={"profile_picture": profile_picture_url},
            cookies=cookies
        )
        
        if response.status_code == 200:
            print(f"Successfully updated profile picture to: {profile_picture_url}")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"Error: API request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error making API request: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update profile picture URL")
    parser.add_argument("url", help="URL of the profile picture to set")
    
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    session_cookie = get_session_cookie()
    
    success = update_profile_picture(session_cookie, args.url)
    if success:
        print("Profile picture updated successfully!")
    else:
        sys.exit(1)
