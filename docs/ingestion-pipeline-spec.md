# Ingestion Pipeline Implementation Spec

**Version:** 1.0
**Date:** 2026-08-10
**Status:** Proposed
**Replaces:** Monolithic `lambda_handler.py` (30 modes, 2,034 lines)

---

## 1. Executive Summary

Replace the current monolithic Lambda function with a purpose-built ingestion pipeline using AWS Step Functions orchestrating lightweight, single-responsibility Lambda functions. Raw data lands in S3 (immutable, reprocessable), transforms produce Parquet for Athena/QuickSight consumption, and RDS PostgreSQL is eventually decommissioned from the read path.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      EVENT TRIGGERS                                  │
│  EventBridge: Mon 9:00 AM CT (weekly)                               │
│  EventBridge: Daily 10:00 AM UTC (jira)                             │
│  EventBridge: Mon 12:00 PM CT (kpi snapshot)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              STEP FUNCTIONS: WeeklyIngestionPipeline                 │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌───────────────┐   │
│  │ Clockify │   │   Jira   │   │   KPI    │   │  QuickSight   │   │
│  │  Import  │──▶│  Import  │──▶│ Snapshot │──▶│ SPICE Refresh │   │
│  └──────────┘   └──────────┘   └──────────┘   └───────────────┘   │
│       │              │              │                    │           │
│       ▼              ▼              ▼                    ▼           │
│  S3: raw/        S3: raw/     S3: curated/      QuickSight SPICE   │
│  clockify/       jira/        kpi_snapshots/                        │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA LAKE (S3)                                    │
│                                                                     │
│  s3://cdx-reporting-{env}/                                          │
│  ├── raw/                    (immutable JSON, date-partitioned)     │
│  │   ├── clockify/users/     YYYY/MM/DD/users.json                 │
│  │   ├── clockify/projects/  YYYY/MM/DD/projects.json              │
│  │   ├── clockify/entries/   YYYY/MM/DD/entries.json               │
│  │   └── jira/issues/        YYYY/MM/DD/issues.json                │
│  ├── curated/                (Parquet, partitioned by week_start)   │
│  │   ├── time_entries/       week_start=2026-08-04/data.parquet    │
│  │   ├── users/              snapshot_date=2026-08-10/data.parquet  │
│  │   ├── projects/           snapshot_date=2026-08-10/data.parquet  │
│  │   ├── jira_projects/      snapshot_date=2026-08-10/data.parquet  │
│  │   └── kpi_snapshots/      week_start=2026-08-04/data.parquet    │
│  └── athena-results/         (query output)                         │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              QUERY LAYER (Glue Data Catalog + Athena)                │
│                                                                     │
│  Database: cdx_reporting                                            │
│  Tables: time_entries, users, projects, jira_projects, kpi_snapshots│
│  Views: vw_weekly_summary, vw_utilization, vw_project_health, etc.  │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              QUICKSIGHT (SPICE datasets from Athena)                 │
│                                                                     │
│  3 Dashboards: Executive Summary, COO Operational, Detailed         │
│  ~12 SPICE datasets (down from 47 — consolidated)                  │
│  Scheduled refresh: Mon 12:30 PM CT (after pipeline completes)      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. S3 Bucket Design

### 3.1 Bucket Name

```
cdx-reporting-production
cdx-reporting-staging     (optional, for dev testing)
```

### 3.2 Prefix Structure

```
raw/
  clockify/
    users/{YYYY}/{MM}/{DD}/users_{timestamp}.json
    projects/{YYYY}/{MM}/{DD}/projects_{timestamp}.json
    entries/{YYYY}/{MM}/{DD}/entries_{timestamp}.json
  jira/
    issues/{YYYY}/{MM}/{DD}/issues_{timestamp}.json

curated/
  time_entries/
    week_start={YYYY-MM-DD}/data.parquet
  users/
    snapshot_date={YYYY-MM-DD}/data.parquet
  projects/
    snapshot_date={YYYY-MM-DD}/data.parquet
  jira_projects/
    snapshot_date={YYYY-MM-DD}/data.parquet
  kpi_snapshots/
    week_start={YYYY-MM-DD}/data.parquet

athena-results/
  (Athena query output — lifecycle: 7 days)
```

### 3.3 Lifecycle Rules

| Prefix | Rule | Rationale |
|--------|------|-----------|
| `raw/` | Transition to IA after 30 days, Glacier after 90 days | Raw JSON is rarely re-read after initial transform |
| `curated/` | No expiry (retain indefinitely) | Parquet files are small and serve as the analytical source of truth |
| `athena-results/` | Expire after 7 days | Ephemeral query output |

### 3.4 Bucket Policy

- Block all public access
- SSE-S3 encryption (default)
- Versioning: enabled on `raw/` prefix (allows reprocessing from any historical pull)
- Access: Lambda execution roles only (write to raw/, read/write to curated/)

---

## 4. Secrets Management

Secrets remain in AWS Secrets Manager (existing `production/weekly-reporting/clockify` secret). Each Lambda reads only the secrets it needs.

| Secret Key | Used By |
|------------|---------|
| `clockify_api_key` | clockify-import Lambda |
| `clockify_workspace_id` | clockify-import Lambda |
| `jira_base_url` | jira-import Lambda |
| `jira_api_email` | jira-import Lambda |
| `jira_api_token` | jira-import Lambda |
| `jira_project_keys` | jira-import Lambda |
| `db_password` | kpi-snapshot Lambda (write-back to RDS during transition) |

---

## 5. IAM Roles (One Per Lambda)

### 5.1 clockify-import-role

```yaml
Policies:
  - Effect: Allow
    Action:
      - s3:PutObject
    Resource: arn:aws:s3:::cdx-reporting-production/raw/clockify/*
  - Effect: Allow
    Action:
      - secretsmanager:GetSecretValue
    Resource: arn:aws:secretsmanager:us-east-1:961341524729:secret:production/weekly-reporting/*
  - Effect: Allow
    Action:
      - logs:CreateLogGroup
      - logs:CreateLogStream
      - logs:PutLogEvents
    Resource: "*"
```

### 5.2 jira-import-role

