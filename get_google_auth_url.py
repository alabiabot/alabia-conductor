#!/usr/bin/env python3
"""
Get Google OAuth URL
Generates the URL you need to visit to authenticate
"""
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = os.getenv('GOOGLE_CALENDAR_CREDENTIALS_JSON', './secrets/google-credentials.json')

def main():
    if not Path(CREDENTIALS_FILE).exists():
        print(f"ERROR: {CREDENTIALS_FILE} not found")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    
    # Get authorization URL
    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    print("\n" + "="*80)
    print("GOOGLE CALENDAR AUTHENTICATION")
    print("="*80)
    print("\n1. Copy this URL and open in your browser:")
    print(f"\n{auth_url}\n")
    print("2. Login with your Google account")
    print("3. Copy the authorization code")
    print("4. Run: python save_google_token.py <code>")
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
