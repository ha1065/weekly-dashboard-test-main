# Weekly Reporting - Cloudelligent

A comprehensive weekly reporting application that pulls data from Clockify and provides dashboards for QuickSight analytics.

## Features

- **Clockify Integration**: Automated data import from Clockify API
- **PostgreSQL Storage**: Structured data storage with optimized views
- **Incremental Imports**: Efficient data updates (only pull new data)
- **Streamlit Dashboard**: Interactive web UI for data management
- **QuickSight Ready**: Optimized views for AWS QuickSight reporting
- **Automated Scheduling**: Cron/EventBridge support for weekly automation
- **Import Tracking**: Complete audit trail of all data imports

## Architecture

```
Clockify API
     ↓
Import Service (Python)
     ↓
PostgreSQL Database
     ├─→ Base Tables (users, projects, time_entries)
     └─→ Reporting Views (10 optimized views)
          ↓
     AWS QuickSight (SPICE)
          ↓
     Dashboards & Reports
```

## Quick Start

### Production AWS Deployment (Recommended)

```bash
# One-command deployment to AWS
./cloudformation/deploy.sh
```

Deploys complete infrastructure in ~15-20 minutes:
- VPC with private/public subnets
- RDS PostgreSQL (encrypted)
- Lambda for automated imports
- EventBridge scheduling
- CloudWatch monitoring

**Cost**: ~$52-67/month

See [DEPLOYMENT_QUICKSTART.md](DEPLOYMENT_QUICKSTART.md) or [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)

---

### Local Development Setup

#### 1. Prerequisites

- Python 3.11+
- PostgreSQL database
- Clockify API key and workspace ID
- AWS account (for QuickSight)

### 2. Installation

```bash
# Clone repository
cd /Users/cdx/weekly-reporting

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env with your credentials
DATABASE_URL=postgresql://user:password@host:5432/database
CLOCKIFY_API_KEY=your_api_key
CLOCKIFY_WORKSPACE_ID=your_workspace_id
```

### 3. Initialize Database

```bash
# Create database schema
python src/database/init_db.py

# Create reporting views
python src/database/apply_views.py
```

### 4. Import Initial Data

```bash
# Option 1: Command line (1 year of data)
python -c "from src.integrations.import_clockify_data import run_full_import; run_full_import()"

# Option 2: Streamlit UI
streamlit run src/app.py
# Navigate to "Data Import" → "Initial Load (1 Year)" → "Run Import"
```

### 5. Launch Dashboard

```bash
streamlit run src/app.py
```

Access at: http://localhost:8501

## Usage

### Import Modes

The application supports three import modes:

#### Incremental (Recommended for Automation)
```bash
python src/scheduled_import.py --mode incremental
```
- Automatically detects last import date
- Only pulls new data since last import
- Efficient for daily/weekly automation

#### Weekly (Ad-hoc Updates)
```bash
python src/scheduled_import.py --mode weekly
```
- Imports last 1 week of data
- Useful for manual refreshes

#### Full (Initial Load Only)
```bash
python src/scheduled_import.py --mode full
```
- Imports 52 weeks (1 year) of data
- Use only for initial setup

### Streamlit Dashboard

The dashboard provides four main sections:

1. **Dashboard**: Service delivery metrics and time entry analysis
2. **Resource Directory**: Searchable resource catalog with filters
3. **Data Import**: Import management with history tracking
4. **Settings**: Database statistics and configuration

### Database Views

10 optimized views for QuickSight reporting:

| View | Description |
|------|-------------|
| `vw_weekly_time_summary` | Weekly aggregates by service line and location |
| `vw_resource_utilization` | Resource utilization and billability metrics |
| `vw_project_time_tracking` | Project-level time tracking and trends |
| `vw_client_time_summary` | Client-level summaries and statistics |
| `vw_skill_area_summary` | Skill area distribution and hours |
| `vw_daily_activity_trend` | Daily activity patterns and trends |
| `vw_active_resources` | Active resource directory with recent activity |
| `vw_import_activity` | Import history and audit trail |
| `vw_service_line_performance_12w` | 12-week service line performance |
| `vw_monthly_summary` | Monthly historical trends |

## Automation

### Local Scheduling (Cron)

```bash
# Quick setup
./scripts/setup_cron.sh

# Manual setup
crontab -e

# Add line (runs every Monday at 1 AM):
0 1 * * 1 cd /Users/cdx/weekly-reporting && python src/scheduled_import.py --mode incremental --notify >> logs/scheduled_import.log 2>&1
```

### AWS EventBridge + Lambda

See [docs/AUTOMATION_SETUP.md](docs/AUTOMATION_SETUP.md) for detailed AWS setup.

## QuickSight Integration

### Setup Steps

1. **Connect Data Source**
   - Create PostgreSQL data source in QuickSight
   - Use your database credentials

