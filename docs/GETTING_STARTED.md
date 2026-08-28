# Getting Started Guide

This guide will walk you through setting up your Weekly Reporting application from scratch.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Python 3.11 or higher installed
- [ ] PostgreSQL database (local or RDS)
- [ ] Clockify account with API access
- [ ] Clockify API key
- [ ] Clockify Workspace ID
- [ ] AWS account (for QuickSight, optional for initial setup)

## Step-by-Step Setup

### Step 1: Get Clockify Credentials

1. **Get API Key**
   - Log in to Clockify: https://app.clockify.me/
   - Go to Settings → Profile Settings
   - Scroll to API section
   - Generate or copy your API key

2. **Get Workspace ID**
   - In Clockify, click on workspace name (top left)
   - Go to Settings → Workspace settings
   - Copy the Workspace ID from the URL or settings page
   - Format: `5f4abc123def456789`

### Step 2: Prepare Database

#### Option A: Local PostgreSQL

```bash
# Install PostgreSQL (macOS)
brew install postgresql@15

# Start PostgreSQL
brew services start postgresql@15

# Create database
createdb weekly_reporting

# Create user (optional)
psql postgres
CREATE USER reporting_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE weekly_reporting TO reporting_user;
\q
```

#### Option B: AWS RDS

1. Create RDS PostgreSQL instance via AWS Console
2. Choose PostgreSQL 15.x
3. Note the endpoint, port, database name, username, password
4. Configure security group to allow your IP

### Step 3: Clone and Install

```bash
# Navigate to project directory
cd /Users/cdx/weekly-reporting

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import streamlit; import sqlalchemy; print('✓ Dependencies installed')"
```

### Step 4: Configure Environment

```bash
# Create .env file
cp .env.example .env

# Edit .env file
nano .env
```

Update with your values:
```bash
DATABASE_URL=postgresql://reporting_user:your_password@localhost:5432/weekly_reporting
CLOCKIFY_API_KEY=YourClockifyAPIKeyHere
CLOCKIFY_WORKSPACE_ID=YourWorkspaceIDHere
```

**Important**: Never commit `.env` to version control!

### Step 5: Initialize Database

```bash
# Create database tables
python src/database/init_db.py

# Expected output:
# Creating database tables...
# ✓ Database tables created successfully!

# Create reporting views
python src/database/apply_views.py

# Expected output:
# 🔨 Creating QuickSight Reporting Views
# ✅ Successfully created all reporting views!
```

### Step 6: Test Clockify Connection

```bash
# Test API connection
python src/integrations/clockify_client.py

# Expected output:
# Testing Clockify connection...
# 1. Fetching users...
# ✓ Found X users
# 2. Fetching projects...
# ✓ Found X projects
# 3. Fetching recent time entries...
# ✓ Found X time entries
# ✅ Clockify connection successful!
```

If this fails:
- Verify API key is correct
- Check workspace ID is correct
- Ensure you have internet connection
- Confirm API key has proper permissions

### Step 7: Initial Data Import

Choose one method:

#### Method A: Command Line (Fastest)

```bash
# Import 1 year of data
python -c "from src.integrations.import_clockify_data import run_full_import; run_full_import()"
```

This will take 5-15 minutes depending on data volume.

#### Method B: Streamlit UI (Recommended for first-time users)

```bash
# Launch Streamlit
streamlit run src/app.py

# Browser will open to http://localhost:8501
# Navigate to: Data Import → Initial Load (1 Year) → Run Import
```

### Step 8: Verify Data Import

```bash
# Connect to database
psql weekly_reporting

# Check data
SELECT COUNT(*) FROM clockify_users;
SELECT COUNT(*) FROM clockify_projects;
SELECT COUNT(*) FROM clockify_detailed_time_entries;

# View import logs
SELECT * FROM import_logs ORDER BY completed_at DESC LIMIT 5;

# Exit
\q
```

Expected results:
- Users: 10-100+ (depends on your organization)
- Projects: 20-500+ (depends on your organization)
- Time entries: 1000-50000+ (depends on organization size and 1 year of data)

### Step 9: Explore Dashboard

```bash
# Launch dashboard (if not already running)
streamlit run src/app.py
```

Navigate through:
1. **Dashboard**: View service line metrics
2. **Resource Directory**: Browse your team
3. **Data Import**: Review import history
4. **Settings**: Check database stats

