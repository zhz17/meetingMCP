import os
import json
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
import msal
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Configuration
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
TENANT_ID = os.getenv("AZURE_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = [
    "User.Read",
    "User.ReadBasic.All",
    "Calendars.ReadWrite",
    "Calendars.Read.Shared",
    "People.Read",
    "Place.Read.All"
]
CACHE_FILE = os.path.join(os.path.dirname(__file__), "token_cache.bin")

# Initialize MCP
mcp = FastMCP("Outlook-Pro-Assistant")

class OutlookManager:
    def __init__(self):
        self.cache = msal.SerializableTokenCache()
        if os.path.exists(CACHE_FILE):
             self.cache.deserialize(open(CACHE_FILE, "r").read())
        
        self.app = msal.PublicClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            token_cache=self.cache
        )

    def _get_token(self):
        """Get token from cache (refreshed automatically)"""
        accounts = self.app.get_accounts()
        if not accounts:
            raise Exception("No accounts found. Please run 'python auth_setup.py' first.")
        
        result = self.app.acquire_token_silent(SCOPES, account=accounts[0])
        
        if self.cache.has_state_changed:
            with open(CACHE_FILE, "w") as f:
                f.write(self.cache.serialize())

        if result and "access_token" in result:
            return result["access_token"]
        
        raise Exception("Failed to acquire token silently. Please re-run 'python auth_setup.py'.")

    async def call_graph(self, method: str, endpoint: str, data: dict = None, params: dict = None):
        """Generic Graph API caller"""
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"https://graph.microsoft.com/v1.0{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                if method == "POST":
                    resp = await client.post(url, headers=headers, json=data, params=params)
                elif method == "GET":
                    resp = await client.get(url, headers=headers, params=params)
                
                resp.raise_for_status()
                return resp.json() if resp.status_code != 204 else {"status": "success"}
            except httpx.HTTPStatusError as e:
                # Catch detailed graph errors
                print(f"Graph API Error: {e.response.text}")
                raise e

# Initialize Manager
outlook = OutlookManager()

@mcp.tool()
async def search_users(query: str):
    """
    Search for users in the organization by name or email keyword, also used for meeting room finding.
    Use this to verify a user's exact email address before booking or checking availability.
    
    Args:
        query: Name or part of an email to search for (e.g., "John", "service")
    """
    try:
        # Use $search for better keyword matching if supported, but $filter startsWith is safer for Basic Read
        # We'll use filter on displayName and userPrincipalName
        endpoint = "/users"
        params = {
            "$select": "displayName,userPrincipalName,mail",
            "$filter": f"startsWith(displayName,'{query}') or startsWith(userPrincipalName,'{query}') or startsWith(mail,'{query}')",
            "$top": 10
        }
        
        data = await outlook.call_graph("GET", endpoint, params=params)
        users = data.get("value", [])
        
        if not users:
            return f"No users found matching '{query}'."
            
        results = []
        for u in users:
            name = u.get("displayName")
            email = u.get("mail") or u.get("userPrincipalName")
            results.append({"name": name, "email": email})
            
        return results
    except Exception as e:
        return f"Error searching users: {str(e)}"

@mcp.tool()
async def find_common_availability(attendee_emails: List[str], date_str: str, duration_minutes: int = 30):
    """
    Find common available time slots for the user and a list of attendees on a specific date.
    
    Args:
        attendee_emails: List of email addresses (e.g., ["aaa@example.com", "bbb@example.com"])
        date_str: Date in 'YYYY-MM-DD' format
        duration_minutes: Duration of the meeting in minutes (default 30)
    """
    start_time = f"{date_str}T08:00:00"
    end_time = f"{date_str}T18:00:00" # Work hours assumption
    
    # 1. Resolve attendees
    attendees = [{"emailAddress": {"address": email}, "type": "required"} for email in attendee_emails]
    
    # 2. Construct payload for findMeetingTimes
    payload = {
        "attendees": attendees,
        "timeConstraint": {
            "activityDomain": "work",
            "timeslots": [{
                "start": {"dateTime": start_time, "timeZone": "Pacific Standard Time"}, # Adjust TimeZone as needed or make configurable
                "end": {"dateTime": end_time, "timeZone": "Pacific Standard Time"}
            }]
        },
        "meetingDuration": f"PT{duration_minutes}M",
        "returnSuggestionReasons": True,
        "minimumAttendeePercentage": 100
    }
    
    try:
        data = await outlook.call_graph("POST", "/me/findMeetingTimes", payload)
        suggestions = data.get("meetingTimeSuggestions", [])
        
        # Format for easier reading
        available_slots = []
        for slot in suggestions:
            start = slot["meetingTimeSlot"]["start"]["dateTime"]
            end = slot["meetingTimeSlot"]["end"]["dateTime"]
            available_slots.append(f"{start} to {end}")
            
        return available_slots
    except Exception as e:
        return f"Error finding availability: {str(e)}"

