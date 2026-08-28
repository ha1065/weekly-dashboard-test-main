"""
Clockify bulk-update integration.

Accepts the native Clockify member/project export files (or our own
generated templates) and updates existing custom fields via the API.

Prohibited: creating/deleting users or projects, modifying time entries.
"""

import io
import time
import requests
import pandas as pd
from typing import Dict, List, Tuple, Optional

from src.database.config import settings


# ---------------------------------------------------------------------------
# Column mappings — Clockify export column name → canonical name used here
# ---------------------------------------------------------------------------

# Members export columns that we can write back
MEMBER_WRITABLE = {
    "Practice Alignment":      "Practice Alignment",
    "Skill Area":               "Skill Area",
    "POD Assignment":           "POD Assignment",
    "Cloudelligent Title":      "Cloudelligent Title",
    "Location":                 "Location",
    "Employment Designation":   "Employment Designation",
    "Time Submission":          "Time Submission",
    "Level":                    "Level",
    "Daily work capacity (h)":  "Daily work capacity (h)",
}

# Members export columns used only for matching (never written)
MEMBER_MATCH_COLS = {"Name", "Email"}

# Members export columns that are read-only (informational, never written)
MEMBER_READONLY = {
    "Billable Rate (USD)", "Cost Rate (USD)", "Role", "Projects",
    "Team members", "Group", "Status", "Week start", "Working days",
    "Assigned team manager",
}

# Projects export columns used for matching
PROJECT_MATCH_COLS = {"Project", "Client"}

# Projects export columns that are read-only
PROJECT_READONLY = {
    "Task", "Tracked (h)", "Estimated (h)", "Remaining (h)", "Overage (h)",
    "Tracked (USD)", "Estimated (USD)", "Remaining (USD)", "Overage (USD)",
    "Progress(%)", "Recurring estimate", "Billable (h)", "Non-billable (h)",
    "Billable Rate (USD)", "Amount (USD)", "Cost Rate (USD)", "Expenses (USD)",
    "Billable expenses (USD)", "Non-billable expenses (USD)",
    "Additional fields", "Project members", "Project manager", "Note",
}

# Project columns we CAN update (mapped to Clockify API fields)
PROJECT_WRITABLE = {
    "Status":      "archived",    # Active → False, Archived → True
    "Visibility":  "isPublic",    # Public → True, Private → False
    "Billability": "billable",    # Yes → True, No → False
    # Custom fields are handled separately — see custom field columns below
}


# ---------------------------------------------------------------------------
# Clockify API helpers
# ---------------------------------------------------------------------------

_BASE = "https://api.clockify.me/api/v1"


def _headers() -> Dict:
    return {"X-Api-Key": settings.clockify_api_key, "Content-Type": "application/json"}


def _get(endpoint: str, params: dict = None) -> dict | list:
    url = f"{_BASE}{endpoint}"
    resp = requests.get(url, headers=_headers(), params=params or {})
    resp.raise_for_status()
    return resp.json()


def _put(endpoint: str, payload: dict) -> dict:
    url = f"{_BASE}{endpoint}"
    resp = requests.put(url, headers=_headers(), json=payload)
    resp.raise_for_status()
    return resp.json()


def _patch(endpoint: str, payload: dict) -> dict:
    url = f"{_BASE}{endpoint}"
    resp = requests.patch(url, headers=_headers(), json=payload)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Catalogue fetchers
# ---------------------------------------------------------------------------

def _fetch_workspace_users() -> List[Dict]:
    ws = settings.clockify_workspace_id
    users = []
    for status in ("ACTIVE", "INACTIVE"):
        page = 1
        while True:
            batch = _get(f"/workspaces/{ws}/users",
                         {"status": status, "page": page, "page-size": 100})
            if not batch:
                break
            users.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    return users


def _fetch_workspace_projects(include_archived: bool = False) -> List[Dict]:
    ws = settings.clockify_workspace_id
    projects = []
    for archived in ([False, True] if include_archived else [False]):
        page = 1
        while True:
            batch = _get(f"/workspaces/{ws}/projects",
                         {"hydrated": "true", "archived": str(archived).lower(), "page": page, "page-size": 100})
            if not batch:
                break
            projects.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    return projects


def _fetch_user_custom_field_defs() -> List[Dict]:
    ws = settings.clockify_workspace_id
    try:
        return _get(f"/workspaces/{ws}/custom-fields/users")
    except Exception:
        return []


