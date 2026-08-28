#!/bin/bash
set -e

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REPO="${ENVIRONMENT}-weekly-reporting-dashboard"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "=============================================="
echo "Weekly Reporting Dashboard Deployment"
echo "=============================================="
echo "Environment: ${ENVIRONMENT}"
echo "AWS Region: ${AWS_REGION}"
echo "AWS Account: ${AWS_ACCOUNT_ID}"
echo "ECR Repository: ${ECR_REPO}"
echo "Image Tag: ${IMAGE_TAG}"
echo "=============================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Step 1: Build Docker image
echo ""
echo "Step 1: Building Docker image..."
docker build --platform linux/amd64 -t ${ECR_REPO}:${IMAGE_TAG} .

# Step 2: Authenticate with ECR
echo ""
echo "Step 2: Authenticating with ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Step 3: Tag and push image to ECR
echo ""
echo "Step 3: Pushing image to ECR..."
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
docker push ${ECR_URI}:${IMAGE_TAG}

echo "Image pushed successfully: ${ECR_URI}:${IMAGE_TAG}"

# Step 4: Update ECS Service (force new deployment)
echo ""
echo "Step 4: Updating ECS service..."
CLUSTER_NAME="${ENVIRONMENT}-weekly-reporting"
SERVICE_NAME="${ENVIRONMENT}-dashboard-service"

aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_NAME} \
    --force-new-deployment \
    --region ${AWS_REGION} \
    --output text > /dev/null

echo "ECS service update initiated"

# Step 5: Wait for deployment to complete
echo ""
echo "Step 5: Waiting for deployment to stabilize..."
aws ecs wait services-stable \
    --cluster ${CLUSTER_NAME} \
    --services ${SERVICE_NAME} \
    --region ${AWS_REGION}

echo ""
echo "=============================================="
echo "Deployment completed successfully!"
echo "=============================================="

# Get ALB DNS name
ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name ${ENVIRONMENT}-weekly-reporting-dashboard \
    --query "Stacks[0].Outputs[?OutputKey=='ALBDNSName'].OutputValue" \
    --output text \
    --region ${AWS_REGION} 2>/dev/null || echo "")

if [ -n "$ALB_DNS" ]; then
    echo "Dashboard URL: http://${ALB_DNS}"
fi
