#!/usr/bin/env python3
"""Find ALL remaining view dependencies after our pre-drops."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# Get ALL view dependencies in the database
result = q("""
SELECT DISTINCT
    dependent_view.relname AS view_name,
    source_view.relname    AS depends_on
FROM pg_depend
JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid
JOIN pg_class AS dependent_view ON pg_rewrite.ev_class = dependent_view.oid
JOIN pg_class AS source_view    ON pg_depend.refobjid  = source_view.oid
WHERE source_view.relkind  = 'v'
  AND dependent_view.relname != source_view.relname
ORDER BY source_view.relname, dependent_view.relname
""")
print(json.dumps(json.loads(result['body']), indent=2))
