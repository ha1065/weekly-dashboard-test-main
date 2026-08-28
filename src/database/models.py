"""Database models for weekly reporting application."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, Numeric
from sqlalchemy.sql import func
from src.database.config import Base


class ClockifyUser(Base):
    """User table."""
    __tablename__ = "clockify_users"

    user_id = Column(Integer, primary_key=True)
    clockify_user_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    daily_capacity = Column(Float, default=8.0)
    practice_alignment = Column(String(100))
    practice_area = Column(String(20))
    skill_area = Column(String(100))
    pod_assignment = Column(String(100))
    cloudelligent_title = Column(String(100))
    location = Column(String(50))
    employment_designation = Column(String(100))
    time_submission = Column(String(50))
    level = Column(String(100))
    status = Column(String(50), default='active')
    synced_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ClockifyProject(Base):
    """Project table."""
    __tablename__ = "clockify_projects"
    
    project_id = Column(Integer, primary_key=True)
    clockify_project_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    client_id = Column(String(50))
    client_name = Column(String(255))
    color = Column(String(50))
    billable = Column(Boolean)
    archived = Column(Boolean, default=False)
    due_date = Column(Date)
    project_type = Column(String(100))
    professional_services_type = Column(String(100))
    professional_services_phase = Column(String(100))
    pod_assignment = Column(String(100))
    is_overtime = Column(Boolean, default=False)
    is_presales = Column(Boolean, default=False)
    synced_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ClockifyTimeEntry(Base):
    """Time entry table."""
    __tablename__ = "clockify_detailed_time_entries"

    entry_id = Column(Integer, primary_key=True)
    clockify_entry_id = Column(String(50), unique=True, nullable=False)
    clockify_user_id = Column(String(50), nullable=False)
    user_name = Column(String(255), nullable=False)
    practice_alignment = Column(String(100))
    skill_area = Column(String(100))
    pod_assignment = Column(String(100))
    cloudelligent_title = Column(String(100))
    location = Column(String(50))
    employment_designation = Column(String(100))
    clockify_project_id = Column(String(50))
    project_name = Column(String(255))
    client_name = Column(String(255))
    task_name = Column(String(255))
    description = Column(Text)
    billable = Column(Boolean, default=True)
    duration_hours = Column(Float)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    entry_date = Column(Date)
    week_start = Column(Date)
    is_nb_productive = Column(Boolean, default=False)
    is_nb_non_productive = Column(Boolean, default=False)
    synced_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())


class UserSkill(Base):
    """User skills table."""
    __tablename__ = "user_skills"
    
    skill_id = Column(Integer, primary_key=True)
    clockify_user_id = Column(String(50), nullable=False)
    user_name = Column(String(255), nullable=False)
    skill_category = Column(String(100), nullable=False)
    skill_name = Column(String(255), nullable=False)
    proficiency_level = Column(String(50))
    years_experience = Column(Float)
    last_used_date = Column(Date)
    certification_name = Column(String(255))
    certification_date = Column(Date)
    certification_expiry = Column(Date)
    added_by = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PSResourceForecast(Base):
    """Forecast table for PS resource planning."""
    __tablename__ = "ps_resource_forecasts"

    forecast_id = Column(Integer, primary_key=True)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    clockify_user_id = Column(String(50))
    user_name = Column(String(255), nullable=False)
    location = Column(String(50))
    employment_designation = Column(String(100))
    project_name = Column(String(255))
    clockify_project_id = Column(String(50))
    client_name = Column(String(255), nullable=False)
    project_type = Column(String(100))  # Migration, AppDev, Infra, Connect, AI/ML
    pm_name = Column(String(255))  # Project Manager
    stage = Column(String(100))  # Closed, Launch and Enable, Discover and Align, Build and Implement
    practice_area = Column(String(100))
    forecasted_hours = Column(Float, nullable=False, default=0)
    actual_hours = Column(Float, default=0)
    comments = Column(Text)
    created_by = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PSResourceForecastHistory(Base):
    """Archive table for forecast history / versioning."""
    __tablename__ = "ps_resource_forecast_history"

    history_id = Column(Integer, primary_key=True)
    forecast_id = Column(Integer)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    clockify_user_id = Column(String(50))
    user_name = Column(String(255), nullable=False)
    location = Column(String(50))
    employment_designation = Column(String(100))
    project_name = Column(String(255))
    clockify_project_id = Column(String(50))
    client_name = Column(String(255), nullable=False)
    project_type = Column(String(100))
    pm_name = Column(String(255))
    stage = Column(String(100))
    practice_area = Column(String(100))
    forecasted_hours = Column(Float, nullable=False, default=0)
    actual_hours = Column(Float, default=0)
    comments = Column(Text)
    created_by = Column(String(255))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    snapshot_id = Column(String(50), nullable=False)
    archived_at = Column(DateTime, nullable=False, default=func.now())


class ImportLog(Base):
    """Track data import history."""
    __tablename__ = "import_logs"

    log_id = Column(Integer, primary_key=True)
    import_type = Column(String(50), nullable=False)  # 'full', 'incremental'
    import_category = Column(String(50), nullable=False)  # 'users', 'projects', 'time_entries'
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    records_imported = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    status = Column(String(50), default='success')  # 'success', 'failed', 'partial'
    error_message = Column(Text)
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)


# ============================================================
# Jira / Professional Services Integration Models
# ============================================================

class JiraProject(Base):
    """Jira project metadata."""
    __tablename__ = "jira_projects"

    id = Column(Integer, primary_key=True)
    jira_project_id = Column(String(50), unique=True, nullable=False)
    project_key = Column(String(50), nullable=False)
    project_name = Column(String(255))
    lead_name = Column(String(255))
    synced_at = Column(DateTime, default=func.now())


class PSProjectStatus(Base):
    """Professional Services Project Status (from Jira Service Desk)."""
    __tablename__ = "ps_project_status"

    id = Column(Integer, primary_key=True)
    jira_issue_id = Column(String(50), nullable=False)  # unique per (jira_issue_id, week_start)
    issue_key = Column(String(50), nullable=False)
    jira_project_key = Column(String(50), nullable=False)

    # Parsed from summary field
    client_name = Column(String(255))
    project_name = Column(String(255))
    summary = Column(String(500))

    # Standard Jira fields
    status = Column(String(100))  # Current stage
    status_category = Column(String(50))
    priority = Column(String(50))
    issue_type = Column(String(100))
    assignee_name = Column(String(255))
    created_date = Column(DateTime)
    updated_date = Column(DateTime)
    due_date = Column(Date)

    # PS / MC classification — set during ingestion based on issue_type rules
    category = Column(String(10))       # 'PS' or 'MC'

    # Project classification
    project_type = Column(String(100))  # Migration, AppDev, etc.

    # Team members
    project_manager = Column(String(255))
    solution_architect = Column(String(255))
    engineer = Column(String(255))
    account_executive = Column(String(255))
    csm = Column(String(255))  # Customer Success Manager

    # Health status fields (Red/Yellow/Green)
    current_health = Column(String(100))
    health_overall = Column(String(50))
    health_budget = Column(String(50))
    health_scope = Column(String(50))
    health_schedule = Column(String(50))
    schedule_score = Column(String(50))  # On Time/Late
    escalation = Column(Text)
    impact = Column(Text)
    risks_blockers = Column(Text)

    # Budget
    budget_hours = Column(Numeric(10, 2))

    # Date fields - Planning
    planned_start = Column(Date)
    planned_end = Column(Date)
    planned_kickoff = Column(Date)
    sow_signing_date = Column(Date)
    expected_completion = Column(Date)
    revised_completion = Column(Date)
    resource_assignment_date = Column(Date)

    # Date fields - Actual completion by phase
    actual_kickoff = Column(Date)
    actual_completion = Column(Date)
    internal_prep_completion = Column(Date)
    discover_align_completion = Column(Date)
    design_review_completion = Column(Date)
    build_implement_completion = Column(Date)
    launch_enable_completion = Column(Date)

    # Narrative fields
    project_summary = Column(Text)
    what_we_did = Column(Text)
    what_we_will_do_next = Column(Text)
    mitigation_plan = Column(Text)
    slippages = Column(Text)

    # Links
    sow_link = Column(Text)
    jira_board_link = Column(Text)

    # System date fields
    resolution_date = Column(DateTime(timezone=True))  # Jira system field: set when issue transitions to Done/Resolved

    # Metadata
    week_start = Column(Date)
    synced_at = Column(DateTime, default=func.now())

    # Manual exclusion flag — set to True to hide stale/artifact rows; survives re-imports
    is_excluded = Column(Boolean, default=False)


class AppUser(Base):
    """Streamlit application users for login authentication."""
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AIAnalysisPrompt(Base):
    """Configurable prompts for the AI project health analysis pipeline."""
    __tablename__ = "ai_analysis_prompts"

    id = Column(Integer, primary_key=True)
    category = Column(String(10), nullable=False)       # 'PS' or 'MC'
    sequence_order = Column(Integer, nullable=False)    # 1, 2, 3, 4 ...
    prompt_text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AIAnalysisByUser(Base):
    """Per-user AI analysis results: Jira estimate vs Clockify actuals."""
    __tablename__ = "ai_analysis_by_user"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False)
    category = Column(String(10), nullable=False)       # 'PS' or 'MC'
    project_name = Column(String(255))
    user_name = Column(String(255), nullable=False)
    role = Column(String(255))
    jira_issues = Column(Text)                          # comma-separated issue keys
    jira_estimate_hours = Column(Float)
    clockify_actual_hours = Column(Float)
    delta = Column(Float)
    verdict = Column(String(50))
    notes = Column(Text)
    analyzed_at = Column(DateTime, default=func.now())


class AIAnalysisByProject(Base):
    """Project-level rollup of AI analysis results."""
    __tablename__ = "ai_analysis_by_project"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False)
    category = Column(String(10), nullable=False)       # 'PS' or 'MC'
    project_name = Column(String(255), nullable=False)
    team_size = Column(Integer)
    total_jira_estimate_hours = Column(Float)
    total_clockify_hours = Column(Float)
    total_delta = Column(Float)
    verdict = Column(String(50))
    notes = Column(Text)
    analyzed_at = Column(DateTime, default=func.now())


class MCv2AuditByCustomer(Base):
    """MC V2 Audit: overall per-customer progress snapshot as of week_start."""
    __tablename__ = "mc_v2_audit_by_customer"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False)
    customer_name = Column(String(255), nullable=False)
    jira_project_key = Column(String(50))
    pod = Column(String(100))
    total_phases = Column(Integer)
    completed_phases = Column(Integer)
    overall_completion_pct = Column(Numeric(5, 1))
    executive_summary = Column(Text)
    analyzed_at = Column(DateTime, default=func.now())


class MCv2AuditByPhase(Base):
    """MC V2 Audit: per-phase breakdown for each customer as of week_start."""
    __tablename__ = "mc_v2_audit_by_phase"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False)
    customer_name = Column(String(255), nullable=False)
    jira_project_key = Column(String(50))
    phase_name = Column(String(255), nullable=False)
    phase_order = Column(Integer)
    total_items = Column(Integer)
    done_items = Column(Integer)
    in_progress_items = Column(Integer)
    todo_items = Column(Integer)
    completion_pct = Column(Numeric(5, 1))
    narrative = Column(Text)
    analyzed_at = Column(DateTime, default=func.now())


class AIForecastAnalysis(Base):
    """Per-user Bedrock AI analysis of forecast vs actual hours."""
    __tablename__ = "ai_forecast_analysis"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False)
    weeks_analyzed = Column(Integer, nullable=False)
    user_name = Column(String(255), nullable=False)
    location = Column(String(100))
    employment_designation = Column(String(100))
    total_forecasted_hours = Column(Numeric(8, 1))
    total_actual_hours = Column(Numeric(8, 1))
    variance_hours = Column(Numeric(8, 1))
    pct_achieved = Column(Numeric(6, 1))
    status = Column(String(50))
    notes = Column(Text)
    analyzed_at = Column(DateTime, default=func.now())


class AIForecastSummary(Base):
    """Week-level AI narrative summary of forecast vs actuals analysis."""
    __tablename__ = "ai_forecast_summary"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False)
    weeks_analyzed = Column(Integer, nullable=False)
    total_resources = Column(Integer)
    on_track_count = Column(Integer)
    over_count = Column(Integer)
    under_count = Column(Integer)
    critical_under_count = Column(Integer)
    no_actuals_count = Column(Integer)
    unforecasted_count = Column(Integer)
    key_observations = Column(Text)
    recommendations = Column(Text)
    analyzed_at = Column(DateTime, default=func.now())


class PSProjectMapping(Base):
    """Mapping between PS projects (Jira) and Clockify clients/projects for actual hours."""
    __tablename__ = "ps_project_mapping"

    id = Column(Integer, primary_key=True)
    ps_client_name = Column(String(255), nullable=False)
    ps_project_name = Column(String(255))
    clockify_client_name = Column(String(255), nullable=False)
    clockify_project_name = Column(String(255))
    category = Column(String(10))                    # 'PS' or 'MC' — which tab it was saved from
    pod_assignment = Column(String(100))             # MC pod (Alpha, Bravo, A2Z, SurePoint, …)
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


class MCPod(Base):
    """User-managed list of Managed Cloud pod names."""
    __tablename__ = "mc_pods"

    id = Column(Integer, primary_key=True)
    pod_name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


class ClockifyUploadLog(Base):
    """Audit log for Clockify Data Update uploads."""
    __tablename__ = "clockify_upload_logs"

    id = Column(Integer, primary_key=True)
    uploaded_at = Column(DateTime, default=func.now())
    uploaded_by = Column(String(255))           # app username
    file_name = Column(String(500))
    file_type = Column(String(50))              # 'Team Members' or 'Projects'
    records_total = Column(Integer)
    records_updated = Column(Integer)
    records_skipped = Column(Integer)
    records_failed = Column(Integer)
    detail = Column(Text)                       # JSON summary of changes


class Escalation(Base):
    """Escalations table for tracking customer issues."""
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True)
    client_name = Column(String(255))
    issue_summary = Column(String(500))
    priority = Column(String(50))               # High, Medium, Low
    status = Column(String(100))
    assignee = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    resolved_date = Column(Date)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())