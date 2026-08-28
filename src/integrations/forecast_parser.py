"""Parse weekly forecasting Excel templates."""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import re


def parse_week_start_date(value, year: int = None) -> datetime:
    """Parse a week start date from various formats.

    Handles:
    - Excel datetime objects
    - Date strings like "1/5/2026", "2026-01-05", "Jan 5, 2026"
    - Timestamp objects

    Returns datetime object or None if parsing fails.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if year is None:
        year = datetime.now().year

    # If it's already a datetime
    if isinstance(value, datetime):
        return value

    # If it's a pandas Timestamp
    if hasattr(value, 'to_pydatetime'):
        return value.to_pydatetime()

    # If it's a date object
    if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
        return datetime(value.year, value.month, value.day)

    # Try to parse as string
    value_str = str(value).strip()

    # Try pandas to_datetime which handles many formats
    try:
        parsed = pd.to_datetime(value_str)
        if pd.notna(parsed):
            return parsed.to_pydatetime()
    except:
        pass

    # Try common date formats explicitly
    date_formats = [
        '%Y-%m-%d',      # 2026-01-05
        '%m/%d/%Y',      # 01/05/2026
        '%m/%d/%y',      # 01/05/26
        '%d/%m/%Y',      # 05/01/2026
        '%B %d, %Y',     # January 5, 2026
        '%b %d, %Y',     # Jan 5, 2026
        '%d %B %Y',      # 5 January 2026
        '%d %b %Y',      # 5 Jan 2026
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue

    return None


def parse_week_date_range(week_str: str, year: int = None) -> Tuple[datetime, datetime]:
    """Parse week date range string like '16th-20th Dec' or '29th-2nd Jan'.

    Returns tuple of (week_start, week_end) as datetime objects.
    """
    if not week_str or pd.isna(week_str):
        return None, None

    if year is None:
        year = datetime.now().year

    # Clean up the string
    week_str = str(week_str).strip()

    # Common patterns:
    # "16th-20th Dec", "22-26th Dec", "29th-2nd Jan", "2ndfeb-6th feb"

    # Month name mapping
    month_map = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12
    }

    try:
        # Try to extract start and end parts
        # Pattern: "16th-20th Dec" or "29th-2nd Jan"
        parts = week_str.lower().replace('th', '').replace('st', '').replace('nd', '').replace('rd', '')

        # Find all numbers and month names
        numbers = re.findall(r'\d+', parts)
        months = re.findall(r'[a-z]+', parts)

        if len(numbers) >= 2:
            start_day = int(numbers[0])
            end_day = int(numbers[1])

            # Determine months
            if len(months) >= 2:
                # Two months mentioned (e.g., "29th Dec - 2nd Jan")
                start_month = month_map.get(months[0], 1)
                end_month = month_map.get(months[1], start_month)
            elif len(months) >= 1:
                # One month mentioned, both days in same month
                start_month = month_map.get(months[0], 1)
                end_month = start_month
            else:
                return None, None

            # Handle year rollover
            start_year = year
            end_year = year
            if start_month == 12 and end_month == 1:
                end_year = year + 1
            elif start_month > end_month:
                end_year = year + 1

            week_start = datetime(start_year, start_month, start_day)
            week_end = datetime(end_year, end_month, end_day)

            return week_start, week_end
    except Exception as e:
        print(f"Failed to parse week string '{week_str}': {e}")

    return None, None


def get_monday_of_week(date: datetime) -> datetime:
    """Get Monday of the week for a given date."""
    days_since_monday = date.weekday()
    monday = date - timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _find_header_row(df, max_scan: int = 10) -> int:
    """Find the header row by scanning for a row containing 'Plan'.

    Returns the row index, or 3 as a fallback for the original template layout.
    """
    for row_idx in range(min(max_scan, len(df))):
        row = df.iloc[row_idx]
        plan_count = sum(1 for val in row if pd.notna(val) and str(val).strip().lower() == 'plan')
        if plan_count >= 2:  # At least 2 'Plan' columns indicates the header row
            return row_idx
    return 3  # Fallback to original hardcoded position


def _find_week_dates_row(df, header_idx: int) -> int:
    """Find the row containing week dates (datetime values) above the header row."""
    for row_idx in range(header_idx):
        row = df.iloc[row_idx]
        datetime_count = sum(1 for val in row if isinstance(val, datetime) or
                            (hasattr(val, 'to_pydatetime') and pd.notna(val)))
        if datetime_count >= 2:
            return row_idx
    return 0  # Fallback


def _find_week_labels_row(df, header_idx: int, dates_row_idx: int) -> int:
    """Find the row containing week labels (Week1, Week2, etc.) between dates and header."""
    for row_idx in range(dates_row_idx + 1, header_idx):
        row = df.iloc[row_idx]
        week_count = sum(1 for val in row if pd.notna(val) and
                        str(val).strip().lower().startswith('week'))
        if week_count >= 2:
            return row_idx
    # If only one row between dates and header, or none found, use dates_row + 1
    return min(dates_row_idx + 1, header_idx - 1) if header_idx > dates_row_idx + 1 else dates_row_idx


def parse_forecast_template(file_path_or_buffer, sheet_name: str = None) -> List[Dict]:
    """Parse the weekly forecasting Excel template.

    Auto-detects the header row by scanning for 'Plan' columns.
    Supports templates with or without a spacer/totals row between
    week labels and headers.

    Returns list of forecast dictionaries ready for database insertion.
    """
    # Read all sheets if none specified
    xlsx = pd.ExcelFile(file_path_or_buffer)

    sheets_to_process = [sheet_name] if sheet_name else xlsx.sheet_names

    all_forecasts = []
    all_week_dates = set()  # Track ALL week dates from the template (including 0-hour weeks)

    for sheet in sheets_to_process:
        try:
            # Read raw data without headers
            df = pd.read_excel(xlsx, sheet_name=sheet, header=None)

            if df.empty or len(df) < 4:
                continue

            # Auto-detect row positions
            header_row_idx = _find_header_row(df)
            dates_row_idx = _find_week_dates_row(df, header_row_idx)
            labels_row_idx = _find_week_labels_row(df, header_row_idx, dates_row_idx)
            data_start_idx = header_row_idx + 1

            week_dates_row = df.iloc[dates_row_idx]
            week_labels_row = df.iloc[labels_row_idx]
            header_row = df.iloc[header_row_idx]

            # Find where the weekly data starts (look for "Plan" in header row)
            plan_columns = []
            for col_idx, val in enumerate(header_row):
                if str(val).strip().lower() == 'plan':
                    plan_columns.append(col_idx)

            # Map week dates to column indices
            week_columns = {}  # {col_idx: (week_start, week_end)}
            current_year = datetime.now().year

            # Match dates to plan columns: each date aligns with the nearest plan column
            # at or after its position (handles dates offset by one column from Plan headers)
            date_entries = []
            for col_idx, week_val in enumerate(week_dates_row):
                if pd.notna(week_val):
                    week_start = parse_week_start_date(week_val, current_year)
                    if not week_start:
                        ws, we = parse_week_date_range(str(week_val), current_year)
                        if ws:
                            week_start = ws
                    if week_start:
                        date_entries.append((col_idx, week_start))

            # Try direct column match first (date col == plan col)
            for col_idx, week_start in date_entries:
                if col_idx in plan_columns:
                    week_end = week_start + timedelta(days=6)
                    week_columns[col_idx] = (week_start, week_end)

            # If no direct matches, align dates to plan columns by position order
            if not week_columns and date_entries and plan_columns:
                # Sort both by column index and pair them up
                sorted_dates = sorted(date_entries, key=lambda x: x[0])
                sorted_plans = sorted(plan_columns)
                # Match each date to the plan column at the same position
                # (e.g., date at col 9 pairs with first plan col at col 8)
                for i, (_, week_start) in enumerate(sorted_dates):
                    if i < len(sorted_plans):
                        plan_col = sorted_plans[i]
                        week_end = week_start + timedelta(days=6)
                        week_columns[plan_col] = (week_start, week_end)

            # If we still couldn't parse week dates, try to infer from week labels
            if not week_columns:
                for col_idx, label in enumerate(week_labels_row):
                    label_str = str(label).strip().lower() if pd.notna(label) else ''
                    if label_str.startswith('week') and col_idx in plan_columns:
                        try:
                            week_num = int(re.search(r'\d+', label_str).group())
                            week_start = get_monday_of_week(datetime.now()) + timedelta(weeks=week_num - 1)
                            week_end = week_start + timedelta(days=6)
                            week_columns[col_idx] = (week_start.date(), week_end.date())
                        except:
                            pass

            # Collect ALL week dates from this sheet's template
            for col_idx, (ws, we) in week_columns.items():
                ws_date = ws.date() if isinstance(ws, datetime) else ws
                all_week_dates.add(ws_date)

            # Find column indices for metadata from the header row
            col_indices = {
                'client': None,
                'project': None,
                'comments': None,
                'type': None,
                'pm': None,
                'stage': None,
                'user': None
            }

            for col_idx, val in enumerate(header_row):
                val_str = str(val).strip().lower() if pd.notna(val) else ''
                if 'client' in val_str:
                    col_indices['client'] = col_idx
                elif 'project' in val_str:
                    col_indices['project'] = col_idx
                elif 'comment' in val_str:
                    col_indices['comments'] = col_idx
                elif val_str == 'type':
                    col_indices['type'] = col_idx
                elif val_str == 'pm':
                    col_indices['pm'] = col_idx
                elif 'stage' in val_str:
                    col_indices['stage'] = col_idx
                elif 'user' in val_str or 'resource' in val_str:
                    col_indices['user'] = col_idx

            # If 'Client' not labeled, infer: client is one column before 'Project'
            if col_indices['client'] is None and col_indices['project'] is not None:
                col_indices['client'] = col_indices['project'] - 1

            # Fallback: assume standard column positions
            if col_indices['client'] is None and col_indices['user'] is None:
                col_indices = {
                    'client': 1,
                    'project': 2,
                    'comments': 3,
                    'type': 4,
                    'pm': 5,
                    'stage': 6,
                    'user': 7
                }

            # Process data rows
            current_client = None
            current_project = None
            current_comments = None
            current_type = None
            current_pm = None
            current_stage = None

            for row_idx in range(data_start_idx, len(df)):
                row = df.iloc[row_idx]

                # Get metadata (with continuation from previous rows if empty)
                client = row.iloc[col_indices['client']] if col_indices['client'] is not None else None
                if pd.notna(client) and str(client).strip():
                    current_client = str(client).strip()
                    current_project = str(row.iloc[col_indices['project']]).strip() if col_indices['project'] is not None and pd.notna(row.iloc[col_indices['project']]) else current_client
                    current_comments = str(row.iloc[col_indices['comments']]).strip() if col_indices['comments'] is not None and pd.notna(row.iloc[col_indices['comments']]) else None
                    current_type = str(row.iloc[col_indices['type']]).strip() if col_indices['type'] is not None and pd.notna(row.iloc[col_indices['type']]) else None
                    current_pm = str(row.iloc[col_indices['pm']]).strip() if col_indices['pm'] is not None and pd.notna(row.iloc[col_indices['pm']]) else None
                    current_stage = str(row.iloc[col_indices['stage']]).strip() if col_indices['stage'] is not None and pd.notna(row.iloc[col_indices['stage']]) else None

                # Get user name
                user = row.iloc[col_indices['user']] if col_indices['user'] is not None else None
                if pd.isna(user) or not str(user).strip():
                    continue
                user_name = str(user).strip()

                # Skip if no client context
                if not current_client:
                    continue

                # Process each week column
                for col_idx, (week_start, week_end) in week_columns.items():
                    hours = row.iloc[col_idx]

                    # Skip if no hours or NaN
                    if pd.isna(hours):
                        continue

                    try:
                        hours_val = float(hours)
                        if hours_val <= 0:
                            continue
                    except (ValueError, TypeError):
                        continue

                    # Ensure dates are date objects
                    if isinstance(week_start, datetime):
                        week_start = week_start.date()
                    if isinstance(week_end, datetime):
                        week_end = week_end.date()

                    forecast = {
                        'week_start_date': week_start,
                        'week_end_date': week_end,
                        'user_name': user_name,
                        'client_name': current_client,
                        'project_name': current_project or current_client,  # Use project name if available, fallback to client
                        'project_type': current_type,
                        'pm_name': current_pm or sheet,  # Use sheet name as PM if not specified
                        'stage': current_stage,
                        'comments': current_comments,
                        'forecasted_hours': hours_val,
                        'actual_hours': 0.0
                    }

                    all_forecasts.append(forecast)

        except Exception as e:
            print(f"Error processing sheet '{sheet}': {e}")
            continue

    return all_forecasts, all_week_dates


def generate_forecast_template(
    users: List[Dict],
    projects: List[Dict],
    weeks_forward: int = 12,
    output_path: str = None
) -> pd.DataFrame:
    """Generate a forecast template Excel file matching the standard format.

    Args:
        users: List of user dicts with 'name' key
        projects: List of project dicts with 'name' and 'client_name' keys
        weeks_forward: Number of weeks to include
        output_path: Path to save the Excel file

    Returns:
        DataFrame with the template structure
    """
    from datetime import datetime, timedelta

    # Calculate week dates
    current_monday = get_monday_of_week(datetime.now())
    weeks = []
    for i in range(weeks_forward):
        week_start = current_monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        weeks.append({
            'start': week_start,
            'end': week_end,
            'label': f"Week{i+1}",
            'date_range': f"{week_start.strftime('%d')}-{week_end.strftime('%d %b')}"
        })

    # Build column structure
    columns = ['Client', 'Comments', 'Type', 'PM', 'Stage', 'User', 'Total Plan', 'Total Actual']

    for week in weeks:
        columns.append(f"{week['date_range']} Plan")
        columns.append(f"{week['date_range']} Actual")

    # Create empty DataFrame
    df = pd.DataFrame(columns=columns)

    # Add sample rows
    sample_data = []
    for project in projects[:5]:  # First 5 projects as examples
        for user in users[:3]:  # First 3 users per project
            row = {
                'Client': project.get('client_name', project.get('name', '')),
                'Comments': '',
                'Type': 'Migration',
                'PM': '',
                'Stage': 'Build and Implement',
                'User': user.get('name', ''),
                'Total Plan': 0,
                'Total Actual': 0
            }
            for week in weeks:
                row[f"{week['date_range']} Plan"] = 0
                row[f"{week['date_range']} Actual"] = 0
            sample_data.append(row)

    df = pd.DataFrame(sample_data)

    if output_path:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Forecast', index=False)

    return df
