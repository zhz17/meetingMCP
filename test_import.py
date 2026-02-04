import sys
import os

# Mock environment variables to avoid errors during import if they are checked at module level
os.environ["AZURE_CLIENT_ID"] = "mock_client_id"
os.environ["AZURE_TENANT_ID"] = "mock_tenant_id"

try:
    print("Attempting to import server...")
    
    # Mock msal to avoid authority validation network calls
    from unittest.mock import MagicMock, patch
    with patch('msal.PublicClientApplication') as mock_app:
        import server
        
    print("Successfully imported server module.")
    # print("Tools registered:", [t.name for t in server.mcp._tools.values()]) # _tools is not available
    print(f"MCP Server Name: {server.mcp.name}")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)