```yaml
Policies:
  - Effect: Allow
    Action:
      - s3:PutObject
    Resource: arn:aws:s3:::cdx-reporting-production/raw/jira/*
  - Effect: Allow
    Action:
      - secretsmanager:GetSecretValue
    Resource: arn:aws:secretsmanager:us-east-1:961341524729:secret:production/weekly-reporting/*
  - Effect: Allow
    Action:
      - logs:CreateLogGroup
      - logs:CreateLogStream
      - logs:PutLogEvents
    Resource: "*"
```

### 5.3 transform-role (KPI snapshot + Parquet writer)

```yaml
Policies:
  - Effect: Allow
    Action:
      - s3:GetObject
    Resource: arn:aws:s3:::cdx-reporting-production/raw/*
  - Effect: Allow
    Action:
      - s3:PutObject
    Resource: arn:aws:s3:::cdx-reporting-production/curated/*
  - Effect: Allow
    Action:
      - secretsmanager:GetSecretValue
    Resource: arn:aws:secretsmanager:us-east-1:961341524729:secret:production/weekly-reporting/*
  - Effect: Allow
    Action:
      - logs:*
    Resource: "*"
```

### 5.4 quicksight-refresh-role

```yaml
Policies:
  - Effect: Allow
    Action:
      - quicksight:CreateIngestion
      - quicksight:DescribeIngestion
      - quicksight:ListIngestions
    Resource: arn:aws:quicksight:us-east-1:961341524729:dataset/*
  - Effect: Allow
    Action:
      - logs:*
    Resource: "*"
```

---

## 6. Lambda: clockify-import

### 6.1 Purpose

Pulls users, projects, and time entries from the Clockify API and writes raw JSON to S3. No database writes. No transformations. Pure extraction.

### 6.2 Configuration

| Property | Value |
|----------|-------|
| Runtime | Python 3.12 |
| Architecture | arm64 (Graviton) |
| Memory | 512 MB |
| Timeout | 5 minutes |
| Layers | None (only `requests`, `backoff` — bundled in ZIP) |
| Package size | ~2 MB (vs current 19 MB) |
| VPC | **No** (no database access needed) |
| Trigger | Step Functions invocation |

### 6.3 Input Event

```json
{
  "mode": "incremental" | "weekly" | "full",
  "weeks_back": 1,
  "run_date": "2026-08-10T09:00:00Z"
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `mode` | Import scope | `incremental` |
| `weeks_back` | How many weeks of time entries to pull | 1 (incremental), 52 (full) |
| `run_date` | ISO timestamp of the pipeline run | now() |

### 6.4 Output Event (returned to Step Functions)

```json
{
  "status": "SUCCESS",
  "run_date": "2026-08-10",
  "s3_paths": {
    "users": "s3://cdx-reporting-production/raw/clockify/users/2026/08/10/users_20260810T090000.json",
    "projects": "s3://cdx-reporting-production/raw/clockify/projects/2026/08/10/projects_20260810T090000.json",
    "entries": "s3://cdx-reporting-production/raw/clockify/entries/2026/08/10/entries_20260810T090000.json"
  },
  "counts": {
    "users": 87,
    "projects": 142,
    "entries": 1247
  },
  "date_range": {
    "start": "2026-08-04",
    "end": "2026-08-10"
  }
}
```

### 6.5 Implementation Logic

```python
"""clockify-import Lambda handler."""
import json
import os
from datetime import datetime, timedelta
import boto3
import requests
import backoff

s3 = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')

BUCKET = os.environ['DATA_BUCKET']
SECRET_NAME = os.environ['SECRET_NAME']

# Cache secrets across warm invocations
_secrets_cache = None


def get_secrets():
    global _secrets_cache
    if _secrets_cache is None:
        resp = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        _secrets_cache = json.loads(resp['SecretString'])
    return _secrets_cache


class ClockifyExtractor:
    BASE_URL = "https://api.clockify.me/api/v1"

    def __init__(self, api_key: str, workspace_id: str):
        self.workspace_id = workspace_id
        self.headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
    def _get(self, endpoint: str, params: dict = None) -> list | dict:
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def extract_users(self) -> list[dict]:
        """Paginate through all users (active + inactive)."""
        all_users = []
        for status in ("ACTIVE", "INACTIVE"):
            page = 1
            while True:
                batch = self._get(
                    f"/workspaces/{self.workspace_id}/users",
                    params={"page": page, "page-size": 100, "status": status}
                )
                if not batch:
                    break
                all_users.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
        return all_users

    def extract_user_profiles(self, user_ids: list[str]) -> list[dict]:
        """Fetch member-profile for each user (custom fields)."""
        profiles = []
        for uid in user_ids:
            try:
                profile = self._get(f"/workspaces/{self.workspace_id}/member-profile/{uid}")
                profiles.append(profile)
            except Exception as e:
                profiles.append({"userId": uid, "error": str(e)})
        return profiles

    def extract_projects(self) -> list[dict]:
        """Paginate through all projects (active + archived)."""
        all_projects = []
        for archived in ("false", "true"):
            page = 1
            while True:
                batch = self._get(
                    f"/workspaces/{self.workspace_id}/projects",
                    params={"archived": archived, "hydrated": "true",
                            "page": page, "page-size": 100}
                )
                if not batch:
                    break
                all_projects.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
        return all_projects

    def extract_time_entries(self, start: datetime, end: datetime) -> list[dict]:
        """Use the detailed report endpoint for bulk extraction."""
        all_entries = []
        page = 1
        while True:
            payload = {
                "dateRangeStart": start.strftime("%Y-%m-%dT00:00:00Z"),
                "dateRangeEnd": end.strftime("%Y-%m-%dT23:59:59Z"),
                "detailedFilter": {"page": page, "pageSize": 1000},
                "sortOrder": "ASCENDING"
            }
            resp = requests.post(
                f"https://reports.api.clockify.me/v1/workspaces/{self.workspace_id}/reports/detailed",
                headers=self.headers, json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("timeentries", [])
            all_entries.extend(entries)
            if len(entries) < 1000:
                break
            page += 1
        return all_entries


def write_to_s3(prefix: str, data: list | dict, run_ts: str) -> str:
    """Write JSON to S3 and return the full S3 path."""
    today = datetime.utcnow()
    key = f"{prefix}/{today.strftime('%Y/%m/%d')}/{prefix.split('/')[-1]}_{run_ts}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(data, default=str),
        ContentType="application/json"
    )
    return f"s3://{BUCKET}/{key}"


