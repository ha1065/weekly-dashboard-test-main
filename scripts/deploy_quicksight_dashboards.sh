#!/bin/bash

# QuickSight Dashboard Deployment Script
# This script deploys the Clockify QuickSight dashboards using CloudFormation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="prod"
STACK_NAME_PREFIX="clockify-quicksight-dashboards"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV     Environment (dev/staging/prod) [default: prod]"
    echo "  -a, --aws-account-id ID   AWS Account ID (required)"
    echo "  -u, --quicksight-user USER QuickSight username (required)"
    echo "  -v, --vpc-connection ARN  VPC connection ARN (required)"
    echo "  -h, --database-host HOST  Database host (required)"
    echo "  -d, --database-name NAME  Database name [default: clockify_reporting]"
    echo "  -U, --database-user USER  Database username [default: admin]"
    echo "  -P, --database-pass PASS  Database password (required)"
    echo "  --help                    Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 -e prod -a 123456789012 -u john.doe \\"
    echo "     -v arn:aws:quicksight:us-east-1:123456789012:vpcConnection/conn-123 \\"
    echo "     -h mydb.cluster-xyz.us-east-1.rds.amazonaws.com \\"
    echo "     -P mySecurePassword123"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -a|--aws-account-id)
            AWS_ACCOUNT_ID="$2"
            shift 2
            ;;
        -u|--quicksight-user)
            QUICKSIGHT_USERNAME="$2"
            shift 2
            ;;
        -v|--vpc-connection)
            VPC_CONNECTION_ARN="$2"
            shift 2
            ;;
        -h|--database-host)
            DATABASE_HOST="$2"
            shift 2
            ;;
        -d|--database-name)
            DATABASE_NAME="$2"
            shift 2
            ;;
        -U|--database-user)
            DATABASE_USERNAME="$2"
            shift 2
            ;;
        -P|--database-pass)
            DATABASE_PASSWORD="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set defaults
DATABASE_NAME="${DATABASE_NAME:-clockify_reporting}"
DATABASE_USERNAME="${DATABASE_USERNAME:-admin}"
STACK_NAME="${STACK_NAME_PREFIX}-${ENVIRONMENT}"

# Validate required parameters
if [[ -z "$AWS_ACCOUNT_ID" ]]; then
    print_error "AWS Account ID is required"
    show_usage
    exit 1
fi

if [[ -z "$QUICKSIGHT_USERNAME" ]]; then
    print_error "QuickSight username is required"
    show_usage
    exit 1
fi

if [[ -z "$VPC_CONNECTION_ARN" ]]; then
    print_error "VPC connection ARN is required"
    show_usage
    exit 1
fi

if [[ -z "$DATABASE_HOST" ]]; then
    print_error "Database host is required"
    show_usage
    exit 1
fi

if [[ -z "$DATABASE_PASSWORD" ]]; then
    print_error "Database password is required"
    show_usage
    exit 1
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Environment must be one of: dev, staging, prod"
    exit 1
fi

# Print deployment summary
echo "============================================================"
echo "🚀 QuickSight Dashboard Deployment"
echo "============================================================"
print_status "Environment: $ENVIRONMENT"
print_status "Stack Name: $STACK_NAME"
print_status "AWS Account ID: $AWS_ACCOUNT_ID"
print_status "QuickSight User: $QUICKSIGHT_USERNAME"
print_status "Database Host: $DATABASE_HOST"
print_status "Database Name: $DATABASE_NAME"
print_status "Database User: $DATABASE_USERNAME"
echo "============================================================"

# Check if CloudFormation template exists
TEMPLATE_FILE="cloudformation/quicksight-dashboards.yaml"
if [[ ! -f "$TEMPLATE_FILE" ]]; then
    print_error "CloudFormation template not found: $TEMPLATE_FILE"
    exit 1
fi

print_status "CloudFormation template found: $TEMPLATE_FILE"

# Check AWS CLI availability
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed or not in PATH"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured or invalid"
    exit 1
fi

print_success "AWS CLI configured and credentials valid"

# Deploy the CloudFormation stack
print_status "Deploying CloudFormation stack..."

aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
        QuickSightUsername="$QUICKSIGHT_USERNAME" \
        AwsAccountId="$AWS_ACCOUNT_ID" \
        VpcConnectionArn="$VPC_CONNECTION_ARN" \
        DatabaseHost="$DATABASE_HOST" \
        DatabaseName="$DATABASE_NAME" \
        DatabaseUsername="$DATABASE_USERNAME" \
        DatabasePassword="$DATABASE_PASSWORD" \
    --capabilities CAPABILITY_IAM

if [[ $? -eq 0 ]]; then
    print_success "CloudFormation stack deployed successfully!"
else
    print_error "CloudFormation deployment failed"
    exit 1
fi

# Get stack outputs
print_status "Retrieving stack outputs..."

OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs' \
    --output table)

if [[ $? -eq 0 ]]; then
    echo ""
    echo "============================================================"
    echo "📊 Deployment Outputs"
    echo "============================================================"
    echo "$OUTPUTS"
else
    print_warning "Could not retrieve stack outputs"
fi

# Offer to refresh datasets
echo ""
echo "============================================================"
echo "🔄 Dataset Refresh"
echo "============================================================"
print_status "Would you like to refresh the QuickSight datasets now? (y/n)"
read -r REFRESH_DATASETS

if [[ "$REFRESH_DATASETS" =~ ^[Yy]$ ]]; then
    print_status "Starting dataset refresh..."
    
    if [[ -f "scripts/refresh_quicksight_datasets.py" ]]; then
        python scripts/refresh_quicksight_datasets.py \
            --environment "$ENVIRONMENT" \
            --aws-account-id "$AWS_ACCOUNT_ID" \
            --timeout 30
    else
        print_warning "Dataset refresh script not found. You can manually refresh datasets in QuickSight console."
    fi
else
    print_status "Skipping dataset refresh. You can run it later with:"
    echo "python scripts/refresh_quicksight_datasets.py --environment $ENVIRONMENT --aws-account-id $AWS_ACCOUNT_ID"
fi

echo ""
echo "============================================================"
echo "🎉 Deployment Complete!"
echo "============================================================"
print_success "QuickSight dashboards have been deployed successfully"
print_status "You can now access your dashboards in the QuickSight console"
print_status "Stack name: $STACK_NAME"
echo "============================================================"