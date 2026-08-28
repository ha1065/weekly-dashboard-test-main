#!/bin/bash
set -e

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${ENVIRONMENT}-weekly-reporting-dashboard"

echo "=============================================="
echo "Deploy Dashboard CloudFormation Stack"
echo "=============================================="
echo "Environment: ${ENVIRONMENT}"
echo "AWS Region: ${AWS_REGION}"
echo "Stack Name: ${STACK_NAME}"
echo "=============================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Get values from main stack
MAIN_STACK="${ENVIRONMENT}-weekly-reporting"

echo ""
echo "Getting values from main stack: ${MAIN_STACK}..."

VPC_ID=$(aws cloudformation describe-stacks \
    --stack-name ${MAIN_STACK} \
    --query "Stacks[0].Outputs[?OutputKey=='VPCId'].OutputValue" \
    --output text \
    --region ${AWS_REGION})

DATABASE_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name ${MAIN_STACK} \
    --query "Stacks[0].Outputs[?OutputKey=='DatabaseEndpoint'].OutputValue" \
    --output text \
    --region ${AWS_REGION})

DATABASE_SG=$(aws cloudformation describe-stacks \
    --stack-name ${MAIN_STACK} \
    --query "Stacks[0].Outputs[?OutputKey=='DatabaseSecurityGroupId'].OutputValue" \
    --output text \
    --region ${AWS_REGION})

SECRETS_ARN=$(aws cloudformation describe-stacks \
    --stack-name ${MAIN_STACK} \
    --query "Stacks[0].Outputs[?OutputKey=='SecretsManagerARN'].OutputValue" \
    --output text \
    --region ${AWS_REGION})

# Get subnet IDs
echo "Getting subnet IDs..."

# Get public subnets
PUBLIC_SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=*public*" \
    --query "Subnets[*].SubnetId" \
    --output text \
    --region ${AWS_REGION})
PUBLIC_SUBNET_1=$(echo $PUBLIC_SUBNETS | awk '{print $1}')
PUBLIC_SUBNET_2=$(echo $PUBLIC_SUBNETS | awk '{print $2}')

# Get private subnets
PRIVATE_SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=*private*" \
    --query "Subnets[*].SubnetId" \
    --output text \
    --region ${AWS_REGION})
PRIVATE_SUBNET_1=$(echo $PRIVATE_SUBNETS | awk '{print $1}')
PRIVATE_SUBNET_2=$(echo $PRIVATE_SUBNETS | awk '{print $2}')

echo "VPC ID: ${VPC_ID}"
echo "Database Endpoint: ${DATABASE_ENDPOINT}"
echo "Database SG: ${DATABASE_SG}"
echo "Secrets ARN: ${SECRETS_ARN}"
echo "Public Subnets: ${PUBLIC_SUBNET_1}, ${PUBLIC_SUBNET_2}"
echo "Private Subnets: ${PRIVATE_SUBNET_1}, ${PRIVATE_SUBNET_2}"

# Check if stack exists
STACK_EXISTS=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${AWS_REGION} 2>/dev/null || echo "")

if [ -z "$STACK_EXISTS" ]; then
    echo ""
    echo "Creating new stack..."
    ACTION="create-stack"
    WAIT_ACTION="stack-create-complete"
else
    echo ""
    echo "Updating existing stack..."
    ACTION="update-stack"
    WAIT_ACTION="stack-update-complete"
fi

# Deploy CloudFormation stack
echo ""
echo "Deploying CloudFormation stack..."

aws cloudformation ${ACTION} \
    --stack-name ${STACK_NAME} \
    --template-body file://${PROJECT_ROOT}/cloudformation/streamlit-ecs.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
        ParameterKey=VpcId,ParameterValue=${VPC_ID} \
        ParameterKey=PublicSubnet1,ParameterValue=${PUBLIC_SUBNET_1} \
        ParameterKey=PublicSubnet2,ParameterValue=${PUBLIC_SUBNET_2} \
        ParameterKey=PrivateSubnet1,ParameterValue=${PRIVATE_SUBNET_1} \
        ParameterKey=PrivateSubnet2,ParameterValue=${PRIVATE_SUBNET_2} \
        ParameterKey=DatabaseSecurityGroupId,ParameterValue=${DATABASE_SG} \
        ParameterKey=DatabaseEndpoint,ParameterValue=${DATABASE_ENDPOINT} \
        ParameterKey=SecretsManagerArn,ParameterValue=${SECRETS_ARN} \
    --capabilities CAPABILITY_NAMED_IAM \
    --region ${AWS_REGION}

echo ""
echo "Waiting for stack ${ACTION} to complete..."
aws cloudformation wait ${WAIT_ACTION} \
    --stack-name ${STACK_NAME} \
    --region ${AWS_REGION}

echo ""
echo "=============================================="
echo "Stack deployment completed!"
echo "=============================================="

# Show outputs
echo ""
echo "Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
    --output table \
    --region ${AWS_REGION}

echo ""
echo "Next steps:"
echo "1. Build and push the Docker image:"
echo "   ./scripts/deploy_dashboard.sh"
echo ""
echo "2. The dashboard will be available at the ALBDNSName URL above"