def handler(event, context):
    secrets = get_secrets()
    extractor = ClockifyExtractor(
        api_key=secrets['clockify_api_key'],
        workspace_id=secrets['clockify_workspace_id']
    )

    mode = event.get('mode', 'incremental')
    weeks_back = event.get('weeks_back', 1 if mode == 'incremental' else 52)
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")

    # Date range for time entries
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(weeks=weeks_back)

    # Extract
    users = extractor.extract_users()
    user_ids = [u['id'] for u in users]
    profiles = extractor.extract_user_profiles(user_ids)
    projects = extractor.extract_projects()
    entries = extractor.extract_time_entries(start_date, end_date)

    # Merge profiles into users for single file
    profile_map = {p.get('userId', p.get('id', '')): p for p in profiles if 'error' not in p}
    for user in users:
        if user['id'] in profile_map:
            user['_profile'] = profile_map[user['id']]

    # Write raw JSON to S3
    users_path = write_to_s3("raw/clockify/users", users, run_ts)
    projects_path = write_to_s3("raw/clockify/projects", projects, run_ts)
    entries_path = write_to_s3("raw/clockify/entries", entries, run_ts)

    return {
        "status": "SUCCESS",
        "run_date": end_date.strftime("%Y-%m-%d"),
        "s3_paths": {
            "users": users_path,
            "projects": projects_path,
            "entries": entries_path
        },
        "counts": {
            "users": len(users),
            "projects": len(projects),
            "entries": len(entries)
        },
        "date_range": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        }
    }