def _fetch_project_custom_field_defs() -> List[Dict]:
    ws = settings.clockify_workspace_id
    try:
        return _get(f"/workspaces/{ws}/custom-fields/projects")
    except Exception:
        return []


def _fetch_member_profile(user_id: str) -> Dict:
    ws = settings.clockify_workspace_id
    return _get(f"/workspaces/{ws}/member-profile/{user_id}")


# ---------------------------------------------------------------------------
# File parser
# ---------------------------------------------------------------------------

def parse_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Parse uploaded CSV or Excel into a DataFrame, preserving all columns."""
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes), dtype=str).fillna("")
    return pd.read_excel(io.BytesIO(file_bytes), dtype=str).fillna("")


def detect_file_type(df: pd.DataFrame) -> Optional[str]:
    """Detect whether uploaded file is a members or projects export."""
    cols = set(df.columns)
    if "Email" in cols and "Name" in cols and "Practice Alignment" in cols:
        return "members"
    if "Project" in cols and "Client" in cols:
        return "projects"
    return None


# ---------------------------------------------------------------------------
# Template generators (for project custom fields — not in native export)
# ---------------------------------------------------------------------------

def build_project_template(include_archived: bool = False) -> Tuple[pd.DataFrame, List[str]]:
    """
    Generate a template with project custom field values (not in native export).
    Returns (df, warnings).
    Columns: Project, Client, Billable, Archived, + one column per project custom field.
    """
    warnings = []
    projects = _fetch_workspace_projects(include_archived=include_archived)

    # Build client ID → name map
    ws = settings.clockify_workspace_id
    try:
        clients_raw = _get(f"/workspaces/{ws}/clients", {"page-size": 500})
        client_map = {c["id"]: c["name"] for c in (clients_raw or [])}
    except Exception:
        client_map = {}

    # Discover all custom field names from the project data itself (preserves insertion order)
    seen_cf = set()
    cf_names = []
    for p in projects:
        for cf in p.get("customFields", []):
            name = (cf.get("customField") or {}).get("name") or cf.get("name", "")
            if name and name not in seen_cf:
                seen_cf.add(name)
                cf_names.append(name)

    rows = []
    for p in projects:
        client_name = client_map.get(p.get("clientId", ""), "")
        row = {
            "Project":  p.get("name", ""),
            "Client":   client_name,
            "Billable": "Yes" if p.get("billable") else "No",
            "Archived": "Yes" if p.get("archived") else "No",
        }
        for cf in p.get("customFields", []):
            name = (cf.get("customField") or {}).get("name") or cf.get("name", "")
            val = cf.get("value", "")
            if isinstance(val, bool):
                val = "Yes" if val else "No"
            elif val and isinstance(val, str):
                val = val.strip("{}\"\\")
            row[name] = val
        # Ensure all cf columns exist even if project has no value for them
        for name in cf_names:
            row.setdefault(name, "")
        rows.append(row)

    cols = ["Project", "Client", "Billable", "Archived"] + cf_names
    df = pd.DataFrame(rows, columns=cols).sort_values(["Client", "Project"])
    return df, warnings


def build_member_export() -> Tuple[pd.DataFrame, List[str]]:
    """
    Generate a full member export with user custom field values from Clockify.
    Fetches member profiles to retrieve custom field values (not in the users list).
    Returns (df, warnings).
    Columns: Name, Email, Status, + one column per user custom field.
    """
    warnings = []
    users = _fetch_workspace_users()
    cf_defs = _fetch_user_custom_field_defs()
    cf_names = [cf.get("name", cf["id"]) for cf in cf_defs]

    rows = []
    for u in users:
        user_id = u.get("id", "")
        name = u.get("name", "")
        email = (u.get("email") or "").strip()
        status = u.get("status", "")

        # Fetch profile to get custom field values
        try:
            profile = _fetch_member_profile(user_id)
            cf_values = {
                (cf.get("customField") or {}).get("name") or cf.get("name", ""): cf.get("value", "")
                for cf in profile.get("userCustomFieldValues", [])
            }
        except Exception as e:
            warnings.append(f"Could not fetch profile for {name}: {e}")
            cf_values = {}

        row = {"Name": name, "Email": email, "Status": status}
        for cf_name in cf_names:
            val = cf_values.get(cf_name, "")
            if val and isinstance(val, str):
                val = val.strip("{}\"\\")
            row[cf_name] = val
        rows.append(row)

    cols = ["Name", "Email", "Status"] + cf_names
    df = pd.DataFrame(rows, columns=cols).sort_values(["Name"])
    return df, warnings


# ---------------------------------------------------------------------------
# Member updater — accepts native Clockify export or generated template
# ---------------------------------------------------------------------------

def update_members(
    df: pd.DataFrame,
    dry_run: bool = True,
) -> Tuple[List[Dict], List[str]]:
    """
    Update user custom fields from a members file.

    Matching: Email (primary), falls back to Name if email missing.
    Writable columns: Practice Alignment, Skill Area, POD Assignment,
    Cloudelligent Title, Location, Employment Designation, Time Submission,
    Level, Daily work capacity (h).
    Read-only columns are silently skipped.
    """
    ws = settings.clockify_workspace_id
    cf_defs = _fetch_user_custom_field_defs()
    cf_by_name = {cf.get("name", cf["id"]): cf["id"] for cf in cf_defs}

    # Build lookup: email → user, name → user
    live_users = _fetch_workspace_users()
    by_email = {(u.get("email") or "").lower(): u for u in live_users if u.get("email")}
    by_name  = {u["name"].lower(): u for u in live_users}

    # Determine which columns in the file are writable custom fields
    # Use actual field definitions from Clockify (not the hardcoded set) so any
    # custom field present in the workspace is recognised, regardless of name.
    writable_cf_cols = [c for c in df.columns if c in cf_by_name]
    has_capacity = "Daily work capacity (h)" in df.columns

    results, errors = [], []

    for _, row in df.iterrows():
        email = str(row.get("Email", "")).strip().lower()
        name  = str(row.get("Name", "")).strip()

        # Match to live user
        user = by_email.get(email) or by_name.get(name.lower())
        if not user:
            errors.append(f"No Clockify user found for '{name}' ({email}) — skipped")
            continue

        uid = user["id"]
        changed_fields = []

        # Build custom field update list
        cf_payload = []
        for col in writable_cf_cols:
            cf_id = cf_by_name.get(col)
            if not cf_id:
                # Unknown custom field name — not in this workspace
                continue
            new_val = str(row.get(col, "")).strip()
            cf_payload.append({"customFieldId": cf_id, "value": new_val})
            changed_fields.append(f"{col}={new_val!r}")

        # Daily capacity
        cap_minutes = None
        if has_capacity:
            cap_str = str(row.get("Daily work capacity (h)", "")).strip()
            if cap_str and cap_str not in ("", "nan"):
                try:
                    cap_minutes = int(float(cap_str) * 60)
                    changed_fields.append(f"daily_capacity={cap_str}h")
                except ValueError:
                    errors.append(f"'{user['name']}': invalid capacity '{cap_str}' — skipped")

        if not cf_payload and cap_minutes is None:
            results.append({"name": user["name"], "email": user.get("email", ""),
                            "status": "skipped", "changed_fields": []})
            continue

        if not dry_run:
            try:
                if cf_payload or cap_minutes is not None:
                    profile = _fetch_member_profile(uid)
                    # Merge custom fields: keep existing values for fields not in upload
                    existing = {
                        (cf.get("customField") or {}).get("id") or cf.get("customFieldId", ""): cf
                        for cf in profile.get("userCustomFieldValues", [])
                    }
                    for item in cf_payload:
                        existing[item["customFieldId"]] = item

                    patch_body = {"userCustomFieldValues": list(existing.values())}

                    if cap_minutes is not None:
                        hours = cap_minutes // 60
                        mins  = cap_minutes % 60
                        patch_body["workCapacity"] = f"PT{hours}H{mins}M" if mins else f"PT{hours}H"

                    _patch(f"/workspaces/{ws}/member-profile/{uid}", patch_body)
                    time.sleep(0.15)

                results.append({"name": user["name"], "email": user.get("email", ""),
                                "status": "updated", "changed_fields": changed_fields})
            except requests.HTTPError as e:
                errors.append(
                    f"'{user['name']}': API error {e.response.status_code} — "
                    f"{e.response.text[:200]}"
                )
                results.append({"name": user["name"], "email": user.get("email", ""),
                                "status": "error", "changed_fields": []})
        else:
            results.append({"name": user["name"], "email": user.get("email", ""),
                            "status": "dry_run", "changed_fields": changed_fields})

    return results, errors


# ---------------------------------------------------------------------------
# Project updater — accepts native Clockify export or generated template
# ---------------------------------------------------------------------------

def update_projects(
    df: pd.DataFrame,
    dry_run: bool = True,
) -> Tuple[List[Dict], List[str]]:
    """
    Update project custom fields and basic settings.

    Matching: Project name + Client name.
    From native export: Status (Active/Archived), Visibility, Billability.
    From generated template: custom field columns (Pod Assignment, etc.).
    Read-only columns (hours, financials, members) are silently skipped.
    """
    ws = settings.clockify_workspace_id
    cf_defs = _fetch_project_custom_field_defs()
    cf_by_name = {cf.get("name", cf["id"]): cf["id"] for cf in cf_defs}

    live_projects = _fetch_workspace_projects()
    # Build lookup: (project_name_lower, client_name_lower) → project
    by_name_client = {
        (p["name"].lower(), (p.get("clientName") or "").lower()): p
        for p in live_projects
    }
    by_name_only = {p["name"].lower(): p for p in live_projects}

    # Determine writable columns present in this file
    # Standard writable: Status, Visibility, Billability
    std_writable = [c for c in ("Status", "Visibility", "Billability") if c in df.columns]
    # Custom field columns = anything not match, readonly, or standard
    known_cols = PROJECT_MATCH_COLS | PROJECT_READONLY | set(PROJECT_WRITABLE.keys())
    cf_cols = [c for c in df.columns if c not in known_cols and c not in PROJECT_MATCH_COLS]

    results, errors = [], []

    for _, row in df.iterrows():
        proj_name  = str(row.get("Project", "")).strip()
        client_name = str(row.get("Client", "")).strip()

        if not proj_name:
            errors.append("Row with empty Project name — skipped")
            continue

        # Match
        key = (proj_name.lower(), client_name.lower())
        proj = by_name_client.get(key) or by_name_only.get(proj_name.lower())
        if not proj:
            errors.append(f"No Clockify project found for '{proj_name}' / '{client_name}' — skipped")
            continue

        pid = proj["id"]
        changed_fields = []
        patch_body: Dict = {}

        # Standard field updates
        for col in std_writable:
            val = str(row.get(col, "")).strip()
            if not val or val == "nan":
                continue
            if col == "Status":
                archived = val.lower() == "archived"
                if archived != proj.get("archived", False):
                    patch_body["archived"] = archived
                    changed_fields.append(f"archived={archived}")
            elif col == "Visibility":
                is_public = val.lower() == "public"
                if is_public != proj.get("isPublic", False):
                    patch_body["isPublic"] = is_public
                    changed_fields.append(f"visibility={'Public' if is_public else 'Private'}")
            elif col == "Billability":
                billable = val.lower() in ("yes", "true", "1")
                if billable != proj.get("billable", True):
                    patch_body["billable"] = billable
                    changed_fields.append(f"billable={billable}")

        # Custom field updates
        cf_payload = []
        for col in cf_cols:
            cf_id = cf_by_name.get(col)
            if not cf_id:
                continue
            new_val = str(row.get(col, "")).strip()
            cf_payload.append({"customFieldId": cf_id, "value": new_val})
            changed_fields.append(f"{col}={new_val!r}")

        if cf_payload:
            patch_body["customFields"] = cf_payload

        if not changed_fields:
            results.append({"name": proj["name"], "client": client_name,
                            "status": "skipped", "changed_fields": []})
            continue

        if not dry_run:
            try:
                _patch(f"/workspaces/{ws}/projects/{pid}", patch_body)
                time.sleep(0.15)
                results.append({"name": proj["name"], "client": client_name,
                                "status": "updated", "changed_fields": changed_fields})
            except requests.HTTPError as e:
                errors.append(
                    f"'{proj['name']}': API error {e.response.status_code} — "
                    f"{e.response.text[:200]}"
                )
                results.append({"name": proj["name"], "client": client_name,
                                "status": "error", "changed_fields": []})
        else:
            results.append({"name": proj["name"], "client": client_name,
                            "status": "dry_run", "changed_fields": changed_fields})

    return results, errors