2. **Create Datasets**
   - Import views to SPICE for performance
   - Recommended: Start with `vw_weekly_time_summary`

3. **Schedule SPICE Refresh**
   - Weekly: Monday 12:00 AM (after Sunday import)
   - Daily: 3:00 AM (after daily import)

4. **Build Dashboards**
   - Use pre-aggregated views for optimal performance
   - Create calculated fields as needed

See [docs/QUICKSIGHT_SETUP.md](docs/QUICKSIGHT_SETUP.md) for complete guide.

## Project Structure

```
weekly-reporting/
├── src/
│   ├── app.py                          # Streamlit dashboard
│   ├── scheduled_import.py             # Automated import script
│   ├── database/
│   │   ├── config.py                   # Database configuration
│   │   ├── models.py                   # SQLAlchemy models
│   │   ├── init_db.py                  # Database initialization
│   │   ├── create_views.sql            # Reporting views SQL
│   │   └── apply_views.py              # Apply views script
│   └── integrations/
│       ├── clockify_client.py          # Clockify API client
│       └── import_clockify_data.py     # Import logic
├── scripts/
│   └── setup_cron.sh                   # Cron setup helper
├── docs/
│   ├── QUICKSIGHT_SETUP.md            # QuickSight guide
│   └── AUTOMATION_SETUP.md            # Automation guide
├── data/
│   ├── uploads/                        # File uploads
│   └── outputs/                        # Generated files
├── logs/                               # Application logs
├── requirements.txt                    # Python dependencies
├── .env                                # Environment variables
└── README.md                           # This file
```

## Database Schema

### Core Tables

- **clockify_users**: User directory with custom fields
- **clockify_projects**: Project catalog
- **clockify_detailed_time_entries**: Time entries (denormalized)
- **import_logs**: Import history and audit trail
- **user_skills**: Skills tracking (future)
- **ps_resource_forecasts**: Resource forecasting (future)

### Custom Fields Imported

From Clockify user profiles:
- Practice Alignment → Service Line
- Skill Area
- POD Assignment
- Cloudelligent Title
- Location (Onshore/Offshore)
- Employment Designation

## Monitoring

### View Import Activity

```sql
SELECT * FROM vw_import_activity
ORDER BY completed_at DESC
LIMIT 10;
```

### Check Data Freshness

```sql
SELECT
    import_category,
    MAX(completed_at) AS last_import,
    MAX(end_date) AS data_through_date
FROM import_logs
WHERE status = 'success'
GROUP BY import_category;
```

### Streamlit Dashboard

Navigate to "Data Import" → Click "View Import History"

## Troubleshooting

### Import Fails

**Check**:
- Clockify API key is valid
- Database connection is working
- Network access to Clockify API
- Review logs: `logs/scheduled_import.log`

### Missing Data in QuickSight

**Solutions**:
- Refresh SPICE datasets manually
- Verify data exists in PostgreSQL views
- Check QuickSight dataset filters
- Review QuickSight refresh logs

### Database Connection Errors

**Check**:
- DATABASE_URL in .env is correct
- PostgreSQL service is running
- Firewall allows connections
- Database user has proper permissions

## Development

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

## Production Deployment

### Recommended Architecture

```
AWS EventBridge Schedule
    ↓
AWS Lambda (import script)
    ↓
Amazon RDS PostgreSQL
    ↓
Amazon QuickSight (SPICE)
    ↓
Dashboards
```

### Security Best Practices

1. **Secrets Management**: Use AWS Secrets Manager for credentials
2. **VPC**: Deploy database in private subnet
3. **Encryption**: Enable SSL for database connections
4. **IAM**: Use least-privilege IAM roles
5. **Logging**: Enable CloudWatch logs for Lambda

## Support

- **Issues**: Create issue in repository
- **Documentation**: See [docs/](docs/) directory
- **Clockify API**: https://docs.clockify.me/

## Roadmap

- [ ] Skills tracking implementation
- [ ] Resource forecasting module
- [ ] Email report generation
- [ ] Slack integration for notifications
- [ ] Multi-workspace support
- [ ] Advanced analytics dashboards

## License

Proprietary - Cloudelligent Internal Use

## Contributors

- Cloudelligent Team

---

## Quick Reference

### Common Commands

```bash
# Start dashboard
streamlit run src/app.py

# Run incremental import
python src/scheduled_import.py --mode incremental

# Create database views
python src/database/apply_views.py

# View import logs
tail -f logs/scheduled_import.log

# Setup cron
./scripts/setup_cron.sh
```

### Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
CLOCKIFY_API_KEY=your_clockify_api_key
CLOCKIFY_WORKSPACE_ID=your_workspace_id
```

### Support Contacts

- Technical Issues: [Your IT team]
- Clockify Questions: [Clockify admin]
- QuickSight Support: [AWS support]