### Step 10: Set Up Automation (Optional)

```bash
# Set up weekly automated imports
./scripts/setup_cron.sh

# Verify cron job
crontab -l
```

This will run incremental imports every Monday at 1 AM.

## Validation Checklist

After setup, verify everything works:

- [ ] Database tables created successfully
- [ ] Reporting views created successfully
- [ ] Clockify API connection working
- [ ] Initial data import completed
- [ ] Users imported correctly
- [ ] Projects imported correctly
- [ ] Time entries imported correctly
- [ ] Streamlit dashboard loads
- [ ] Dashboard shows data correctly
- [ ] Import logs visible in database
- [ ] Automation scheduled (optional)

## Next Steps

### For Development/Testing

1. Explore the Streamlit dashboard
2. Review imported data for accuracy
3. Test incremental imports
4. Customize views as needed

### For Production Use

1. Follow [QUICKSIGHT_SETUP.md](QUICKSIGHT_SETUP.md) to set up QuickSight
2. Follow [AUTOMATION_SETUP.md](AUTOMATION_SETUP.md) for production automation
3. Set up monitoring and alerts
4. Document runbook for your team

## Common Issues and Solutions

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution**:
```bash
# Make sure you're in the project root
cd /Users/cdx/weekly-reporting

# Run Python with project in path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Issue: "Could not connect to database"

**Solutions**:
1. Verify PostgreSQL is running: `pg_isready`
2. Check DATABASE_URL in .env
3. Test connection: `psql $DATABASE_URL`
4. Check firewall/security groups

### Issue: "Clockify API authentication failed"

**Solutions**:
1. Verify API key in .env (no quotes needed)
2. Check API key is still valid in Clockify
3. Ensure API key has workspace access
4. Try generating a new API key

### Issue: "Import takes too long"

This is normal for large datasets:
- 10K entries: ~5 minutes
- 50K entries: ~15 minutes
- 100K+ entries: ~30+ minutes

**Tips**:
- Use incremental imports after initial load
- Consider importing fewer weeks initially
- Check network connection speed

### Issue: "Not all users imported"

**Check**:
1. Users might be inactive (only active users are imported for time entries)
2. Users might have no name/email (skipped with warning)
3. Review logs for warnings

### Issue: "Views not showing data in QuickSight"

**Solutions**:
1. Verify views have data: `SELECT * FROM vw_weekly_time_summary LIMIT 10;`
2. Refresh SPICE dataset manually in QuickSight
3. Check QuickSight dataset filters
4. Verify date ranges in views match expectations

## Getting Help

If you encounter issues:

1. **Check Logs**
   ```bash
   # Application logs
   tail -f logs/scheduled_import.log

   # Database import logs
   psql weekly_reporting -c "SELECT * FROM vw_import_activity;"
   ```

2. **Review Documentation**
   - [README.md](../README.md) - Overview and quick reference
   - [QUICKSIGHT_SETUP.md](QUICKSIGHT_SETUP.md) - QuickSight integration
   - [AUTOMATION_SETUP.md](AUTOMATION_SETUP.md) - Automation setup

3. **Test Components Individually**
   ```bash
   # Test database connection
   python -c "from src.database.config import engine; print(engine.execute('SELECT 1').scalar())"

   # Test Clockify API
   python src/integrations/clockify_client.py

   # Test import function
   python src/scheduled_import.py --mode weekly
   ```

## Success Criteria

You've successfully set up the application when:

✅ Dashboard loads and shows your organization's data
✅ Service line metrics are accurate
✅ Resource directory shows your team
✅ Time entries are being tracked
✅ Import logs show successful operations
✅ Incremental imports work correctly
✅ (Optional) QuickSight dashboards are live
✅ (Optional) Automated imports are scheduled

## What's Next?

Congratulations on setting up your Weekly Reporting system!

**For immediate use**:
- Start using the Streamlit dashboard for weekly reporting
- Run manual incremental imports as needed
- Export data for analysis

**For production deployment**:
- Set up QuickSight dashboards
- Configure automated weekly imports
- Set up monitoring and alerts
- Train your team on the system

**For customization**:
- Modify views for your specific reporting needs
- Add custom fields to data models
- Create custom dashboards in Streamlit
- Integrate with other tools (Slack, email, etc.)

Happy reporting! 📊
