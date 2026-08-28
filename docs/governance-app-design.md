# Agentic Service Delivery Governance App — Design & Prompt

## Overview

A QuickSight App (Amazon Quick) that tracks project governance adherence to the Agentic Service Delivery Methodology. The app captures completion status at each phase gate (purple boxes in the methodology diagram), provides role-based views, and stores data in a relational database accessible outside QuickSight.

**Deployment:** Quick-specific AWS account (separate from reporting account)
**Database:** Aurora Serverless v2 PostgreSQL (accessible via Data API or VPC peering for external consumers)

---

## 1. Methodology Structure (from Diagram)

### Phases

| Phase | Name | Description |
|-------|------|-------------|
| 0 | Internal Preparation | Pre-engagement setup, team assembly, internal alignment |
| 1 | Discover & Align | Customer discovery, requirements gathering, SOW alignment |
| 2 | Design And Review | Architecture, SRS, security gates, spec creation |
| 3 | Build and Implement | Sprint execution, code review, testing, deployment |
| 4 | Launch and Enable | Go-live, handoff, enablement, support transition |

### Swim Lanes (Personas/Roles)

| Lane | Role | Responsibility |
|------|------|---------------|
| 1 | Sales / BD | Opportunity qualification, handoff to delivery |
| 2 | Account Management | Customer relationship, commercial alignment, escalations |
| 3 | Delivery Practice | Technical delivery, architecture, implementation |
| 4 | Client / Customer | Requirements input, approvals, UAT |
| 5 | Customer CTO / TA | Technical authority, architecture sign-off |

### Governance Gates (Purple Boxes)

Each purple box represents a checkpoint where completion must be captured. These are the governance enforcement points.

**Phase 0 — Internal Preparation:**
- Team assignment confirmed
- Internal kickoff complete
- Tooling & access provisioned
- Engagement brief reviewed

**Phase 1 — Discover & Align:**
- Discovery sessions complete
- Requirements documented (SRS)
- SOW/scope alignment confirmed
- Stakeholder map finalized
- Risk register initialized

**Phase 2 — Design And Review:**
- Architecture docs complete
- Security Gate 1 passed
- Data model approved
- Security Gate 2 (Well-Architected) passed
- Cost estimate approved
- Sprint plan approved

**Phase 3 — Build and Implement:**
- Sprint spec reviews complete (per sprint)
- Code reviews passed (per sprint)
- Testing gates passed (per sprint)
- Security review passed
- Deployment validation complete

**Phase 4 — Launch and Enable:**
- UAT sign-off
- Production deployment complete
- Knowledge transfer delivered
- Support handoff complete
- Post-launch review conducted

---

## 2. Database Schema

### Core Tables