@mcp.tool()
async def find_available_rooms(date_str: str, start_time_str: str, end_time_str: str):
    """
    Find available meeting rooms for a specific time slot.
    
    Args:
        date_str: 'YYYY-MM-DD'
        start_time_str: 'HH:MM:SS' (e.g. '14:00:00')
        end_time_str: 'HH:MM:SS' (e.g. '15:00:00')
    """
    # 1. List all rooms (limit to 20 for performance)
    try:
        rooms_data = await outlook.call_graph("GET", "/places/microsoft.graph.room")
        rooms = rooms_data.get("value", [])
        if not rooms:
            return "No meeting rooms found in the directory."
            
        room_emails = [r.get("emailAddress") for r in rooms if r.get("emailAddress")]
        
        # 2. Check availability (getSchedule)
        start_dt = f"{date_str}T{start_time_str}"
        end_dt = f"{date_str}T{end_time_str}"
        
        payload = {
            "schedules": room_emails,
            "startTime": {"dateTime": start_dt, "timeZone": "Pacific Standard Time"},
            "endTime": {"dateTime": end_dt, "timeZone": "Pacific Standard Time"},
            "availabilityViewInterval": 60 # Check the whole block
        }
        
        schedule_data = await outlook.call_graph("POST", "/me/calendar/getSchedule", payload)
        
        available_rooms = []
        for item in schedule_data.get("value", []):
            email = item["scheduleId"]
            # key: 0=free, 1=tentative, 2=busy, 3=ood, 4=workingElsewhere
            # We look for simple '0' (Free) in the schedule items or just check if there are NO busy blocks in the requested window
            # The API returns 'scheduleItems'. If empty or status is free, it's good.
            is_free = True
            for event in item.get("scheduleItems", []):
                if event["status"] != "free":
                    is_free = False
                    break
            
            if is_free:
                # Find the room name
                room_name = next((r["displayName"] for r in rooms if r.get("emailAddress") == email), email)
                available_rooms.append({"name": room_name, "email": email})
                
        return available_rooms
    except Exception as e:
        return f"Error finding rooms: {str(e)}"

@mcp.tool()
async def book_meeting(
    subject: str,
    start_iso: str,
    end_iso: str,
    attendee_emails: List[str],
    room_email: Optional[str] = None,
    is_online: bool = False,
    content: str = "Please join us for a meeting."
):
    """
    Book a meeting in Outlook.
    
    Args:
        subject: Meeting Title
        start_iso: Start time ISO format (YYYY-MM-DDTHH:MM:SS)
        end_iso: End time ISO format
        attendee_emails: List of emails of people to invite
        room_email: (Optional) Email of the meeting room to book
        is_online: (Optional) If True, creates a Teams meeting
        content: Body of the meeting invite
    """
    
    attendees = [{"emailAddress": {"address": email}, "type": "required"} for email in attendee_emails]
    
    if room_email:
        attendees.append({"emailAddress": {"address": room_email}, "type": "resource"})
        
    location_display = "Online (Teams)" if is_online else "TBD"
    if room_email:
        # Ideally lookup name, but email is functional for booking
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
    
    try:
        result = await outlook.call_graph("POST", "/me/events", payload)
        return f"Meeting booked successfully! WebLink: {result.get('webLink')}"
    except Exception as e:
        return f"Failed to book meeting: {str(e)}"

if __name__ == "__main__":
    mcp.run()