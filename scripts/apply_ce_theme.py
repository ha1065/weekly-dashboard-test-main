#!/usr/bin/env python3
import boto3, json, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'
ANALYSIS_ID = '0c48736d-0c17-4607-998c-4c2410d20025'

resp = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
name = resp['Analysis']['Name']
print(f'Applying CE theme to: {name}')

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name=name, ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')

time.sleep(15)
status = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Status']
print(f'Final status: {status}')