```sql
-- Projects being tracked
CREATE TABLE projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name VARCHAR(255) NOT NULL,
    project_code VARCHAR(50) UNIQUE NOT NULL,  -- e.g., Jira project key
    client_name VARCHAR(255) NOT NULL,
    current_phase INTEGER DEFAULT 0 CHECK (current_phase BETWEEN 0 AND 4),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'on_hold', 'completed', 'cancelled')),
    start_date DATE,
    target_end_date DATE,
    actual_end_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Configurable phases (admin can modify names, descriptions, ordering)
CREATE TABLE phases (
    phase_id SERIAL PRIMARY KEY,
    phase_number INTEGER NOT NULL UNIQUE,
    phase_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Configurable governance gates (purple boxes) per phase
CREATE TABLE gates (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phase_id INTEGER REFERENCES phases(phase_id),
    gate_name VARCHAR(255) NOT NULL,
    description TEXT,
    responsible_role VARCHAR(100),  -- which role is responsible
    is_required BOOLEAN DEFAULT TRUE,  -- mandatory vs optional gate
    sort_order INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Gate completion records (the governance tracking)
CREATE TABLE gate_completions (
    completion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id),
    gate_id UUID REFERENCES gates(gate_id),
    status VARCHAR(20) DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed', 'skipped', 'blocked')),
    completed_by UUID REFERENCES team_members(member_id),
    completed_at TIMESTAMP,
    evidence_url TEXT,  -- link to artifact (Confluence, S3, etc.)
    notes TEXT,
    skip_reason TEXT,  -- required if status = 'skipped'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(project_id, gate_id)
);

-- Team members (synced from Jira roles)
CREATE TABLE team_members (
    member_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    role VARCHAR(100) NOT NULL,  -- matches Jira roles
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Configurable roles (admin-managed, mirrors Jira project roles)
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(100) UNIQUE NOT NULL,
    role_category VARCHAR(50) NOT NULL,  -- 'sales', 'account_mgmt', 'delivery', 'client', 'leadership'
    can_complete_gates BOOLEAN DEFAULT TRUE,
    can_skip_gates BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Project team assignments (who is on which project, in what role)
CREATE TABLE project_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id),
    member_id UUID REFERENCES team_members(member_id),
    role_id INTEGER REFERENCES roles(role_id),
    assigned_date DATE DEFAULT CURRENT_DATE,
    removed_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(project_id, member_id, role_id)
);

-- Audit log for all governance actions
CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id),
    actor_id UUID REFERENCES team_members(member_id),
    action VARCHAR(50) NOT NULL,  -- 'gate_completed', 'gate_skipped', 'phase_advanced', 'project_created'
    entity_type VARCHAR(50),  -- 'gate_completion', 'project', 'assignment'
    entity_id UUID,
    old_value JSONB,
    new_value JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Admin configuration (key-value for app settings)
CREATE TABLE app_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value JSONB NOT NULL,
    description TEXT,
    updated_by UUID REFERENCES team_members(member_id),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Phase transition rules (which gates must be complete before advancing)
CREATE TABLE phase_transition_rules (
    rule_id SERIAL PRIMARY KEY,
    from_phase INTEGER REFERENCES phases(phase_id),
    to_phase INTEGER REFERENCES phases(phase_id),
    required_gate_ids UUID[],  -- array of gate_ids that must be 'completed'
    allow_skipped BOOLEAN DEFAULT FALSE,  -- can skipped gates satisfy the rule?
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Views for QuickSight Dashboards

```sql
-- Project governance health overview
CREATE VIEW vw_project_governance_health AS
SELECT 
    p.project_id,
    p.project_name,
    p.client_name,
    p.current_phase,
    ph.phase_name AS current_phase_name,
    p.status,
    COUNT(g.gate_id) AS total_gates,
    COUNT(gc.completion_id) FILTER (WHERE gc.status = 'completed') AS completed_gates,
    COUNT(gc.completion_id) FILTER (WHERE gc.status = 'skipped') AS skipped_gates,
    COUNT(gc.completion_id) FILTER (WHERE gc.status = 'blocked') AS blocked_gates,
    ROUND(
        COUNT(gc.completion_id) FILTER (WHERE gc.status = 'completed')::NUMERIC / 
        NULLIF(COUNT(g.gate_id), 0) * 100, 1
    ) AS completion_percentage
FROM projects p
JOIN phases ph ON ph.phase_number = p.current_phase
CROSS JOIN gates g
LEFT JOIN gate_completions gc ON gc.project_id = p.project_id AND gc.gate_id = g.gate_id
WHERE p.status = 'active' AND g.is_active = TRUE
GROUP BY p.project_id, p.project_name, p.client_name, p.current_phase, ph.phase_name, p.status;

-- Per-phase gate status for a project
CREATE VIEW vw_phase_gate_status AS
SELECT
    p.project_id,
    p.project_name,
    ph.phase_number,
    ph.phase_name,
    g.gate_id,
    g.gate_name,
    g.responsible_role,
    g.is_required,
    COALESCE(gc.status, 'not_started') AS gate_status,
    gc.completed_by,
    tm.display_name AS completed_by_name,
    gc.completed_at,
    gc.evidence_url,
    gc.notes
FROM projects p
CROSS JOIN phases ph
JOIN gates g ON g.phase_id = ph.phase_id AND g.is_active = TRUE
LEFT JOIN gate_completions gc ON gc.project_id = p.project_id AND gc.gate_id = g.gate_id
LEFT JOIN team_members tm ON tm.member_id = gc.completed_by
WHERE ph.is_active = TRUE
ORDER BY p.project_name, ph.sort_order, g.sort_order;