```

### 6.6 Error Handling

| Failure | Behavior |
|---------|----------|
| Clockify API 429 (rate limit) | `backoff` retries with exponential delay (3 attempts) |
| Clockify API 5xx | Retry 3x, then raise → Step Functions catches and sends SNS alert |
| S3 write failure | Raise immediately → Step Functions retry policy (2 attempts) |
| Timeout (>5 min) | Step Functions detects timeout, marks step as failed |

### 6.7 Dependencies (requirements.txt)

```
requests==2.32.3
backoff==2.2.1
boto3  # provided by Lambda runtime
```

---

## 7. Lambda: jira-import

### 7.1 Purpose

Pulls PS/MC project issues from Jira Cloud API and writes raw JSON to S3. Extracts all custom fields (health status, budget, dates, team members) for downstream transformation.

### 7.2 Configuration

| Property | Value |
|----------|-------|
| Runtime | Python 3.12 |
| Architecture | arm64 (Graviton) |
| Memory | 256 MB |
| Timeout | 3 minutes |
| VPC | **No** |
| Trigger | Step Functions invocation |

### 7.3 Input Event

```json
{
  "mode": "incremental" | "full",
  "since_date": "2026-08-03T00:00:00Z",
  "project_keys": ["PS", "MC", "ESC"]
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `mode` | `incremental` = updated since last run; `full` = all issues | `incremental` |
| `since_date` | Override for incremental cutoff (ISO datetime) | 7 days ago |
| `project_keys` | Jira project keys to query | From secrets (`jira_project_keys`) |

### 7.4 Output Event

```json
{
  "status": "SUCCESS",
  "s3_path": "s3://cdx-reporting-production/raw/jira/issues/2026/08/10/issues_20260810T100000.json",
  "counts": {
    "issues_fetched": 48,
    "projects_queried": ["PS", "MC", "ESC"]
  }
}
```

### 7.5 Implementation Logic

```python
"""jira-import Lambda handler."""
import json
import os
import base64
from datetime import datetime, timedelta
import boto3
import requests
import backoff

s3 = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')

BUCKET = os.environ['DATA_BUCKET']
SECRET_NAME = os.environ['SECRET_NAME']

_secrets_cache = None


def get_secrets():
    global _secrets_cache
    if _secrets_cache is None:
        resp = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        _secrets_cache = json.loads(resp['SecretString'])
    return _secrets_cache


# Custom field IDs (from existing jira_client.py)
CUSTOM_FIELDS = {
    'project_type': 'customfield_11880',
    'project_manager': 'customfield_11781',
    'solution_architect': 'customfield_11533',
    'engineer': 'customfield_11532',
    'current_health': 'customfield_11263',
    'health_overall': 'customfield_11271',
    'health_budget': 'customfield_11420',
    'health_scope': 'customfield_11454',
    'health_schedule': 'customfield_11455',
    'budget_hours': 'customfield_11780',
    'planned_start': 'customfield_10049',
    'planned_end': 'customfield_10050',
    'expected_completion': 'customfield_11567',
    'actual_completion': 'customfield_11636',
    'escalation': 'customfield_11421',
    'risks_blockers': 'customfield_11489',
    'what_we_did': 'customfield_11265',
    'what_we_will_do_next': 'customfield_11266',
}


class JiraExtractor:
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
    def _post(self, endpoint: str, payload: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}{endpoint}",
            headers=self.headers, json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def extract_issues(self, project_keys: list[str], since: datetime = None) -> list[dict]:
        """Fetch all issues using cursor-based pagination."""
        jql_parts = [f"project in ({','.join(project_keys)})"]
        if since:
            jql_parts.append(f'updated >= "{since.strftime("%Y-%m-%d %H:%M")}"')
        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

        fields = [
            'summary', 'status', 'priority', 'issuetype', 'project',
            'assignee', 'reporter', 'created', 'updated', 'resolutiondate',
            'duedate', 'customfield_10010'
        ] + list(CUSTOM_FIELDS.values())

        all_issues = []
        next_page_token = None

        while True:
            payload = {"jql": jql, "maxResults": 100, "fields": fields}
            if next_page_token:
                payload["nextPageToken"] = next_page_token

            result = self._post("/rest/api/3/search/jql", payload)
            issues = result.get('issues', [])
            all_issues.extend(issues)

            if result.get('isLast', True):
                break
            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break

        return all_issues


def handler(event, context):
    secrets = get_secrets()
    extractor = JiraExtractor(
        base_url=secrets['jira_base_url'],
        email=secrets['jira_api_email'],
        api_token=secrets['jira_api_token']
    )

    mode = event.get('mode', 'incremental')
    project_keys = event.get('project_keys') or secrets.get('jira_project_keys', 'PS,MC,ESC').split(',')
    project_keys = [k.strip() for k in project_keys]

    since = None
    if mode == 'incremental':
        since_str = event.get('since_date')
        if since_str:
            since = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
        else:
            since = datetime.utcnow() - timedelta(days=7)

    # Extract
    issues = extractor.extract_issues(project_keys, since=since)

    # Write to S3
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    today = datetime.utcnow()
    key = f"raw/jira/issues/{today.strftime('%Y/%m/%d')}/issues_{run_ts}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(issues, default=str),
        ContentType="application/json"
    )

    return {
        "status": "SUCCESS",
        "s3_path": f"s3://{BUCKET}/{key}",
        "counts": {
            "issues_fetched": len(issues),
            "projects_queried": project_keys
        }
    }
```

### 7.6 Error Handling

| Failure | Behavior |
|---------|----------|
| Jira 401 (auth expired) | Raise immediately — manual intervention needed (rotate token) |
| Jira 429 (rate limit) | `backoff` retries with exponential delay |
| Jira 5xx | Retry 3x, then fail → SNS notification |
| Empty result set | Return SUCCESS with count=0 (not an error — project may have no updates) |

### 7.7 Dependencies

```
requests==2.32.3
backoff==2.2.1
```

---

## 8. Lambda: transform-and-snapshot

### 8.1 Purpose

Reads raw JSON from S3, transforms/flattens it into analytics-ready Parquet files in the `curated/` prefix, and computes weekly KPI snapshots. This is the only Lambda that needs pandas/pyarrow (heavier dependencies).

### 8.2 Configuration

| Property | Value |
|----------|-------|
| Runtime | Python 3.12 |
| Architecture | arm64 (Graviton) |
| Memory | 1024 MB (pandas + pyarrow need RAM for columnar conversion) |
| Timeout | 5 minutes |
| VPC | **Yes** (needs RDS access during transition period for KPI write-back) |
| Trigger | Step Functions invocation (after clockify-import and jira-import complete) |
| Layer | `pandas-pyarrow-arm64` (shared Lambda layer, ~50 MB) |

### 8.3 Input Event

```json
{
  "clockify_output": {
    "s3_paths": {
      "users": "s3://cdx-reporting-production/raw/clockify/users/2026/08/10/users_20260810T090000.json",
      "projects": "s3://cdx-reporting-production/raw/clockify/projects/2026/08/10/projects_20260810T090000.json",
      "entries": "s3://cdx-reporting-production/raw/clockify/entries/2026/08/10/entries_20260810T090000.json"
    },
    "date_range": { "start": "2026-08-04", "end": "2026-08-10" }
  },
  "jira_output": {
    "s3_path": "s3://cdx-reporting-production/raw/jira/issues/2026/08/10/issues_20260810T100000.json"
  },
  "snapshot_kpis": true
}
```

### 8.4 Output Event

```json
{
  "status": "SUCCESS",
  "curated_paths": {
    "time_entries": "s3://cdx-reporting-production/curated/time_entries/week_start=2026-08-04/data.parquet",
    "users": "s3://cdx-reporting-production/curated/users/snapshot_date=2026-08-10/data.parquet",
    "projects": "s3://cdx-reporting-production/curated/projects/snapshot_date=2026-08-10/data.parquet",
    "jira_projects": "s3://cdx-reporting-production/curated/jira_projects/snapshot_date=2026-08-10/data.parquet",
    "kpi_snapshots": "s3://cdx-reporting-production/curated/kpi_snapshots/week_start=2026-08-04/data.parquet"
  },
  "kpi_summary": {
    "week_start": "2026-08-04",
    "utilization_pct": 78.4,
    "ps_on_time_pct": 85.0,
    "mc_health_green_pct": 92.3,
    "total_hours": 3420.5
  }
}
```

### 8.5 Transform Logic

#### 8.5.1 Users Transform

Flattens the Clockify user + profile data into a clean analytical schema:

```python
def transform_users(raw_users: list[dict]) -> pd.DataFrame:
    """Flatten Clockify users + embedded profiles into analytics schema."""
    rows = []
    for user in raw_users:
        profile = user.get('_profile', {})
        custom_fields = profile.get('userCustomFieldValues', [])

        rows.append({
            'clockify_user_id': user['id'],
            'name': user.get('name', '').strip(),
            'email': user.get('email'),
            'status': user.get('status', 'ACTIVE').lower(),
            'daily_capacity_hours': _parse_capacity(profile.get('workCapacity')),
            'practice_alignment': _get_cf(custom_fields, 'Practice Alignment'),
            'skill_area': _get_cf(custom_fields, 'Skill Area'),
            'pod_assignment': _get_cf(custom_fields, 'POD Assignment'),
            'title': _get_cf(custom_fields, 'Cloudelligent Title'),
            'location': _get_cf(custom_fields, 'Location') or 'Unknown',
            'employment_designation': _get_cf(custom_fields, 'Employment Designation') or 'FTE',
            'level': _get_cf(custom_fields, 'Level'),
        })

    return pd.DataFrame(rows)
```

#### 8.5.2 Time Entries Transform

Denormalizes Clockify report entries into a flat analytical table:

```python
def transform_entries(raw_entries: list[dict], users_df: pd.DataFrame) -> pd.DataFrame:
    """Flatten detailed report entries with user enrichment."""
    rows = []
    for entry in raw_entries:
        user_id = entry.get('userId', '')
        rows.append({
            'clockify_entry_id': entry.get('_id', entry.get('id', '')),
            'clockify_user_id': user_id,
            'user_name': entry.get('userName', ''),
            'project_name': entry.get('projectName', ''),
            'client_name': entry.get('clientName', ''),
            'task_name': entry.get('taskName', ''),
            'description': entry.get('description', ''),
            'billable': entry.get('billable', True),
            'duration_hours': entry.get('timeInterval', {}).get('duration', 0) / 3600,
            'start_time': entry.get('timeInterval', {}).get('start'),
            'end_time': entry.get('timeInterval', {}).get('end'),
            'entry_date': entry.get('timeInterval', {}).get('start', '')[:10],
        })

    df = pd.DataFrame(rows)
    # Add week_start partition column
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df['week_start'] = df['entry_date'] - pd.to_timedelta(df['entry_date'].dt.weekday, unit='D')

    # Enrich with user attributes (practice, pod, location)
    if not users_df.empty:
        user_attrs = users_df[['clockify_user_id', 'practice_alignment',
                               'pod_assignment', 'location', 'employment_designation']]
        df = df.merge(user_attrs, on='clockify_user_id', how='left')

    return df
```

#### 8.5.3 Jira Projects Transform

```python
def transform_jira(raw_issues: list[dict]) -> pd.DataFrame:
    """Flatten Jira issues with custom field extraction."""
    rows = []
    for issue in raw_issues:
        fields = issue.get('fields', {})
        row = {
            'jira_key': issue.get('key'),
            'summary': fields.get('summary'),
            'status': fields.get('status', {}).get('name'),
            'issue_type': fields.get('issuetype', {}).get('name'),
            'project_key': fields.get('project', {}).get('key'),
            'created': fields.get('created'),
            'updated': fields.get('updated'),
        }
        # Extract custom fields
        for field_name, field_id in JIRA_CUSTOM_FIELDS.items():
            row[field_name] = _extract_jira_field(fields, field_id)
        rows.append(row)

    return pd.DataFrame(rows)
```

#### 8.5.4 KPI Snapshot Computation

Computes the same KPIs as the existing `kpi_snapshot.py` but from the in-memory DataFrames rather than SQL queries:

```python
def compute_kpi_snapshot(entries_df: pd.DataFrame, users_df: pd.DataFrame,
                         jira_df: pd.DataFrame, week_start: date) -> dict:
    """Compute weekly KPI values from transformed DataFrames."""
    week_end = week_start + timedelta(days=6)

    # Filter entries to target week
    week_entries = entries_df[
        (entries_df['week_start'] == pd.Timestamp(week_start))
    ]

    # --- Utilization ---
    active_users = users_df[users_df['status'] == 'active']
    total_capacity = active_users['daily_capacity_hours'].sum() * 5  # 5-day week
    total_hours = week_entries['duration_hours'].sum()
    utilization_pct = (total_hours / total_capacity * 100) if total_capacity > 0 else 0

    # --- Billable ratio ---
    billable_hours = week_entries[week_entries['billable'] == True]['duration_hours'].sum()
    billable_pct = (billable_hours / total_hours * 100) if total_hours > 0 else 0

    # --- PS metrics ---
    ps_issues = jira_df[jira_df['project_key'] == 'PS']
    ps_total = len(ps_issues)
    ps_green = len(ps_issues[ps_issues['health_overall'] == 'Green'])
    ps_health_pct = (ps_green / ps_total * 100) if ps_total > 0 else 0

    # --- MC metrics ---
    mc_issues = jira_df[jira_df['project_key'] == 'MC']
    mc_total = len(mc_issues)
    mc_green = len(mc_issues[mc_issues['health_overall'] == 'Green'])
    mc_health_pct = (mc_green / mc_total * 100) if mc_total > 0 else 0

    # --- Compliance (40hr/week) ---
    user_weekly = week_entries.groupby('clockify_user_id')['duration_hours'].sum()
    fte_users = active_users[active_users['employment_designation'] == 'FTE']
    compliant = sum(1 for uid in fte_users['clockify_user_id'] if user_weekly.get(uid, 0) >= 40)
    compliance_pct = (compliant / len(fte_users) * 100) if len(fte_users) > 0 else 0

    return {
        'week_start': str(week_start),
        'week_end': str(week_end),
        'total_hours': round(total_hours, 1),
        'utilization_pct': round(utilization_pct, 1),
        'billable_pct': round(billable_pct, 1),
        'ps_total_projects': ps_total,
        'ps_health_green_pct': round(ps_health_pct, 1),
        'mc_total_customers': mc_total,
        'mc_health_green_pct': round(mc_health_pct, 1),
        'compliance_pct': round(compliance_pct, 1),
        'headcount_active': len(active_users),
    }
```

### 8.6 Parquet Write Pattern

```python
def write_parquet(df: pd.DataFrame, prefix: str, partition_col: str, partition_val: str):
    """Write a DataFrame as Parquet to S3 with Hive-style partitioning."""
    key = f"curated/{prefix}/{partition_col}={partition_val}/data.parquet"
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine='pyarrow')
    buffer.seek(0)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
    return f"s3://{BUCKET}/{key}"
```

### 8.7 Transition Period: RDS Write-Back

During the migration period (until QuickSight is fully on Athena), this Lambda also writes the KPI snapshot row to `kpi_weekly_snapshots` in RDS — same logic as the existing `kpi_snapshot.py`:

```python
def write_kpi_to_rds(kpi: dict, engine):
    """Upsert KPI row to RDS for backward compatibility."""
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO kpi_weekly_snapshots (week_start, week_end, ...)
            VALUES (:week_start, :week_end, ...)
            ON CONFLICT (week_start) DO UPDATE SET ...
        """), kpi)
        conn.commit()
```

This write-back is removed once QuickSight datasets are migrated to Athena.

### 8.8 Dependencies

```
pandas==2.2.3
pyarrow==17.0.0
requests==2.32.3
sqlalchemy==2.0.31
pg8000==1.31.2
boto3  # runtime
```

---

## 9. Step Functions: WeeklyIngestionPipeline

### 9.1 Purpose

Orchestrates the full ingestion pipeline as a state machine. Handles parallelism (Clockify and Jira can run concurrently), sequencing (transform depends on both), retries, error notifications, and provides full execution visibility.

### 9.2 State Machine Definition (ASL)

```json
{
  "Comment": "Weekly Reporting Ingestion Pipeline",
  "StartAt": "ExtractData",
  "States": {
    "ExtractData": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "ClockifyImport",
          "States": {
            "ClockifyImport": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:us-east-1:961341524729:function:clockify-import",
              "Parameters": {
                "mode.$": "$.mode",
                "weeks_back.$": "$.weeks_back",
                "run_date.$": "$$.Execution.StartTime"
              },
              "Retry": [
                {
                  "ErrorEquals": ["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
                  "IntervalSeconds": 30,
                  "MaxAttempts": 2,
                  "BackoffRate": 2
                }
              ],
              "Catch": [
                {
                  "ErrorEquals": ["States.ALL"],
                  "Next": "ClockifyFailed",
                  "ResultPath": "$.error"
                }
              ],
              "End": true
            },
            "ClockifyFailed": {
              "Type": "Pass",
              "Result": { "status": "FAILED", "source": "clockify" },
              "End": true
            }
          }
        },
        {
          "StartAt": "JiraImport",
          "States": {
            "JiraImport": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:us-east-1:961341524729:function:jira-import",
              "Parameters": {
                "mode.$": "$.mode"
              },
              "Retry": [
                {
                  "ErrorEquals": ["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
                  "IntervalSeconds": 30,
                  "MaxAttempts": 2,
                  "BackoffRate": 2
                }
              ],
              "Catch": [
                {
                  "ErrorEquals": ["States.ALL"],
                  "Next": "JiraFailed",
                  "ResultPath": "$.error"
                }
              ],
              "End": true
            },
            "JiraFailed": {
              "Type": "Pass",
              "Result": { "status": "FAILED", "source": "jira" },
              "End": true
            }
          }
        }
      ],
      "ResultPath": "$.extract_results",
      "Next": "CheckExtractionResults"
    },

    "CheckExtractionResults": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.extract_results[0].status",
          "StringEquals": "FAILED",
          "Next": "NotifyFailure"
        }
      ],
      "Default": "TransformAndSnapshot"
    },

    "TransformAndSnapshot": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:961341524729:function:transform-and-snapshot",
      "Parameters": {
        "clockify_output.$": "$.extract_results[0]",
        "jira_output.$": "$.extract_results[1]",
        "snapshot_kpis": true
      },
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException"],
          "IntervalSeconds": 60,
          "MaxAttempts": 1,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyFailure",
          "ResultPath": "$.error"
        }
      ],
      "ResultPath": "$.transform_results",
      "Next": "RefreshQuickSight"
    },

    "RefreshQuickSight": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:961341524729:function:quicksight-refresh",
      "Parameters": {
        "datasets.$": "$.quicksight_dataset_ids"
      },
      "Retry": [
        {
          "ErrorEquals": ["States.ALL"],
          "IntervalSeconds": 30,
          "MaxAttempts": 2,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyPartialSuccess",
          "ResultPath": "$.error"
        }
      ],
      "ResultPath": "$.refresh_results",
      "Next": "NotifySuccess"
    },

    "NotifySuccess": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:961341524729:weekly-reporting-notifications",
        "Subject": "✅ Weekly Import Pipeline — SUCCESS",
        "Message.$": "States.Format('Pipeline completed successfully. Clockify: {} entries, Jira: {} issues. KPIs written for week {}', $.extract_results[0].counts.entries, $.extract_results[1].counts.issues_fetched, $.transform_results.kpi_summary.week_start)"
      },
      "End": true
    },

    "NotifyPartialSuccess": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:961341524729:weekly-reporting-notifications",
        "Subject": "⚠️ Weekly Import Pipeline — PARTIAL SUCCESS (QuickSight refresh failed)",
        "Message.$": "States.Format('Data imported and transformed successfully but QuickSight SPICE refresh failed. Error: {}', $.error.Cause)"
      },
      "End": true
    },

    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:961341524729:weekly-reporting-notifications",
        "Subject": "🔴 Weekly Import Pipeline — FAILED",
        "Message.$": "States.Format('Pipeline failed. Check Step Functions execution for details. Error: {}', $.error.Cause)"
      },
      "End": true
    }
  }
}
```

### 9.3 EventBridge Rules

| Rule Name | Schedule | Payload |
|-----------|----------|---------|
| `weekly-ingestion-monday-9am` | `cron(0 14 ? * MON *)` (9 AM CT = 14:00 UTC) | `{"mode": "incremental", "weeks_back": 1}` |
| `daily-jira-refresh` | `cron(0 10 ? * MON-FRI *)` (10 AM UTC) | `{"mode": "incremental", "weeks_back": 0}` — triggers only Jira branch |
| `monthly-full-sync` | `cron(0 6 1 * ? *)` (1st of month, 6 AM UTC) | `{"mode": "full", "weeks_back": 12}` |

### 9.4 Execution Visibility

- **Console:** Step Functions visual workflow shows each step's status in real-time
- **CloudWatch Logs:** Each Lambda logs to its own log group (`/aws/lambda/clockify-import`, etc.)
- **X-Ray:** Enable tracing on the state machine for end-to-end latency breakdown
- **Metrics:** Custom CloudWatch metrics emitted by each Lambda (records_count, duration_seconds)

### 9.5 Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| Step Functions (4 transitions × 30 runs/month) | <$0.01 |
| Lambda: clockify-import (512 MB × 3 min × 30) | ~$0.60 |
| Lambda: jira-import (256 MB × 1 min × 50) | ~$0.10 |
| Lambda: transform (1024 MB × 3 min × 30) | ~$1.20 |
| Lambda: quicksight-refresh (128 MB × 30s × 30) | ~$0.02 |
| S3 storage (~500 MB/month growing) | ~$0.01 |
| SNS notifications (30/month) | ~$0.01 |
| **Total pipeline cost** | **~$2/month** |

---

## 10. Lambda: quicksight-refresh

### 10.1 Purpose

Triggers SPICE ingestion on all relevant QuickSight datasets after curated Parquet files are written.

### 10.2 Configuration

| Property | Value |
|----------|-------|
| Runtime | Python 3.12 |
| Architecture | arm64 |
| Memory | 128 MB |
| Timeout | 60 seconds |
| VPC | **No** |

### 10.3 Implementation

```python
"""quicksight-refresh Lambda handler."""
import json
import os
from datetime import datetime
import boto3

qs = boto3.client('quicksight')
ACCOUNT_ID = os.environ['AWS_ACCOUNT_ID']

# Consolidated dataset list (down from 47 to ~12 meaningful datasets)
DATASET_IDS = [
    'kpi-weekly-snapshots-prod',
    'time-entries-weekly-prod',
    'project-hours-summary-prod',
    'ps-projects-prod',
    'mc-activity-prod',
    'escalations-prod',
    'resource-utilization-prod',
    'compliance-prod',
    'productive-util-prod',
    'ps-at-risk-prod',
    'mc-at-risk-prod',
    'user-directory-prod',
]


def handler(event, context):
    dataset_ids = event.get('datasets', DATASET_IDS)
    results = []
    errors = []

    for ds_id in dataset_ids:
        try:
            ingestion_id = f"auto-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            qs.create_ingestion(
                DataSetId=ds_id,
                IngestionId=ingestion_id,
                AwsAccountId=ACCOUNT_ID,
                IngestionType='FULL_REFRESH'
            )
            results.append({"dataset": ds_id, "status": "TRIGGERED"})
        except qs.exceptions.ResourceExistsException:
            results.append({"dataset": ds_id, "status": "ALREADY_IN_PROGRESS"})
        except Exception as e:
            errors.append({"dataset": ds_id, "error": str(e)})

    return {
        "status": "SUCCESS" if not errors else "PARTIAL",
        "triggered": len(results),
        "errors": errors
    }
```

---

## 11. Glue Data Catalog + Athena Layer

### 11.1 Glue Database

```
Database: cdx_reporting
Location: s3://cdx-reporting-production/curated/
```

### 11.2 Glue Tables (created by Crawler or manually via CloudFormation)

| Table | Location | Partition Key | Format |
|-------|----------|---------------|--------|
| `time_entries` | `s3://cdx-reporting-production/curated/time_entries/` | `week_start` (string, YYYY-MM-DD) | Parquet |
| `users` | `s3://cdx-reporting-production/curated/users/` | `snapshot_date` (string) | Parquet |
| `projects` | `s3://cdx-reporting-production/curated/projects/` | `snapshot_date` (string) | Parquet |
| `jira_projects` | `s3://cdx-reporting-production/curated/jira_projects/` | `snapshot_date` (string) | Parquet |
| `kpi_snapshots` | `s3://cdx-reporting-production/curated/kpi_snapshots/` | `week_start` (string) | Parquet |

### 11.3 Athena Views (replicate key PostgreSQL views)

```sql
-- vw_weekly_time_summary (replaces PostgreSQL view)
CREATE OR REPLACE VIEW cdx_reporting.vw_weekly_time_summary AS
SELECT
    week_start,
    practice_alignment,
    location,
    pod_assignment,
    COUNT(DISTINCT clockify_user_id) AS resource_count,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours
FROM cdx_reporting.time_entries
GROUP BY week_start, practice_alignment, location, pod_assignment;

-- vw_resource_utilization
CREATE OR REPLACE VIEW cdx_reporting.vw_resource_utilization AS
SELECT
    t.week_start,
    t.clockify_user_id,
    u.name,
    u.practice_alignment,
    u.pod_assignment,
    u.location,
    u.daily_capacity_hours * 5 AS weekly_capacity,
    SUM(t.duration_hours) AS actual_hours,
    ROUND(SUM(t.duration_hours) / (u.daily_capacity_hours * 5) * 100, 1) AS utilization_pct
FROM cdx_reporting.time_entries t
JOIN cdx_reporting.users u ON t.clockify_user_id = u.clockify_user_id
WHERE u.snapshot_date = (SELECT MAX(snapshot_date) FROM cdx_reporting.users)
GROUP BY t.week_start, t.clockify_user_id, u.name,
         u.practice_alignment, u.pod_assignment, u.location, u.daily_capacity_hours;

-- vw_project_health (Jira PS/MC)
CREATE OR REPLACE VIEW cdx_reporting.vw_project_health AS
SELECT
    jira_key,
    summary,
    status,
    project_key,
    project_type,
    project_manager,
    health_overall,
    health_budget,
    health_scope,
    health_schedule,
    escalation,
    planned_start,
    expected_completion,
    updated
FROM cdx_reporting.jira_projects
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM cdx_reporting.jira_projects);
```

### 11.4 Glue Crawler Configuration

```yaml
CrawlerName: cdx-reporting-curated-crawler
DatabaseName: cdx_reporting
Targets:
  S3Targets:
    - Path: s3://cdx-reporting-production/curated/
      Exclusions:
        - "athena-results/**"
Schedule: cron(30 14 ? * MON *)   # 30 min after pipeline runs
SchemaChangePolicy:
  UpdateBehavior: UPDATE_IN_DATABASE
  DeleteBehavior: LOG
```

### 11.5 QuickSight Data Source (Athena)

Replace the current PostgreSQL VPC data source with:

```yaml
DataSource:
  Type: ATHENA
  Name: cdx-reporting-athena
  DataSourceParameters:
    AthenaParameters:
      WorkGroup: primary
      RoleArn: arn:aws:iam::961341524729:role/quicksight-athena-access
```

**Benefits:**
- No VPC connection needed
- No security group to maintain
- No RDS instance for read path
- QuickSight reads directly from S3 via Athena (serverless)

---

## 12. Migration Plan

### Phase 1: Parallel Write (Week 1-2)

1. Deploy the new Lambdas and Step Functions state machine
2. Run the new pipeline in parallel with the existing monolithic Lambda
3. Both write to their respective destinations (S3 + RDS)
4. Validate: compare S3 Parquet output against RDS tables for data parity

### Phase 2: Athena Layer (Week 2-3)

1. Deploy Glue Crawler + tables
2. Create Athena views
3. Create new QuickSight datasets pointing to Athena
4. Build test dashboards using Athena datasets — validate against production dashboards

### Phase 3: QuickSight Cutover (Week 3-4)

1. Switch production QuickSight datasets from RDS to Athena
2. Validate all 3 dashboards render correctly
3. Switch EventBridge rules from old Lambda to new Step Functions

### Phase 4: Decommission (Week 4-5)

1. Disable old EventBridge rules
2. Remove VPC security group for QuickSight
3. Stop ECS Streamlit task (if fully replaced by admin API)
4. Keep RDS running for 2 weeks as safety net, then decommission
5. Delete old monolithic Lambda

---

## 13. CloudFormation Template Outline

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Weekly Reporting Ingestion Pipeline

Parameters:
  Environment:
    Type: String
    Default: production
  SecretName:
    Type: String
    Default: production/weekly-reporting/clockify

Resources:
  # ── S3 Bucket ──
  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub cdx-reporting-${Environment}
      VersioningConfiguration:
        Status: Enabled
      LifecycleConfiguration:
        Rules:
          - Id: RawToIA
            Prefix: raw/
            Status: Enabled
            Transitions:
              - TransitionInDays: 30
                StorageClass: STANDARD_IA
              - TransitionInDays: 90
                StorageClass: GLACIER
          - Id: AthenaCleanup
            Prefix: athena-results/
            Status: Enabled
            ExpirationInDays: 7
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  # ── Lambda Functions ──
  ClockifyImportFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: clockify-import
      Handler: handler.handler
      Runtime: python3.12
      Architectures: [arm64]
      MemorySize: 512
      Timeout: 300
      CodeUri: lambdas/clockify-import/
      Environment:
        Variables:
          DATA_BUCKET: !Ref DataBucket
          SECRET_NAME: !Ref SecretName
      Policies:
        - S3WritePolicy:
            BucketName: !Ref DataBucket
        - Statement:
            Effect: Allow
            Action: secretsmanager:GetSecretValue
            Resource: !Sub arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${SecretName}*

  JiraImportFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: jira-import
      Handler: handler.handler
      Runtime: python3.12
      Architectures: [arm64]
      MemorySize: 256
      Timeout: 180
      CodeUri: lambdas/jira-import/
      Environment:
        Variables:
          DATA_BUCKET: !Ref DataBucket
          SECRET_NAME: !Ref SecretName
      Policies:
        - S3WritePolicy:
            BucketName: !Ref DataBucket
        - Statement:
            Effect: Allow
            Action: secretsmanager:GetSecretValue
            Resource: !Sub arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${SecretName}*

  TransformFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: transform-and-snapshot
      Handler: handler.handler
      Runtime: python3.12
      Architectures: [arm64]
      MemorySize: 1024
      Timeout: 300
      CodeUri: lambdas/transform/
      Environment:
        Variables:
          DATA_BUCKET: !Ref DataBucket
          SECRET_NAME: !Ref SecretName
      Policies:
        - S3CrudPolicy:
            BucketName: !Ref DataBucket
        - Statement:
            Effect: Allow
            Action: secretsmanager:GetSecretValue
            Resource: !Sub arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${SecretName}*

  QuickSightRefreshFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: quicksight-refresh
      Handler: handler.handler
      Runtime: python3.12
      Architectures: [arm64]
      MemorySize: 128
      Timeout: 60
      CodeUri: lambdas/quicksight-refresh/
      Environment:
        Variables:
          AWS_ACCOUNT_ID: !Ref AWS::AccountId
      Policies:
        - Statement:
            Effect: Allow
            Action:
              - quicksight:CreateIngestion
              - quicksight:DescribeIngestion
            Resource: !Sub arn:aws:quicksight:${AWS::Region}:${AWS::AccountId}:dataset/*

  # ── Step Functions ──
  IngestionStateMachine:
    Type: AWS::Serverless::StateMachine
    Properties:
      Name: WeeklyIngestionPipeline
      DefinitionUri: statemachine/pipeline.asl.json
      DefinitionSubstitutions:
        ClockifyImportArn: !GetAtt ClockifyImportFunction.Arn
        JiraImportArn: !GetAtt JiraImportFunction.Arn
        TransformArn: !GetAtt TransformFunction.Arn
        QuickSightRefreshArn: !GetAtt QuickSightRefreshFunction.Arn
        NotificationTopicArn: !Ref NotificationTopic
      Policies:
        - LambdaInvokePolicy:
            FunctionName: !Ref ClockifyImportFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref JiraImportFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref TransformFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref QuickSightRefreshFunction
        - SNSPublishMessagePolicy:
            TopicName: !GetAtt NotificationTopic.TopicName
      Events:
        WeeklySchedule:
          Type: Schedule
          Properties:
            Schedule: cron(0 14 ? * MON *)
            Input: '{"mode": "incremental", "weeks_back": 1}'

  # ── SNS Topic ──
  NotificationTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: weekly-reporting-notifications

  # ── Glue ──
  GlueDatabase:
    Type: AWS::Glue::Database
    Properties:
      CatalogId: !Ref AWS::AccountId
      DatabaseInput:
        Name: cdx_reporting
        LocationUri: !Sub s3://${DataBucket}/curated/

  GlueCrawler:
    Type: AWS::Glue::Crawler
    Properties:
      Name: cdx-reporting-curated-crawler
      Role: !GetAtt GlueCrawlerRole.Arn
      DatabaseName: !Ref GlueDatabase
      Targets:
        S3Targets:
          - Path: !Sub s3://${DataBucket}/curated/
      Schedule:
        ScheduleExpression: cron(30 14 ? * MON *)
      SchemaChangePolicy:
        UpdateBehavior: UPDATE_IN_DATABASE
        DeleteBehavior: LOG

  GlueCrawlerRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: glue.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole
      Policies:
        - PolicyName: S3Access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:ListBucket
                Resource:
                  - !GetAtt DataBucket.Arn
                  - !Sub ${DataBucket.Arn}/*

Outputs:
  StateMachineArn:
    Value: !Ref IngestionStateMachine
  DataBucketName:
    Value: !Ref DataBucket
  GlueDatabaseName:
    Value: !Ref GlueDatabase
```

---

## 14. Testing Strategy

| Test | Method |
|------|--------|
| Unit: Clockify extraction pagination | Mock `requests`, verify all pages are fetched |
| Unit: Transform logic | Feed known JSON, assert Parquet schema matches |
| Unit: KPI computation | Feed known DataFrames, assert KPI values |
| Integration: S3 write | LocalStack or real bucket in staging |
| Integration: Step Functions | Deploy to staging, run full pipeline |
| Validation: Data parity | Compare S3/Athena output vs RDS views for 4 weeks |
| Load: Large history | Run with `weeks_back=52`, verify timeout not hit |

---

## 15. Rollback Plan

1. EventBridge rules for old Lambda remain **disabled but not deleted** for 30 days
2. Old monolithic Lambda remains deployed (just not triggered)
3. RDS database retained for 2 weeks after cutover
4. If pipeline fails: re-enable old EventBridge rules → instant rollback to prior system
5. S3 raw data is immutable — can always reprocess from any point in history

---

## 16. Success Criteria

- [ ] Pipeline runs Monday 9 AM CT → QuickSight dashboards updated by 9:30 AM CT
- [ ] Zero VPC dependencies for QuickSight read path
- [ ] Lambda cold start < 3 seconds (no 19 MB package)
- [ ] Total pipeline cost < $5/month (vs current ~$85)
- [ ] Full audit trail: every raw API response preserved in S3
- [ ] Any historical week can be reprocessed without re-calling external APIs
- [ ] Step Functions console shows execution status at a glance (vs digging through CloudWatch logs)
