#!/usr/bin/env python3
"""
Google Calendar Authentication Helper
Run this script ONCE to authenticate and generate token.json
"""
import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Paths
CREDENTIALS_FILE = os.getenv('GOOGLE_CALENDAR_CREDENTIALS_JSON', './secrets/google-credentials.json')
TOKEN_FILE = './secrets/token.json'


def main():
    """Authenticate and save token"""

    print("\n" + "="*80)
    print("GOOGLE CALENDAR AUTHENTICATION")
    print("="*80 + "\n")

    # Check credentials file exists
    if not Path(CREDENTIALS_FILE).exists():
        print(f"ERROR: Credentials file not found: {CREDENTIALS_FILE}")
        print("\nPlease:")
        print("1. Create OAuth 2.0 credentials in Google Cloud Console")
        print("2. Download credentials.json")
        print("3. Save to: ./secrets/google-credentials.json")
        print("\nSee: docs/google-calendar-setup.md for detailed instructions")
        return

    print(f"Found credentials file: {CREDENTIALS_FILE}\n")

    creds = None
    token_path = Path(TOKEN_FILE)

    # Check if token already exists
    if token_path.exists():
        print(f"Token file already exists: {TOKEN_FILE}")
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if creds and creds.valid:
            print("Token is still valid!")
            print("\nAuthentication complete. You're ready to use Calendar API.\n")
            return

        print("Token expired or invalid. Re-authenticating...\n")

    # Authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("Starting OAuth flow...\n")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)

            # Use console flow (better for WSL)
            print("="*80)
            print("MANUAL AUTHENTICATION REQUIRED")
            print("="*80)
            print("\nPlease follow these steps:")
            print("1. Copy the URL that will be shown below")
            print("2. Open it in your browser (Windows)")
            print("3. Login with your Google account")
            print("4. Copy the authorization code")
            print("5. Paste it back here\n")

            try:
                # Try run_console first (best for WSL)
                creds = flow.run_console()
            except Exception as e:
                print(f"\nConsole flow failed: {e}")
                print("Trying local server flow...\n")
                # Fallback to local server (won't open browser)
                creds = flow.run_local_server(port=0, open_browser=False)

        # Save token
        print(f"\nAuthentication successful!")
        print(f"Saving token to: {TOKEN_FILE}")

        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

        print("Token saved!\n")

    print("="*80)
    print("AUTHENTICATION COMPLETE")
    print("="*80)
    print("\nYou can now:")
    print("- Run the Calendar MCP server")
    print("- Use calendar tools via the agent")
    print("- Test with: python test_calendar_integration.py\n")


if __name__ == "__main__":
    main()