-- Team workload across projects
CREATE VIEW vw_team_workload AS
SELECT
    tm.member_id,
    tm.display_name,
    tm.role,
    COUNT(DISTINCT pa.project_id) AS active_projects,
    COUNT(gc.completion_id) FILTER (WHERE gc.status = 'completed') AS gates_completed_total,
    COUNT(gc.completion_id) FILTER (WHERE gc.status = 'completed' AND gc.completed_at > NOW() - INTERVAL '7 days') AS gates_completed_this_week
FROM team_members tm
LEFT JOIN project_assignments pa ON pa.member_id = tm.member_id AND pa.is_active = TRUE
LEFT JOIN gate_completions gc ON gc.completed_by = tm.member_id
WHERE tm.is_active = TRUE
GROUP BY tm.member_id, tm.display_name, tm.role;
```

---

## 3. Admin Functionality

### Configurable Elements

| Element | What Admin Can Do |
|---------|-------------------|
| Phases | Add/rename/reorder/deactivate phases |
| Gates | Add/rename/reorder gates within phases; mark as required/optional |
| Roles | Add/modify roles; control gate completion permissions |
| Transition Rules | Define which gates must pass before phase advancement |
| Team Members | Add/deactivate; assign roles |
| App Settings | Configure notification rules, SLA thresholds, display preferences |

### Admin Screens

1. **Methodology Configuration** — drag-and-drop phase/gate editor
2. **Role Management** — CRUD roles, map to Jira roles
3. **Transition Rules** — define phase advancement criteria
4. **Team Directory** — manage members, bulk import from Jira
5. **Audit Log Viewer** — full history of governance actions

---

## 4. Integration Points

| System | Direction | What |
|--------|-----------|------|
| Jira | Import | Project codes, team roles, sprint data |
| QuickSight Dashboards | Read (SQL) | Governance health metrics, compliance views |
| Kiro Orchestrator | Read/Write | Auto-complete gates when orchestrator passes phase gates |
| Slack/Teams | Push | Notifications when gates are completed or blocked |

---

## 5. Amazon Quick Apps Prompt

Use this prompt when creating the application in the Quick Apps builder:

---

### PROMPT FOR QUICK APPS:

```
Build a Project Governance Tracker application for managing service delivery methodology compliance.

PURPOSE:
Track how well delivery teams follow our 5-phase Agentic Service Delivery Methodology. Each phase has governance checkpoints (gates) that must be completed before advancing. The app provides visibility into which gates are done, blocked, or skipped across all active projects.

