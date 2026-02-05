import os
import json
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Any
from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize North MCP Server
server = NorthMCPServer(
    name="outlook-calendar-mcp",
    port=3001,
    server_secret="some server secret" # Ideally get from env var
)

class GraphClient:
    """
    Client for interacting with Microsoft Graph API.
    Handles token retrieval from various sources suitable for RBC internal environment.
    """
    def __init__(self):
        self.base_url = "https://graph.microsoft.com/v1.0"
        
    def _get_token(self) -> str:
        """
        Retrieve a valid access token for Microsoft Graph.
        Strategy:
        1. Check specific environment variable (Dev/Manual override)
        2. Check for On-Behalf-Of token from authenticated user context (Future/Integration)
        3. Check for Managed Identity (Azure internal)
        4. Client Credentials (Service Account)
        """
        
        # --- STRATEGY 1: Environment Variable (Testing/Dev) ---
        # Simplest for local dev: hardcode a token or set in .env
        token = os.getenv("AZURE_ACCESS_TOKEN")
        if token:
            return token

        # --- STRATEGY 2: User Context / On-Behalf-Of (OBO) ---
        # Logic: If the North SDK passes the user's OBO token in the user object
        # try:
        #     user = get_authenticated_user()
        #     # distinct_id or metadata might hold the upstream token
        #     if hasattr(user, "graph_token") and user.graph_token:
        #         return user.graph_token
        # except Exception:
        #     pass

        # --- STRATEGY 3: Managed Identity (Azure Production) ---
        # Logic: If running on an Azure VM/Container with identity enabled
        # try:
        #     # Use azure-identity library (needs to be installed)
        #     # from azure.identity import DefaultAzureCredential
        #     # credential = DefaultAzureCredential()
        #     # token_obj = credential.get_token("https://graph.microsoft.com/.default")
        #     # return token_obj.token
        #     pass
        # except ImportError:
        #     logger.warning("azure-identity not installed")
        # except Exception as e:
        #     logger.error(f"Managed Identity token failed: {e}")

        # --- STRATEGY 4: Client Credentials (Service Account) ---
        # Logic: Use App ID + Secret to act AS THE APP (not as user)
        # Note: This limits access to what the App permissions allow, not the user's data
        # unless "Application Permissions" are granted.
        # try:
        #      import msal
        #      app = msal.ConfidentialClientApplication(
        #          client_id=os.getenv("AZURE_CLIENT_ID"),
        #          client_credential=os.getenv("AZURE_CLIENT_SECRET"),
        #          authority=f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}"
        #      )
        #      result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        #      if "access_token" in result:
        #          return result['access_token']
        # except Exception:
        #      pass

        
        raise Exception("No valid Graph API token found. Please set AZURE_ACCESS_TOKEN or configure OBO/Managed Identity.")

    async def call_api(self, method: str, endpoint: str, data: dict = None, params: dict = None):
        """Generic Graph API caller"""
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                if method == "POST":
                    resp = await client.post(url, headers=headers, json=data, params=params)
                elif method == "GET":
                    resp = await client.get(url, headers=headers, params=params)
                
                resp.raise_for_status()
                return resp.json() if resp.status_code != 204 else {"status": "success"}
            except httpx.HTTPStatusError as e:
                logger.error(f"Graph API Error: {e.response.text}")
                raise Exception(f"Graph API Error ({e.response.status_code}): {e.response.text}")

# Initialize Graph Client
graph_client = GraphClient()

# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@server.tool()
async def search_users(query: str) -> List[dict]:
    """
    Search for users in the organization by name or email keyword.
    Use this to verify a user's exact email address before booking.
    
    Args:
        query: Name or part of an email to search for (e.g., "John", "service")
    """
    try:
        current_user = get_authenticated_user() # Audit who is calling
        logger.info(f"User {current_user.email} calling search_users with query: {query}")

        endpoint = "/users"
        params = {
            "$select": "displayName,userPrincipalName,mail",
            "$filter": f"startsWith(displayName,'{query}') or startsWith(userPrincipalName,'{query}') or startsWith(mail,'{query}')",
            "$top": 10
        }
        
        data = await graph_client.call_api("GET", endpoint, params=params)
        users = data.get("value", [])
        
        results = []
        for u in users:
            name = u.get("displayName")
            email = u.get("mail") or u.get("userPrincipalName")
            results.append({"name": name, "email": email})
            
        return results
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        return [{"error": str(e)}]

