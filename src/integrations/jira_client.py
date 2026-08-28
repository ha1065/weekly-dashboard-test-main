"""Jira API client for fetching issues and project data."""

import re
import requests
import backoff
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from src.database.config import settings


class JiraClient:
    """Client for Jira REST API."""

    # Custom field IDs for project tracking - comprehensive list
    CUSTOM_FIELDS = {
        # Project classification
        'project_type': 'customfield_11880',           # Migration, AppDev, etc.

        # Team members
        'project_manager': 'customfield_11781',
        'solution_architect': 'customfield_11533',
        'engineer': 'customfield_11532',
        'account_executive': 'customfield_11534',
        'csm': 'customfield_11735',                    # Customer Success Manager

        # Health status fields
        'current_health': 'customfield_11263',         # Current Project Health
        'health_overall': 'customfield_11271',         # Health: (Red/Yellow/Green)
        'health_budget': 'customfield_11420',          # Budget:
        'health_scope': 'customfield_11454',           # Scope:
        'health_schedule': 'customfield_11455',        # Schedule:
        'schedule_score': 'customfield_11569',         # On Time/Late
        'escalation': 'customfield_11421',             # Escalation
        'impact': 'customfield_11268',                 # Impact:
        'risks_blockers': 'customfield_11489',         # Risks/Blockers

        # Budget
        'budget_hours': 'customfield_11780',           # SOW Hours

        # Date fields - Planning
        'planned_start': 'customfield_10049',
        'planned_end': 'customfield_10050',
        'planned_kickoff': 'customfield_11527',        # Planned Kick-off Date
        'sow_signing_date': 'customfield_11531',       # SOW Signing Date
        'expected_completion': 'customfield_11567',    # Expected Completion Date
        'revised_completion': 'customfield_11568',     # Revise Expected Completion Date
        'resource_assignment_date': 'customfield_11914',  # Resource Assignment Date

        # Date fields - Actual completion by phase
        'actual_kickoff': 'customfield_11913',         # Actual Kick off Date
        'actual_completion': 'customfield_11636',      # Actual Completion Date
        'internal_prep_completion': 'customfield_11522',      # Internal Prep
        'discover_align_completion': 'customfield_11523',     # Discover and Align
        'design_review_completion': 'customfield_11524',      # Design and Review
        'build_implement_completion': 'customfield_11525',    # Build and Implement
        'launch_enable_completion': 'customfield_11526',      # Launch and Enable

        # Narrative fields
        'project_summary': 'customfield_11267',        # Summary:
        'what_we_did': 'customfield_11265',
        'what_we_will_do_next': 'customfield_11266',
        'mitigation_plan': 'customfield_11269',
        'slippages': 'customfield_11264',              # Planned vs Actual

        # Links
        'sow_link': 'customfield_10846',
        'jira_board_link': 'customfield_11528',   # JIRA Board Link
    }

    def __init__(self):
        self.base_url = settings.jira_base_url.rstrip('/')
        self.email = settings.jira_api_email
        self.api_token = settings.jira_api_token

        # Use Basic authentication (email:token) for Jira Cloud API
        credentials = base64.b64encode(
            f"{self.email}:{self.api_token}".encode()
        ).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Custom field ID for phase (configure in .env)
        self.phase_field_id = settings.jira_phase_field_id

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=3
    )
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_projects(self) -> List[Dict]:
        """Get all accessible projects."""
        endpoint = "/rest/api/3/project"
        return self._make_request("GET", endpoint)

    def get_field_definitions(self) -> List[Dict]:
        """Get all field definitions including custom fields."""
        endpoint = "/rest/api/3/field"
        return self._make_request("GET", endpoint)

    def search_issues(
        self,
        jql: str,
        max_results: int = 100,
        fields: List[str] = None,
        next_page_token: str = None
    ) -> Dict:
        """Search issues using JQL with cursor-based pagination."""
        endpoint = "/rest/api/3/search/jql"

        if fields is None:
            fields = [
                'summary', 'status', 'priority', 'issuetype',
                'project', 'assignee', 'reporter', 'created',
                'updated', 'resolutiondate', 'duedate'
            ]
            # Add custom phase field if configured
            if self.phase_field_id:
                fields.append(self.phase_field_id)
            # Add all project tracking custom fields
            fields.extend(self.CUSTOM_FIELDS.values())
            # Add JSM Request Type field
            fields.append('customfield_10010')

        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields
        }

        if next_page_token:
            payload["nextPageToken"] = next_page_token

        return self._make_request("POST", endpoint, json=payload)

    def get_issues_updated_since(
        self,
        since_date: datetime,
        project_keys: List[str] = None
    ) -> List[Dict]:
        """Get all issues updated since a given date."""
        date_str = since_date.strftime('%Y-%m-%d %H:%M')
        jql_parts = [f'updated >= "{date_str}"']

        if project_keys:
            keys_str = ','.join(project_keys)
            jql_parts.append(f'project in ({keys_str})')

        jql = ' AND '.join(jql_parts)

        all_issues = []
        next_page_token = None

        while True:
            result = self.search_issues(
                jql=jql,
                max_results=100,
                next_page_token=next_page_token
            )

            issues = result.get('issues', [])
            all_issues.extend(issues)

            if result.get('isLast', True):
                break

            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break

            print(f"  Fetched {len(all_issues)} issues so far...")

        return all_issues

    def get_all_project_issues(self, project_keys: List[str]) -> List[Dict]:
        """Get all issues for specified projects (full sync)."""
        if not project_keys:
            return []

        keys_str = ','.join(project_keys)
        jql = f'project in ({keys_str}) ORDER BY updated DESC'

        all_issues = []
        next_page_token = None

        while True:
            result = self.search_issues(
                jql=jql,
                max_results=100,
                next_page_token=next_page_token
            )

            issues = result.get('issues', [])
            all_issues.extend(issues)

            if result.get('isLast', True):
                break

            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break

            print(f"  Fetched {len(all_issues)} issues so far...")

        return all_issues

    @staticmethod
    def parse_client_project_from_summary(summary: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse client name and project name from summary field.

        Patterns:
        - "ClientName - Project Description" -> (ClientName, Project Description)
        - "ClientName ProjectType" -> (ClientName, ProjectType)
        - "Client Name Multi Word - Description" -> (Client Name Multi Word, Description)

        Returns:
            Tuple of (client_name, project_name)
        """
        if not summary:
            return None, None

        summary = summary.strip()

        # Pattern 1: "Client - Project" (dash separator)
        if ' - ' in summary:
            parts = summary.split(' - ', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None

        # Pattern 2: "Client: Project" (colon separator)
        if ': ' in summary:
            parts = summary.split(': ', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None

        # Pattern 3: Look for known project types at the end
        project_types = [
            'Migration', 'AppDev', 'Infrastructure', 'Connect', 'AI/ML',
            'Security', 'DevOps', 'Data', 'Analytics', 'Modernization',
            'Assessment', 'Optimization', 'Support', 'Managed Services'
        ]

        for ptype in project_types:
            if summary.endswith(ptype):
                client = summary[:-len(ptype)].strip()
                return client, ptype

        # Pattern 4: Last word as project type if summary has multiple words
        words = summary.split()
        if len(words) >= 2:
            # Assume last 1-2 words are project type
            client = ' '.join(words[:-1])
            project = words[-1]
            return client, project

        # Fallback: entire summary as client name
        return summary, None

    def _extract_field_value(self, fields: Dict, field_id: str) -> Optional[any]:
        """Extract a field value, handling various Jira field types."""
        value = fields.get(field_id)

        if value is None:
            return None

        # String values
        if isinstance(value, str):
            return value

        # Numeric values
        if isinstance(value, (int, float)):
            return value

        # Dict values (user fields, option fields)
        if isinstance(value, dict):
            return value.get('displayName') or value.get('value') or value.get('name')

        # List values (multi-select, etc.)
        if isinstance(value, list) and len(value) > 0:
            first = value[0]
            if isinstance(first, dict):
                return first.get('displayName') or first.get('value') or first.get('name')
            return str(first)

        return str(value) if value else None

    def _extract_multi_user_field(self, fields: Dict, field_id: str) -> Optional[str]:
        """Extract a multi-user field, joining all display names with ', '."""
        raw = fields.get(field_id)
        if not raw:
            return None
        if isinstance(raw, list):
            names = [
                (item.get('displayName') or item.get('name') or str(item))
                for item in raw
                if isinstance(item, dict)
            ]
            return ', '.join(names) if names else None
        # Fall back to standard extraction for single-user or string values
        return self._extract_field_value(fields, field_id)

    def extract_custom_fields(self, issue: Dict) -> Dict[str, any]:
        """Extract all custom fields from an issue."""
        fields = issue.get('fields', {})
        result = {}

        for field_key, field_id in self.CUSTOM_FIELDS.items():
            if field_key == 'engineer':
                result[field_key] = self._extract_multi_user_field(fields, field_id)
            else:
                result[field_key] = self._extract_field_value(fields, field_id)

        return result

    def extract_phase(self, issue: Dict) -> Optional[str]:
        """Extract phase value from custom field."""
        if not self.phase_field_id:
            return None

        fields = issue.get('fields', {})
        return self._extract_field_value(fields, self.phase_field_id)