DATA SOURCE:
Connect to our Aurora PostgreSQL database (I'll provide connection details). The database has these main tables: projects, phases, gates, gate_completions, team_members, roles, project_assignments, audit_log.

MAIN VIEWS:

1. PORTFOLIO DASHBOARD (home page):
   - Card grid showing all active projects
   - Each card shows: project name, client, current phase, completion % (progress bar), days since last gate completed
   - Color coding: Green (on track), Yellow (gate overdue >3 days), Red (gate blocked)
   - Filter by: phase, client, team member, status

2. PROJECT DETAIL VIEW (click into a project):
   - Horizontal phase timeline (Phase 0 → 4) with current phase highlighted
   - Gate checklist for current phase showing: gate name, responsible role, status (checkbox), completed by, date, evidence link
   - Ability to mark gates as complete (with notes and evidence URL)
   - Ability to mark gates as skipped (requires reason)
   - History of all gate completions for this project

3. TEAM VIEW:
   - Table of all team members with columns: name, role, active projects count, gates completed this week, gates completed total
   - Click a member to see their project assignments and gate activity

4. PHASE ADVANCEMENT:
   - When all required gates in current phase are complete, show "Advance to Phase X" button
   - Validate transition rules before allowing advancement
   - Log the phase transition in audit log

5. ADMIN PANEL (restricted to admin role):
   - Manage phases: add, rename, reorder, deactivate
   - Manage gates: add gates to phases, set as required/optional, assign responsible role
   - Manage roles: create roles, set permissions (can complete, can skip, is admin)
   - Manage transition rules: which gates must pass before phase advancement
   - View audit log: all governance actions with filters

ROLES & PERMISSIONS:
- Admin: full access, can configure methodology, manage team
- Delivery Practice: can complete/skip gates for their assigned projects
- Account Management: can view all projects, complete account-related gates
- Sales/BD: can view projects, complete sales handoff gates (Phase 0-1 only)
- Client: read-only view of their project's governance status
- Leadership/CTO: read-only portfolio view with drill-down

BUSINESS RULES:
- A gate cannot be marked complete without the person being assigned to the project in the responsible role
- Skipping a required gate requires a reason and is flagged in reporting
- Phase cannot advance until all required gates are complete (or explicitly skipped with reason)
- All actions are audit-logged with timestamp, actor, and before/after state
- Evidence URLs are encouraged but not mandatory for gate completion

VISUAL DESIGN:
- Clean, professional dashboard style
- Phase colors matching our methodology: Phase 0 (purple), Phase 1 (orange), Phase 2 (blue), Phase 3 (green), Phase 4 (teal)
- Progress bars for gate completion percentage
- Red/Yellow/Green status indicators
```

---

## 6. Database Access from External Applications

Since this runs in a Quick-specific account, external access options:

| Method | Use Case | Setup |
|--------|----------|-------|
| RDS Data API | Lambda functions, Kiro orchestrator | Enable on Aurora cluster, IAM auth |
| VPC Peering | Reporting account QuickSight dashboards | Peer VPCs between accounts |
| Cross-account IAM | Other AWS accounts needing read access | AssumeRole with external ID |
| API Gateway + Lambda | REST API for any consumer | Thin Lambda over Data API |

**Recommended:** Enable RDS Data API + expose a lightweight API Gateway for external consumers. This keeps the database private while providing controlled access.

---

## 7. Seed Data

### Default Phases
```sql
INSERT INTO phases (phase_number, phase_name, description, sort_order) VALUES
(0, 'Internal Preparation', 'Pre-engagement setup, team assembly, internal alignment', 0),
(1, 'Discover & Align', 'Customer discovery, requirements gathering, SOW alignment', 1),
(2, 'Design And Review', 'Architecture, SRS, security gates, spec creation', 2),
(3, 'Build and Implement', 'Sprint execution, code review, testing, deployment', 3),
(4, 'Launch and Enable', 'Go-live, handoff, enablement, support transition', 4);
```

### Default Roles (matching Jira project roles)
```sql
INSERT INTO roles (role_name, role_category, can_complete_gates, can_skip_gates, is_admin) VALUES
('Solutions Architect', 'delivery', TRUE, TRUE, FALSE),
('Delivery Lead', 'delivery', TRUE, TRUE, FALSE),
('Technical PM', 'delivery', TRUE, FALSE, FALSE),
('Backend Developer', 'delivery', TRUE, FALSE, FALSE),
('Frontend Developer', 'delivery', TRUE, FALSE, FALSE),
('DevOps Engineer', 'delivery', TRUE, FALSE, FALSE),
('QA Engineer', 'delivery', TRUE, FALSE, FALSE),
('Account Manager', 'account_mgmt', TRUE, FALSE, FALSE),
('Sales Executive', 'sales', TRUE, FALSE, FALSE),
('Practice Director', 'leadership', TRUE, TRUE, TRUE),
('CTO', 'leadership', TRUE, TRUE, TRUE),
('Client Stakeholder', 'client', FALSE, FALSE, FALSE);
```

---

## 8. Next Steps

1. [ ] Upload higher-res diagram or share Miro access so I can map exact purple box labels
2. [ ] Confirm Jira roles match the seed data above
3. [ ] Confirm Aurora PostgreSQL as database choice
4. [ ] Decide: new Aurora instance in Quick account, or cross-account access to existing?
5. [ ] Set up Aurora instance in Quick account with Data API enabled
6. [ ] Run schema creation SQL
7. [ ] Create the Quick App using the prompt above
8. [ ] Configure admin settings (phases, gates, roles)
9. [ ] Integrate with Jira for team sync
