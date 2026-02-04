import os
import json
import logging
import msal
from msal import PublicClientApplication
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
TENANT_ID = os.getenv("AZURE_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# Scopes verified in AZURE_SETUP.md
SCOPES = [
    "User.Read",
    "User.ReadBasic.All",
    "Calendars.ReadWrite",
    "Calendars.Read.Shared", 
    "People.Read",
    "Place.Read.All"
]

CACHE_FILE = "token_cache.bin"

def create_app():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        cache.deserialize(open(CACHE_FILE, "r").read())
    
    return PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

def main():
    if not CLIENT_ID or not TENANT_ID:
         print("Error: Please set AZURE_CLIENT_ID and AZURE_TENANT_ID in .env file first.")
         return

    import msal
    app = create_app()
    
    accounts = app.get_accounts()
    result = None
    
    if accounts:
        print(f"Found stored account: {accounts[0]['username']}")
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    
    if not result:
        print("No suitable token found in cache. Starting Device Code Flow...")
        flow = app.initiate_device_flow(scopes=SCOPES)
        
        if "user_code" not in flow:
            print(f"Failed to create device flow. Error: {json.dumps(flow, indent=2)}")
            return

        print("\n" + "#" * 60)
        print(flow.get("message"))
        print("#" * 60 + "\n")
        
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        print("Authentication successful!")
        print(f"Account: {result.get('id_token_claims', {}).get('name')}")
        print(f"Username: {result.get('id_token_claims', {}).get('preferred_username')}")
        
        # Save cache
        if app.token_cache.has_state_changed:
            with open(CACHE_FILE, "w") as f:
                f.write(app.token_cache.serialize())
            print(f"Token cache saved to {CACHE_FILE}")
            
    else:
        print("Authentication failed.")
        print(result.get("error"))
        print(result.get("error_description"))

if __name__ == "__main__":
    main()