@server.tool()
async def find_common_availability(attendee_emails: List[str], date_str: str, duration_minutes: int = 30) -> List[str]:
    """
    Find common available time slots for the user and a list of attendees on a specific date.
    
    Args:
        attendee_emails: List of email addresses
        date_str: Date in 'YYYY-MM-DD' format
        duration_minutes: Duration in minutes (default 30)
    """
    try:
        current_user = get_authenticated_user()
        
        start_time = f"{date_str}T08:00:00"
        end_time = f"{date_str}T18:00:00" # Standard work hours assumption
        
        # Add current user to potential check if implicit
        # (API 'me/findMeetingTimes' usually considers 'me' automatically)
        
        attendees = [{"emailAddress": {"address": email}, "type": "required"} for email in attendee_emails]
        
        payload = {
            "attendees": attendees,
            "timeConstraint": {
                "activityDomain": "work",
                "timeslots": [{
                    "start": {"dateTime": start_time, "timeZone": "Pacific Standard Time"},
                    "end": {"dateTime": end_time, "timeZone": "Pacific Standard Time"}
                }]
            },
            "meetingDuration": f"PT{duration_minutes}M",
            "returnSuggestionReasons": True,
            "minimumAttendeePercentage": 100
        }
        
        data = await graph_client.call_api("POST", "/me/findMeetingTimes", data=payload)
        suggestions = data.get("meetingTimeSuggestions", [])
        
        available_slots = []
        for slot in suggestions:
            start = slot["meetingTimeSlot"]["start"]["dateTime"]
            end = slot["meetingTimeSlot"]["end"]["dateTime"]
            available_slots.append(f"{start} to {end}")
            
        return available_slots
    except Exception as e:
        return [f"Error: {str(e)}"]

@server.tool()
async def find_available_rooms(date_str: str, start_time_str: str, end_time_str: str) -> List[dict]:
    """
    Find available meeting rooms for a specific time slot.
    
    Args:
        date_str: 'YYYY-MM-DD'
        start_time_str: 'HH:MM:SS' (e.g. '14:00:00')
        end_time_str: 'HH:MM:SS' (e.g. '15:00:00')
    """
    try:
        # 1. List rooms
        rooms_data = await graph_client.call_api("GET", "/places/microsoft.graph.room")
        rooms = rooms_data.get("value", [])
        if not rooms:
            return [{"error": "No meeting rooms found in directory"}]
            
        room_emails = [r.get("emailAddress") for r in rooms if r.get("emailAddress")]
        
        # 2. Check availability
        start_dt = f"{date_str}T{start_time_str}"
        end_dt = f"{date_str}T{end_time_str}"
        
        payload = {
            "schedules": room_emails,
            "startTime": {"dateTime": start_dt, "timeZone": "Pacific Standard Time"},
            "endTime": {"dateTime": end_dt, "timeZone": "Pacific Standard Time"},
            "availabilityViewInterval": 60
        }
        
        schedule_data = await graph_client.call_api("POST", "/me/calendar/getSchedule", data=payload)
        
        available_rooms = []
        for item in schedule_data.get("value", []):
            email = item["scheduleId"]
            is_free = True
            for event in item.get("scheduleItems", []):
                if event["status"] != "free":
                    is_free = False
                    break
            
            if is_free:
                room_name = next((r["displayName"] for r in rooms if r.get("emailAddress") == email), email)
                available_rooms.append({"name": room_name, "email": email})
                
        return available_rooms
    except Exception as e:
        return [{"error": f"Error finding rooms: {str(e)}"}]

@server.tool()
async def book_meeting(
    subject: str,
    start_iso: str,
    end_iso: str,
    attendee_emails: List[str],
    room_email: Optional[str] = None,
    is_online: bool = False,
    content: str = "Please join us for a meeting."
) -> str:
    """
    Book a meeting in Outlook.
    
    Args:
        subject: Meeting Title
        start_iso: Start time ISO format (YYYY-MM-DDTHH:MM:SS)
        end_iso: End time ISO format
        attendee_emails: List of emails
        room_email: (Optional) Email of the meeting room
        is_online: (Optional) Create Teams meeting
        content: Body of the invite
    """
    try:
        attendees = [{"emailAddress": {"address": email}, "type": "required"} for email in attendee_emails]
        
        if room_email:
            attendees.append({"emailAddress": {"address": room_email}, "type": "resource"})
            
        location_display = "Online (Teams)" if is_online else "TBD"
        if room_email:
            location_display = room_email 

        payload = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": content
            },
            "start": {
                "dateTime": start_iso,
                "timeZone": "Pacific Standard Time"
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": "Pacific Standard Time"
            },
            "location": {
                "displayName": location_display
            },
            "attendees": attendees,
            "isOnlineMeeting": is_online,
            "onlineMeetingProvider": "teamsForBusiness" if is_online else None
        }
        
        result = await graph_client.call_api("POST", "/me/events", data=payload)
        weblink = result.get('webLink', 'No link returned')
        return f"Meeting booked successfully! WebLink: {weblink}"
        
    except Exception as e:
        return f"Failed to book meeting: {str(e)}"
