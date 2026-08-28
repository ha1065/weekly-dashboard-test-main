#!/bin/bash
# Setup cron job for automated weekly Clockify imports
#
# This script helps set up a cron job to run the Clockify import automatically.
# By default, it runs every Monday at 1:00 AM.
#
# Usage:
#   ./scripts/setup_cron.sh

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_PATH=$(which python3)

# Cron job configuration
# Run every Monday at 1:00 AM (incremental mode)
CRON_SCHEDULE="0 1 * * 1"
CRON_COMMAND="cd $PROJECT_DIR && $PYTHON_PATH src/scheduled_import.py --mode incremental --notify >> $PROJECT_DIR/logs/scheduled_import.log 2>&1"

echo "Setting up cron job for Clockify imports"
echo "=========================================="
echo ""
echo "Project Directory: $PROJECT_DIR"
echo "Python Path: $PYTHON_PATH"
echo "Schedule: Every Monday at 1:00 AM"
echo ""

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# Check if cron job already exists
EXISTING_CRON=$(crontab -l 2>/dev/null | grep "scheduled_import.py" || true)

if [ -n "$EXISTING_CRON" ]; then
    echo "⚠️  Existing cron job found:"
    echo "$EXISTING_CRON"
    echo ""
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    # Remove existing cron job
    (crontab -l 2>/dev/null | grep -v "scheduled_import.py") | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_COMMAND") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "Current crontab:"
crontab -l | grep "scheduled_import.py"
echo ""
echo "To view all cron jobs: crontab -l"
echo "To remove this cron job: crontab -e (then delete the line)"
echo ""
echo "Logs will be written to: $PROJECT_DIR/logs/scheduled_import.log"
echo ""
echo "📋 Other useful cron schedules:"
echo "   Every day at 2 AM:     0 2 * * *"
echo "   Every Sunday at 1 AM:  0 1 * * 0"
echo "   Every 6 hours:         0 */6 * * *"
echo ""
