#!/bin/bash
# Quick script to update Lambda and apply database views
set -e

REGION="us-east-1"
ENVIRONMENT="production"
LAMBDA_FUNCTION_NAME="${ENVIRONMENT}-clockify-import"
LAMBDA_PACKAGE="lambda-deployment-package.zip"
DEPLOYMENT_BUCKET="weekly-reporting-production-deployments-$(aws sts get-caller-identity --query Account --output text --region $REGION)"

echo "========================================"
echo "Update Lambda and Apply Views"
echo "========================================"

# Clean and create package
echo "Creating Lambda package..."
rm -rf lambda_package
rm -f "$LAMBDA_PACKAGE"
mkdir -p lambda_package

# Copy source code
cp -r src lambda_package/

# Install dependencies (use Lambda-minimal packages)
pip3 install -r requirements-lambda.txt -t lambda_package/ --upgrade --quiet

# Create zip
cd lambda_package
zip -r ../"$LAMBDA_PACKAGE" . -x "*.pyc" -x "*__pycache__*" -x "*.git*" > /dev/null
cd ..
rm -rf lambda_package

echo "Uploading to S3..."
aws s3 cp "$LAMBDA_PACKAGE" "s3://$DEPLOYMENT_BUCKET/lambda/$LAMBDA_PACKAGE" --region $REGION

echo "Updating Lambda function..."
aws lambda update-function-code \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --s3-bucket "$DEPLOYMENT_BUCKET" \
    --s3-key "lambda/$LAMBDA_PACKAGE" \
    --region "$REGION" \
    --publish > /dev/null

echo "Waiting for Lambda to be ready..."
aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION_NAME" --region $REGION

echo "Applying database views..."
aws lambda invoke \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --payload '{"mode":"apply_views"}' \
    --region "$REGION" \
    --cli-binary-format raw-in-base64-out \
    /tmp/apply_views_response.json

echo ""
echo "Response:"
cat /tmp/apply_views_response.json | python3 -m json.tool 2>/dev/null || cat /tmp/apply_views_response.json

echo ""
echo "Done!"
