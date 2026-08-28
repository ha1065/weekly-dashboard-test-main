"""Forecast import logic, extracted from app.py for testability."""

from datetime import datetime
import pandas as pd

from src.database.models import (
    ClockifyUser, PSResourceForecast, PSResourceForecastHistory, ImportLog
)


def import_forecasts_from_template(db, forecasts: list, template_week_dates: set = None):
    """Import forecasts from parsed template data with upsert.

    Uses savepoints so individual record failures don't roll back the entire
    transaction (which would undo the delete and lose all prior inserts).

    template_week_dates: ALL week dates from the template (including 0-hour weeks)
                         used to clear old records even when all entries are 0.
    Rows for users not found in Clockify are rejected (not imported).

    Returns tuple of (imported, updated, skipped_users) where skipped_users
    is a set of user names that were rejected because they weren't found in Clockify.
    """
    from sqlalchemy import func
    from sqlalchemy import text as _text

    imported = 0
    updated = 0
    errors = 0
    skipped_users = set()

    # Rollback any pending transaction first
    try:
        db.rollback()
    except Exception:
        pass

    # Create import log entry
    import_log = ImportLog(
        import_type='manual',
        import_category='forecasts',
        started_at=datetime.now(),
        status='in_progress'
    )
    db.add(import_log)
    db.flush()

    # Delete existing forecasts for weeks covered by this upload
    week_dates = template_week_dates or set()
    if not week_dates:
        for f in forecasts:
            if f.get('week_start_date'):
                week_dates.add(f['week_start_date'])

    if week_dates:
        snapshot_id = str(import_log.log_id)
        existing_count = db.query(PSResourceForecast).filter(
            PSResourceForecast.week_start_date.in_(list(week_dates))
        ).count()

        if existing_count > 0:
            existing_records = db.query(PSResourceForecast).filter(
                PSResourceForecast.week_start_date.in_(list(week_dates))
            ).all()
            archive_time = datetime.now()
            for ef in existing_records:
                db.add(PSResourceForecastHistory(
                    forecast_id=ef.forecast_id,
                    week_start_date=ef.week_start_date,
                    week_end_date=ef.week_end_date,
                    clockify_user_id=ef.clockify_user_id,
                    user_name=ef.user_name,
                    location=ef.location,
                    project_name=ef.project_name,
                    clockify_project_id=ef.clockify_project_id,
                    client_name=ef.client_name,
                    project_type=ef.project_type,
                    pm_name=ef.pm_name,
                    stage=ef.stage,
                    practice_area=ef.practice_area,
                    forecasted_hours=ef.forecasted_hours,
                    actual_hours=ef.actual_hours,
                    comments=ef.comments,
                    created_by=ef.created_by,
                    created_at=ef.created_at,
                    updated_at=ef.updated_at,
                    snapshot_id=snapshot_id,
                    archived_at=archive_time,
                ))
            db.flush()
            print(f"Archived {len(existing_records)} forecast records to history (snapshot {snapshot_id})")

        deleted = db.query(PSResourceForecast).filter(
            PSResourceForecast.week_start_date.in_(list(week_dates))
        ).delete(synchronize_session='fetch')
        db.flush()
        print(f"Cleared {deleted} existing forecast records for {len(week_dates)} weeks before re-import")
        print(f"Will insert {len(forecasts)} new forecast entries")

    for f in forecasts:
        try:
            nested = db.begin_nested()

            forecasted_hours_val = f.get('forecasted_hours', 0)
            if forecasted_hours_val is None or pd.isna(forecasted_hours_val):
                forecasted_hours_val = 0.0
            else:
                forecasted_hours_val = float(forecasted_hours_val)

            user = db.query(ClockifyUser).filter(
                func.lower(ClockifyUser.name) == func.lower(f['user_name'])
            ).first()

            if user:
                user_id = user.clockify_user_id
                location = user.location
                employment_designation = user.employment_designation
                practice_area = user.practice_alignment
            else:
                skipped_users.add(f['user_name'])
                nested.rollback()
                continue

            forecast = PSResourceForecast(
                week_start_date=f['week_start_date'],
                week_end_date=f['week_end_date'],
                clockify_user_id=user_id,
                user_name=f['user_name'],
                location=location,
                employment_designation=employment_designation,
                project_name=f.get('project_name'),
                client_name=f['client_name'],
                project_type=f.get('project_type'),
                pm_name=f.get('pm_name'),
                stage=f.get('stage'),
                practice_area=practice_area,
                forecasted_hours=forecasted_hours_val,
                actual_hours=float(f.get('actual_hours', 0) or 0),
                comments=f.get('comments')
            )
            db.add(forecast)
            nested.commit()
            imported += 1

        except Exception as e:
            errors += 1
            print(f"Error importing forecast for {f.get('user_name', 'unknown')}: {e}")
            try:
                nested.rollback()
            except Exception:
                pass
            continue

    try:
        if skipped_users:
            for u in sorted(skipped_users):
                db.execute(_text(
                    "INSERT INTO forecast_dropped_users (user_name, import_log_id) VALUES (:u, :lid)"
                ), {'u': u, 'lid': import_log.log_id})

        import_log.records_imported = imported
        import_log.records_updated = updated
        import_log.records_skipped = errors
        import_log.status = 'success' if errors == 0 else 'partial'
        import_log.error_message = (
            f"Rejected (user not in Clockify): {', '.join(sorted(skipped_users))}"
            if skipped_users else None
        )
        import_log.completed_at = datetime.now()
        db.commit()
        print(f"Forecast import committed: {imported} inserted, {updated} updated, {errors} errors")
    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to commit forecasts: {e}")

    return imported, updated, skipped_users
