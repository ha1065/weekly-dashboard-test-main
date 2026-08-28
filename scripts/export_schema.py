#!/usr/bin/env python3
"""Export database schema to Excel for review."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from sqlalchemy import text
from src.database.config import engine

def get_table_columns():
    """Get all table columns with their types."""
    query = text("""
        SELECT
            table_name,
            column_name,
            data_type,
            character_maximum_length,
            numeric_precision,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name NOT LIKE 'pg_%'
        ORDER BY table_name, ordinal_position
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return pd.DataFrame(result.fetchall(), columns=[
            'Table', 'Column', 'Data Type', 'Max Length',
            'Numeric Precision', 'Nullable', 'Default'
        ])

def get_views():
    """Get all view definitions."""
    query = text("""
        SELECT
            viewname as view_name,
            definition
        FROM pg_views
        WHERE schemaname = 'public'
        ORDER BY viewname
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return pd.DataFrame(result.fetchall(), columns=['View Name', 'Definition'])

def get_table_counts():
    """Get row counts for all tables."""
    # First get table names
    tables_query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)

    with engine.connect() as conn:
        result = conn.execute(tables_query)
        tables = [row[0] for row in result.fetchall()]

        counts = []
        for table in tables:
            try:
                count_result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                count = count_result.scalar()
                counts.append({'Table': table, 'Row Count': count})
            except Exception as e:
                counts.append({'Table': table, 'Row Count': f'Error: {e}'})

        return pd.DataFrame(counts)

def get_indexes():
    """Get all indexes."""
    query = text("""
        SELECT
            tablename as table_name,
            indexname as index_name,
            indexdef as definition
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return pd.DataFrame(result.fetchall(), columns=['Table', 'Index Name', 'Definition'])

def get_constraints():
    """Get all constraints (primary keys, foreign keys, unique)."""
    query = text("""
        SELECT
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.table_schema = 'public'
        ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        return pd.DataFrame(result.fetchall(), columns=[
            'Table', 'Constraint Name', 'Type', 'Column',
            'Foreign Table', 'Foreign Column'
        ])

def main():
    print("Connecting to database...")

    output_path = project_root / 'database_schema.xlsx'

    print("Fetching table columns...")
    columns_df = get_table_columns()

    print("Fetching views...")
    views_df = get_views()

    print("Fetching table row counts...")
    counts_df = get_table_counts()

    print("Fetching indexes...")
    indexes_df = get_indexes()

    print("Fetching constraints...")
    constraints_df = get_constraints()

    # Write to Excel with multiple sheets
    print(f"Writing to {output_path}...")
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = {
            'Item': ['Total Tables', 'Total Views', 'Total Columns'],
            'Count': [
                columns_df['Table'].nunique(),
                len(views_df),
                len(columns_df)
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        # Table counts
        counts_df.to_excel(writer, sheet_name='Table Counts', index=False)

        # All columns
        columns_df.to_excel(writer, sheet_name='All Columns', index=False)

        # Create separate sheets for each major table
        for table in columns_df['Table'].unique():
            table_cols = columns_df[columns_df['Table'] == table]
            # Truncate sheet name to 31 chars (Excel limit)
            sheet_name = table[:31]
            table_cols.to_excel(writer, sheet_name=sheet_name, index=False)

        # Views
        views_df.to_excel(writer, sheet_name='Views', index=False)

        # Indexes
        indexes_df.to_excel(writer, sheet_name='Indexes', index=False)

        # Constraints
        constraints_df.to_excel(writer, sheet_name='Constraints', index=False)

    print(f"\nSchema exported to: {output_path}")

    # Also print summary to console
    print("\n" + "="*60)
    print("DATABASE SCHEMA SUMMARY")
    print("="*60)

    print("\nTABLES AND ROW COUNTS:")
    print(counts_df.to_string(index=False))

    print("\n\nTABLE COLUMNS:")
    for table in columns_df['Table'].unique():
        print(f"\n--- {table} ---")
        table_cols = columns_df[columns_df['Table'] == table][['Column', 'Data Type', 'Nullable']]
        print(table_cols.to_string(index=False))

    print("\n\nVIEWS:")
    for _, row in views_df.iterrows():
        print(f"\n--- {row['View Name']} ---")

if __name__ == "__main__":
    main()
