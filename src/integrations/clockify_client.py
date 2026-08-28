"""Clockify API client for fetching users and time entries."""

import requests
import backoff
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.database.config import settings

class ClockifyClient:
    """Client for Clockify API."""
    
    BASE_URL = "https://api.clockify.me/api/v1"
    
    def __init__(self):
        self.api_key = settings.clockify_api_key
        self.workspace_id = settings.clockify_workspace_id
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request with retry logic."""
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def get_users(self, membership_status: str = "ACTIVE") -> List[Dict]:
        """Get users in workspace filtered by workspace membership status.

        Args:
            membership_status: Workspace membership status filter.
                - "ACTIVE": Only workspace-active users (default)
                - "INACTIVE": Only workspace-inactive users
                - "ALL": All users regardless of workspace status

        Note: The 'status' query parameter filters by WORKSPACE membership,
        not by account status. Users returned may have account status "ACTIVE"
        but still be inactive in this specific workspace.
        """
        endpoint = f"/workspaces/{self.workspace_id}/users"
        all_users = []
        page = 1
        page_size = 100

        while True:
            params = {"page": page, "page-size": page_size, "status": membership_status}
            users = self._make_request("GET", endpoint, params=params)
            if not users:
                break
            all_users.extend(users)
            print(f"  Fetched page {page}: {len(users)} users (total: {len(all_users)})")
            if len(users) < page_size:
                break
            page += 1

        return all_users

    def get_user_profile(self, user_id: str) -> Dict:
        """Get user member profile with custom fields."""
        endpoint = f"/workspaces/{self.workspace_id}/member-profile/{user_id}"
        return self._make_request("GET", endpoint)
    
    def get_projects(self, archived: bool = False) -> List[Dict]:
        """Get all projects in workspace (paginated)."""
        endpoint = f"/workspaces/{self.workspace_id}/projects"
        all_projects = []
        page = 1
        page_size = 100
        while True:
            params = {"archived": str(archived).lower(), "hydrated": "true", "page": page, "page-size": page_size}
            batch = self._make_request("GET", endpoint, params=params)
            if not batch:
                break
            all_projects.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return all_projects

    def get_clients(self) -> List[Dict]:
        """Get all clients in workspace (paginated)."""
        endpoint = f"/workspaces/{self.workspace_id}/clients"
        all_clients = []
        page = 1
        page_size = 100
        while True:
            params = {"page": page, "page-size": page_size}
            batch = self._make_request("GET", endpoint, params=params)
            if not batch:
                break
            all_clients.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return all_clients
    
    def get_time_entries(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """Get time entries for a user within date range."""
        endpoint = f"/workspaces/{self.workspace_id}/user/{user_id}/time-entries"
        params = {
            "start": start_date.isoformat() + "Z",
            "end": end_date.isoformat() + "Z",
            "page-size": 200,
            "hydrated": "true"
        }
        return self._make_request("GET", endpoint, params=params)
    
    def get_detailed_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Get detailed time report for all users."""
        endpoint = f"/workspaces/{self.workspace_id}/reports/detailed"
        payload = {
            "dateRangeStart": start_date.isoformat() + "Z",
            "dateRangeEnd": end_date.isoformat() + "Z",
            "detailedFilter": {
                "page": 1,
                "pageSize": 1000
            }
        }
        return self._make_request("POST", endpoint, json=payload)


def debug_user_fields():
    """Debug: Show all fields returned by Clockify for users."""
    print("Debugging Clockify user fields...")

    try:
        client = ClockifyClient()
        users = client.get_users()

        if users:
            # Show first user's raw data
            print("\n=== SAMPLE USER RAW DATA (from /users endpoint) ===")
            sample = users[0]
            for key, value in sample.items():
                print(f"  {key}: {value}")

            # Show member profile data
            print(f"\n=== MEMBER PROFILE DATA (from /member-profile endpoint) ===")
            profile = client.get_user_profile(sample['id'])
            for key, value in profile.items():
                if key != 'userCustomFieldValues':
                    print(f"  {key}: {value}")

            # Count users by status field
            print(f"\n=== USER STATUS COUNTS ===")
            status_counts = {}
            for u in users:
                status = u.get('status', 'NO_STATUS')
                status_counts[status] = status_counts.get(status, 0) + 1
            for status, count in status_counts.items():
                print(f"  {status}: {count} users")

            # Check for memberStatus or other fields
            print(f"\n=== CHECKING FOR OTHER STATUS FIELDS ===")
            for u in users[:5]:
                profile = client.get_user_profile(u['id'])
                print(f"  {u['name']}: status={u.get('status')}, memberStatus={profile.get('memberStatus')}, activeStatus={profile.get('activeStatus')}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_clockify_connection():
    """Test Clockify API connection."""
    print("Testing Clockify connection...")

    try:
        client = ClockifyClient()

        # Test 1: Get users
        print("\n1. Fetching users...")
        users = client.get_users()
        print(f"✓ Found {len(users)} users")
        
        # Test 2: Get projects
        print("\n2. Fetching projects...")
        projects = client.get_projects()
        print(f"✓ Found {len(projects)} projects")
        
        # Test 3: Get recent time entries for first user
        if users:
            print("\n3. Fetching recent time entries...")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            entries = client.get_time_entries(
                user_id=users[0]['id'],
                start_date=start_date,
                end_date=end_date
            )
            print(f"✓ Found {len(entries)} time entries for {users[0]['name']}")
        
        print("\n✅ Clockify connection successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Clockify connection failed: {str(e)}")
        return False


if __name__ == "__main__":
    test_clockify_connection()