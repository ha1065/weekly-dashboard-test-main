#!/usr/bin/env python3
"""Fix kpi-weekly-snapshots-prod: remove _prev columns that don't exist in vw_kpi_ytd."""
import boto3, json, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

# Columns that actually exist in vw_kpi_ytd (from our earlier check)
VALID_COLS = {
    'week_start_date', 'week_num', 'snapshot_taken_at',
    'billable_util_pct', 'productive_util_pct', 'time_compliance_pct',
    'presales_hours', 'productive_nb_hours', 'nb_nonproductive_hours',
    'total_available_hours', 'total_billable_hours', 'missing_time_count',
    'target_billable_util_pct', 'target_productive_util_pct', 'target_time_compliance_pct',
    'billable_util_vs_target', 'productive_util_vs_target', 'compliance_vs_target',
    'billable_util_wow', 'productive_util_wow', 'compliance_wow',
    'presales_wow', 'headcount_wow', 'escalations_wow', 'productive_nb_wow', 'nb_nonproductive_wow',
    # _prev columns (added in migration 060)
    'billable_util_prev', 'productive_util_prev', 'compliance_prev',
    'presales_prev', 'productive_nb_prev', 'nb_nonproductive_prev',
    'missing_time_prev', 'headcount_prev', 'escalations_prev',
    'ps_active_projects', 'ps_on_time_pct', 'ps_avg_duration_weeks',
    'ps_projects_green', 'ps_projects_amber', 'ps_projects_red',
    'ps_billable_hours', 'ps_budget_hours_total', 'ps_actual_hours_ytd',
    'ps_ontime_vs_target', 'ps_billable_wow', 'target_ps_on_time_pct', 'target_ps_avg_duration_weeks',
    'ps_active_prev', 'ps_green_prev', 'ps_red_prev', 'ps_billable_prev',
    'mc_active_projects', 'mc_on_time_pct', 'mc_avg_duration_weeks',
    'mc_projects_green', 'mc_projects_amber', 'mc_projects_red',
    'mc_billable_hours', 'mc_budget_hours_total', 'mc_actual_hours_ytd',
    'mc_ontime_vs_target', 'mc_billable_wow', 'target_mc_on_time_pct',
    'mc_active_prev', 'mc_green_prev', 'mc_red_prev', 'mc_billable_prev',
    'total_projects_red', 'total_projects_amber', 'total_projects_green',
    'total_billable_hours_combined',
    'open_escalations', 'escalations_high_priority', 'escalations_med_priority',
    'avg_escalation_days_open', 'escalations_resolved_ytd',
    'active_resource_count',
}

ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod')['DataSet']

removed = []
for pt_id, pt in ds['PhysicalTableMap'].items():
    if 'RelationalTable' in pt:
        before = len(pt['RelationalTable']['InputColumns'])
        pt['RelationalTable']['InputColumns'] = [
            c for c in pt['RelationalTable']['InputColumns']
            if c['Name'] in VALID_COLS
        ]
        after = len(pt['RelationalTable']['InputColumns'])
        removed_cols = before - after
        if removed_cols:
            print(f'Removed {removed_cols} invalid columns from {pt_id}')

for lt_id, lt in ds.get('LogicalTableMap', {}).items():
    for t in lt.get('DataTransforms', []):
        if 'ProjectOperation' in t:
            t['ProjectOperation']['ProjectedColumns'] = [
                c for c in t['ProjectOperation']['ProjectedColumns']
                if c in VALID_COLS
            ]

qs.update_data_set(
    AwsAccountId=ACCOUNT,
    DataSetId='kpi-weekly-snapshots-prod',
    Name=ds['Name'], ImportMode=ds['ImportMode'],
    PhysicalTableMap=ds['PhysicalTableMap'],
    LogicalTableMap=ds['LogicalTableMap'],
)
print('✅ kpi-weekly-snapshots-prod updated')

# Trigger refresh
time.sleep(1)
qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod',
    IngestionId=f'fix-kpi-{int(time.time())}')
print('✅ SPICE refresh triggered')
