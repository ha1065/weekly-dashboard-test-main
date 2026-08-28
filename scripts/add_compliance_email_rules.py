#!/usr/bin/env python3
"""
Script to add EventBridge rules for compliance report emails.
Targets the production-clockify-import Lambda with scheduled compliance report payloads.

Usage:
    python scripts/add_compliance_email_rules.py
"""

import boto3
import json

def add_compliance_email_rules():
    """Create EventBridge rules for compliance report scheduling."""
    events = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('events')
    lambda_client = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

    # Get the Lambda function to extract its role ARN
    lambda_name = 'production-clockify-import'
    try:
        lambda_info = lambda_client.get_function(FunctionName=lambda_name)
        lambda_arn = lambda_info['Configuration']['FunctionArn']
        role_arn = lambda_info['Configuration']['Role']
    except Exception as e:
        print(f"Error getting Lambda function info: {e}")
        raise

    rules = [
        {
            'Name': 'production-compliance-report-morning',
            'Description': 'Monday 9:30 AM CT (3:30 PM UTC) - non-compliance report after 9am import',
            'ScheduleExpression': 'cron(30 15 ? * MON *)',
            'Payload': {'mode': 'send_compliance_report', 'run': 'morning'}
        },
        {
            'Name': 'production-compliance-report-noon',
            'Description': 'Monday 12:30 PM CT (6:30 PM UTC) - non-compliance report after noon import',
            'ScheduleExpression': 'cron(30 18 ? * MON *)',
            'Payload': {'mode': 'send_compliance_report', 'run': 'noon'}
        }
    ]

    for rule in rules:
        rule_name = rule['Name']
        print(f"\nCreating rule: {rule_name}")

        # Create or update the rule
        try:
            events.put_rule(
                Name=rule_name,
                Description=rule['Description'],
                ScheduleExpression=rule['ScheduleExpression'],
                State='ENABLED'
            )
            print(f"  ✓ Rule created/updated: {rule_name}")
        except Exception as e:
            print(f"  ✗ Error creating rule: {e}")
            raise

        # Create target (Lambda invocation)
        try:
            events.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        'Id': '1',
                        'Arn': lambda_arn,
                        'RoleArn': role_arn,
                        'Input': json.dumps(rule['Payload'])
                    }
                ]
            )
            print(f"  ✓ Target added: {lambda_name}")
        except events.exceptions.ResourceAlreadyExistsException:
            print(f"  ✓ Target already exists (skipping)")
        except Exception as e:
            # If it's a conflict error about target already existing, continue
            if 'ResourceAlreadyExistsException' in str(e) or 'already exists' in str(e):
                print(f"  ✓ Target already exists (skipping)")
            else:
                print(f"  ✗ Error adding target: {e}")
                raise

        # Add Lambda permission for EventBridge to invoke
        try:
            lambda_client.add_permission(
                FunctionName=lambda_name,
                StatementId=f'AllowEventBridgeInvoke-{rule_name}',
                Action='lambda:InvokeFunction',
                Principal='events.amazonaws.com',
                SourceArn=f'arn:aws:events:us-east-1:961341524729:rule/{rule_name}'
            )
            print(f"  ✓ Lambda permission added")
        except lambda_client.exceptions.ResourceConflictException:
            print(f"  ✓ Lambda permission already exists (skipping)")
        except Exception as e:
            if 'already exists' in str(e):
                print(f"  ✓ Lambda permission already exists (skipping)")
            else:
                print(f"  ✗ Error adding permission: {e}")
                raise

    print("\n✅ All compliance email rules configured successfully")


if __name__ == '__main__':
    add_compliance_email_rules()
