#!/bin/bash
# Deployment script for Weekly Reporting CloudFormation stack
#
# This script deploys the complete infrastructure including VPC, RDS, Lambda, and EventBridge.
# It handles secret management, Lambda packaging, and stack creation/updates.

set -e

# Configuration
STACK_NAME="weekly-reporting-production"
REGION="us-east-1"
ENVIRONMENT="production"
TEMPLATE_FILE="cloudformation/template.yaml"
LAMBDA_PACKAGE="lambda-deployment-package.zip"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

error() {
    echo -e "${RED}✗ ERROR: $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}⚠ WARNING: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI not found. Please install: https://aws.amazon.com/cli/"
    fi
    success "AWS CLI installed"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        error "Python 3 not found"
    fi
    success "Python 3 installed"

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured. Run: aws configure"
    fi
    success "AWS credentials configured"

    # Check if in project root
    if [ ! -f "requirements-lambda.txt" ]; then
        error "Must run from project root directory"
    fi
    success "Running from project root"
}

# Get parameters from user
get_parameters() {
    info "Gathering deployment parameters..."

    # Clockify API Key
    if [ -z "$CLOCKIFY_API_KEY" ]; then
        echo -n "Enter Clockify API Key: "
        read -s CLOCKIFY_API_KEY
        echo
    fi

    # Clockify Workspace ID
    if [ -z "$CLOCKIFY_WORKSPACE_ID" ]; then
        echo -n "Enter Clockify Workspace ID: "
        read CLOCKIFY_WORKSPACE_ID
    fi

    # Database Password
    if [ -z "$DB_PASSWORD" ]; then
        echo -n "Enter Database Master Password (min 16 chars, mixed case/numbers/symbols): "
        read -s DB_PASSWORD
        echo
    fi

    # Validate password strength
    if [ ${#DB_PASSWORD} -lt 16 ]; then
        error "Database password must be at least 16 characters"
    fi

    success "Parameters collected"
}

# Create Lambda deployment package
create_lambda_package() {
    info "Creating Lambda deployment package..."

    # Clean previous package
    rm -rf lambda_package
    rm -f "$LAMBDA_PACKAGE"

    # Create package directory
    mkdir -p lambda_package

    # Copy source code
    cp -r src lambda_package/
    cp requirements-lambda.txt lambda_package/

    # Install dependencies
    pip install -r requirements-lambda.txt -t lambda_package/ --upgrade

    # Create zip file
    cd lambda_package
    zip -r ../"$LAMBDA_PACKAGE" . -x "*.pyc" -x "*__pycache__*" -x "*.git*"
    cd ..

    # Clean up
    rm -rf lambda_package

    success "Lambda package created: $LAMBDA_PACKAGE"
}

# Upload Lambda package to S3
upload_lambda_package() {
    info "Uploading Lambda package to S3..."

    # Create S3 bucket for deployments if it doesn't exist
    DEPLOYMENT_BUCKET="${STACK_NAME}-deployments-$(aws sts get-caller-identity --query Account --output text)"

    if ! aws s3 ls "s3://$DEPLOYMENT_BUCKET" &> /dev/null; then
        aws s3 mb "s3://$DEPLOYMENT_BUCKET" --region "$REGION"
        success "Created deployment bucket: $DEPLOYMENT_BUCKET"
    fi

    # Upload package
    aws s3 cp "$LAMBDA_PACKAGE" "s3://$DEPLOYMENT_BUCKET/lambda/$LAMBDA_PACKAGE"

    success "Lambda package uploaded to S3"

    echo "$DEPLOYMENT_BUCKET"
}

# Deploy CloudFormation stack
deploy_stack() {
    local deployment_bucket=$1

    info "Deploying CloudFormation stack..."

    # Package template (handles Lambda code references)
    PACKAGED_TEMPLATE="cloudformation/template-packaged.yaml"

    aws cloudformation package \
        --template-file "$TEMPLATE_FILE" \
        --s3-bucket "$deployment_bucket" \
        --output-template-file "$PACKAGED_TEMPLATE" \
        --region "$REGION"

    # Deploy stack
    aws cloudformation deploy \
        --template-file "$PACKAGED_TEMPLATE" \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            Environment="$ENVIRONMENT" \
            ClockifyAPIKey="$CLOCKIFY_API_KEY" \
            ClockifyWorkspaceId="$CLOCKIFY_WORKSPACE_ID" \
            DatabasePassword="$DB_PASSWORD" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --no-fail-on-empty-changeset

    success "CloudFormation stack deployed"
}

# Update Lambda function code
update_lambda_code() {
    local deployment_bucket=$1

    info "Updating Lambda function code..."

    LAMBDA_FUNCTION_NAME="${ENVIRONMENT}-clockify-import"

    # Wait for stack to be ready
    aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME" --region "$REGION" 2>/dev/null || \
    aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" --region "$REGION" 2>/dev/null || true

    # Update Lambda code
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --s3-bucket "$deployment_bucket" \
        --s3-key "lambda/$LAMBDA_PACKAGE" \
        --region "$REGION" \
        --publish

    success "Lambda function code updated"
}

# Initialize database
initialize_database() {
    info "Database initialization required..."

    warning "You need to initialize the database manually:"
    echo ""
    echo "1. Get the database endpoint from stack outputs:"
    echo "   aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs'"
    echo ""
    echo "2. Connect to the database using a bastion host or VPN"
    echo ""
    echo "3. Run initialization scripts:"
    echo "   python src/database/init_db.py"
    echo "   python src/database/apply_views.py"
    echo ""
    echo "4. Create application user:"
    echo "   psql -h <endpoint> -U postgres -d weekly_reporting"
    echo "   CREATE USER report_user WITH PASSWORD '<password>';"
    echo "   GRANT ALL PRIVILEGES ON DATABASE weekly_reporting TO report_user;"
    echo "   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO report_user;"
    echo "   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO report_user;"
    echo ""
}

# Get stack outputs
show_outputs() {
    info "Stack outputs:"
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
}

# Main deployment flow
main() {
    echo "========================================"
    echo "Weekly Reporting - AWS Deployment"
    echo "========================================"
    echo ""

    check_prerequisites
    get_parameters
    create_lambda_package

    # Upload and deploy
    deployment_bucket=$(upload_lambda_package | tail -n 1)
    deploy_stack "$deployment_bucket"
    update_lambda_code "$deployment_bucket"

    echo ""
    success "Deployment completed successfully!"
    echo ""

    show_outputs

    echo ""
    initialize_database

    echo ""
    info "Next steps:"
    echo "  1. Initialize the database (see instructions above)"
    echo "  2. Run initial data import:"
    echo "     aws lambda invoke --function-name ${ENVIRONMENT}-clockify-import \\"
    echo "       --payload '{\"mode\":\"full\"}' response.json"
    echo "  3. Set up QuickSight data sources (see docs/QUICKSIGHT_SETUP.md)"
    echo "  4. Subscribe to SNS notifications for import status"
    echo ""
}

# Run deployment
main
