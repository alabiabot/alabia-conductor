#!/usr/bin/env python3
"""
Save Google OAuth Token
Takes the authorization code and saves the token
"""
import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = os.getenv('GOOGLE_CALENDAR_CREDENTIALS_JSON', './secrets/google-credentials.json')
TOKEN_FILE = './secrets/token.json'

def main():
    if len(sys.argv) < 2:
        print("Usage: python save_google_token.py <authorization_code>")
        return

    auth_code = sys.argv[1]

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
    
    # Exchange code for token
    flow.fetch_token(code=auth_code)
    creds = flow.credentials
    
    # Save token
    Path(TOKEN_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())
    
    print(f"\nToken saved to: {TOKEN_FILE}")
    print("Authentication complete!\n")

if __name__ == "__main__":
    main()
