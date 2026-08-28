#!/bin/bash
# Security checklist script for weekly-reporting application
#
# This script checks for common security issues and misconfigurations.
# Run before deploying to production.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "Security Check - Weekly Reporting"
echo "========================================"
echo ""

ERRORS=0
WARNINGS=0

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

error() {
    echo -e "${RED}✗ ERROR: $1${NC}"
    ERRORS=$((ERRORS + 1))
}

warning() {
    echo -e "${YELLOW}⚠ WARNING: $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

info() {
    echo "ℹ $1"
}

# Check 1: .env file exists and has correct permissions
echo "1. Checking .env file..."
if [ ! -f ".env" ]; then
    error ".env file not found"
else
    success ".env file exists"

    # Check permissions
    PERMS=$(stat -f "%Lp" .env 2>/dev/null || stat -c "%a" .env 2>/dev/null)
    if [ "$PERMS" != "600" ]; then
        warning ".env permissions are $PERMS (should be 600)"
        info "  Fix with: chmod 600 .env"
    else
        success ".env has correct permissions (600)"
    fi

    # Check for weak passwords
    if grep -q "password@\|password123\|admin@" .env 2>/dev/null; then
        error "Weak password detected in .env"
    fi

    # Check for placeholder values
    if grep -q "your_api_key_here\|your_workspace_id\|your_password" .env 2>/dev/null; then
        error "Placeholder values found in .env"
    else
        success "No placeholder values in .env"
    fi
fi
echo ""

# Check 2: .env is in .gitignore
echo "2. Checking .gitignore..."
if grep -q "^\.env$" .gitignore 2>/dev/null; then
    success ".env is in .gitignore"
else
    error ".env is NOT in .gitignore"
fi
echo ""

# Check 3: No credentials in git
echo "3. Checking for credentials in git..."
if git log --all --pretty=format: -S "api_key" -S "password" --name-only | grep -q .; then
    warning "Possible credentials found in git history"
    info "  Review git history for exposed secrets"
else
    success "No obvious credentials in git history"
fi
echo ""

# Check 4: Python dependencies
echo "4. Checking Python dependencies..."
if command -v safety &> /dev/null; then
    safety check --json > /tmp/safety_check.json 2>&1 || true
    VULNS=$(cat /tmp/safety_check.json | grep -o '"vulnerabilities_found": [0-9]*' | grep -o '[0-9]*')
    if [ "$VULNS" -gt 0 ]; then
        error "Found $VULNS vulnerable dependencies"
        info "  Run: safety check --full-report"
    else
        success "No known vulnerabilities in dependencies"
    fi
    rm -f /tmp/safety_check.json
else
    warning "safety not installed (pip install safety)"
fi
echo ""

# Check 5: Database URL format
echo "5. Checking database configuration..."
if [ -f ".env" ]; then
    if grep -q "DATABASE_URL.*postgresql://" .env; then
        success "Database URL uses postgresql://"

        # Check for SSL mode
        if grep -q "sslmode=" .env; then
            success "SSL mode configured"
        else
            warning "SSL mode not configured in DATABASE_URL"
            info "  Add ?sslmode=require to DATABASE_URL for production"
        fi
    else
        error "DATABASE_URL format incorrect"
    fi
fi
echo ""

# Check 6: File permissions
echo "6. Checking file permissions..."
if [ -d "logs" ]; then
    LOG_PERMS=$(stat -f "%Lp" logs 2>/dev/null || stat -c "%a" logs 2>/dev/null)
    if [ "$LOG_PERMS" = "777" ]; then
        warning "logs directory has 777 permissions (too permissive)"
        info "  Fix with: chmod 755 logs"
    else
        success "logs directory permissions OK"
    fi
fi
echo ""

# Check 7: Check for hardcoded secrets in code
echo "7. Scanning code for hardcoded secrets..."
FOUND_SECRETS=0

# Check for API keys
if grep -r "api_key.*=.*['\"][a-zA-Z0-9]\{20,\}" src/ --exclude-dir=__pycache__ 2>/dev/null; then
    error "Possible hardcoded API key found in code"
    FOUND_SECRETS=1
fi

# Check for passwords
if grep -r "password.*=.*['\"][^'\"]*['\"]" src/ --exclude-dir=__pycache__ | grep -v "password.*:.*str" 2>/dev/null; then
    warning "Possible hardcoded password found in code"
    FOUND_SECRETS=1
fi

if [ $FOUND_SECRETS -eq 0 ]; then
    success "No obvious hardcoded secrets in code"
fi
echo ""

# Check 8: SQLAlchemy SQL echo setting
echo "8. Checking SQLAlchemy configuration..."
if grep -r "echo=True" src/ 2>/dev/null; then
    warning "SQLAlchemy echo=True found (should be False in production)"
else
    success "SQLAlchemy echo setting OK"
fi
echo ""

# Check 9: Error handling
echo "9. Checking error handling..."
if grep -r "except.*pass" src/ 2>/dev/null; then
    warning "Silent exception handling found (except: pass)"
    info "  Review exception handling to ensure errors are logged"
fi
echo ""

# Check 10: Logging configuration
echo "10. Checking logging configuration..."
if [ -d "logs" ]; then
    # Check if logs might contain secrets
    if grep -r "password\|api_key" logs/ 2>/dev/null | grep -v "Binary file" | head -1; then
        error "Possible secrets found in log files"
        info "  Review and sanitize logs"
    fi
fi
echo ""

# Summary
echo "========================================"
echo "Security Check Summary"
echo "========================================"
echo ""
echo -e "Errors: ${RED}${ERRORS}${NC}"
echo -e "Warnings: ${YELLOW}${WARNINGS}${NC}"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ Security check FAILED - fix errors before deploying${NC}"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Security check passed with warnings${NC}"
    echo "   Review warnings before deploying to production"
    exit 0
else
    echo -e "${GREEN}✅ Security check PASSED${NC}"
    exit 0
fi
