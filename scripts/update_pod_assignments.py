#!/usr/bin/env python3
"""
Script to update pod assignments for users and time entries.
This helps populate the pod_assignment field if it's currently empty.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from database.config import engine
from sqlalchemy import text


def show_current_pod_assignments():
    """Display current pod assignment distribution."""
    print("Current Pod Assignment Distribution:")
    print("=" * 50)
    
    query = """
    SELECT 
        COALESCE(pod_assignment, 'Unassigned') as pod,
        COUNT(*) as user_count
    FROM clockify_users 
    WHERE status = 'active'
    GROUP BY COALESCE(pod_assignment, 'Unassigned')
    ORDER BY user_count DESC
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.fetchall()
        
        for row in rows:
            print(f"  {row.pod}: {row.user_count} users")
    
    print()


def update_pod_assignments_interactive():
    """Interactive script to update pod assignments."""
    print("🏢 Pod Assignment Update Tool")
    print("=" * 50)
    
    # Show current assignments
    show_current_pod_assignments()
    
    # Get list of users without pod assignments
    query = """
    SELECT clockify_user_id, name, email, practice_alignment, location
    FROM clockify_users 
    WHERE (pod_assignment IS NULL OR pod_assignment = '') 
    AND status = 'active'
    ORDER BY name
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query))
        unassigned_users = result.fetchall()
    
    if not unassigned_users:
        print("✅ All active users have pod assignments!")
        return
    
    print(f"Found {len(unassigned_users)} users without pod assignments:")
    print()
    
    # Available pods
    available_pods = ['Free Agent', 'Alpha', 'Bravo', 'SurePoint', 'A2Z']
    
    print("Available Pods:")
    for i, pod in enumerate(available_pods, 1):
        print(f"  {i}. {pod}")
    print("  0. Skip this user")
    print()
    
    updates = []
    
    for user in unassigned_users:
        print(f"User: {user.name} ({user.email})")
        print(f"  Practice: {user.practice_alignment}")
        print(f"  Location: {user.location}")
        
        while True:
            try:
                choice = input(f"  Select pod (1-{len(available_pods)}, 0 to skip): ").strip()
                
                if choice == '0':
                    print("  Skipped.")
                    break
                
                pod_index = int(choice) - 1
                if 0 <= pod_index < len(available_pods):
                    selected_pod = available_pods[pod_index]
                    updates.append((user.clockify_user_id, selected_pod))
                    print(f"  ✅ Assigned to {selected_pod}")
                    break
                else:
                    print("  Invalid choice. Please try again.")
            
            except ValueError:
                print("  Please enter a number.")
            except KeyboardInterrupt:
                print("\n\nOperation cancelled.")
                return
        
        print()
    
    # Apply updates
    if updates:
        print(f"Ready to update {len(updates)} user assignments.")
        confirm = input("Apply these changes? (y/N): ").strip().lower()
        
        if confirm == 'y':
            with engine.begin() as conn:
                for user_id, pod in updates:
                    # Update user record
                    conn.execute(text("""
                        UPDATE clockify_users 
                        SET pod_assignment = :pod, updated_at = NOW()
                        WHERE clockify_user_id = :user_id
                    """), {"pod": pod, "user_id": user_id})
                    
                    # Update time entries (for future entries, past entries keep historical assignment)
                    conn.execute(text("""
                        UPDATE clockify_detailed_time_entries 
                        SET pod_assignment = :pod
                        WHERE clockify_user_id = :user_id
                        AND entry_date >= CURRENT_DATE - INTERVAL '7 days'
                    """), {"pod": pod, "user_id": user_id})
            
            print(f"✅ Updated {len(updates)} pod assignments!")
            print("\nUpdated distribution:")
            show_current_pod_assignments()
        else:
            print("Changes cancelled.")
    else:
        print("No updates to apply.")


def bulk_update_by_pattern():
    """Bulk update pod assignments based on patterns."""
    print("🔄 Bulk Pod Assignment Update")
    print("=" * 50)
    
    # Example patterns - customize based on your organization
    patterns = [
        {
            'name': 'Assign all unassigned to Free Agent',
            'condition': "(pod_assignment IS NULL OR pod_assignment = '')",
            'pod': 'Free Agent'
        },
        {
            'name': 'Assign by practice alignment',
            'condition': "practice_alignment LIKE '%Cloud%' AND (pod_assignment IS NULL OR pod_assignment = '')",
            'pod': 'Alpha'
        }
    ]
    
    print("Available bulk update patterns:")
    for i, pattern in enumerate(patterns, 1):
        print(f"  {i}. {pattern['name']}")
    print("  0. Cancel")
    print()
    
    try:
        choice = int(input("Select pattern: ").strip())
        
        if choice == 0:
            return
        
        if 1 <= choice <= len(patterns):
            pattern = patterns[choice - 1]
            
            # Preview the update
            preview_query = f"""
            SELECT name, email, practice_alignment, location
            FROM clockify_users 
            WHERE {pattern['condition']} AND status = 'active'
            """
            
            with engine.connect() as conn:
                result = conn.execute(text(preview_query))
                affected_users = result.fetchall()
            
            if not affected_users:
                print("No users match this pattern.")
                return
            
            print(f"\nThis will assign {len(affected_users)} users to '{pattern['pod']}':")
            for user in affected_users[:10]:  # Show first 10
                print(f"  - {user.name} ({user.email})")
            
            if len(affected_users) > 10:
                print(f"  ... and {len(affected_users) - 10} more")
            
            confirm = input(f"\nAssign all {len(affected_users)} users to '{pattern['pod']}'? (y/N): ").strip().lower()
            
            if confirm == 'y':
                update_query = f"""
                UPDATE clockify_users 
                SET pod_assignment = :pod, updated_at = NOW()
                WHERE {pattern['condition']} AND status = 'active'
                """
                
                with engine.begin() as conn:
                    result = conn.execute(text(update_query), {"pod": pattern['pod']})
                    
                    # Also update recent time entries
                    time_entry_query = f"""
                    UPDATE clockify_detailed_time_entries 
                    SET pod_assignment = :pod
                    WHERE clockify_user_id IN (
                        SELECT clockify_user_id FROM clockify_users 
                        WHERE pod_assignment = :pod AND status = 'active'
                    )
                    AND entry_date >= CURRENT_DATE - INTERVAL '7 days'
                    """
                    conn.execute(text(time_entry_query), {"pod": pattern['pod']})
                
                print(f"✅ Updated {result.rowcount} users!")
                show_current_pod_assignments()
            else:
                print("Update cancelled.")
        else:
            print("Invalid choice.")
    
    except ValueError:
        print("Please enter a number.")
    except KeyboardInterrupt:
        print("\nOperation cancelled.")


def main():
    """Main function to run pod assignment updates."""
    print("🎯 Pod Assignment Management Tool")
    print("=" * 50)
    print("1. Interactive assignment (assign users one by one)")
    print("2. Bulk assignment (assign multiple users at once)")
    print("3. Show current assignments")
    print("0. Exit")
    print()
    
    try:
        choice = input("Select option: ").strip()
        
        if choice == '1':
            update_pod_assignments_interactive()
        elif choice == '2':
            bulk_update_by_pattern()
        elif choice == '3':
            show_current_pod_assignments()
        elif choice == '0':
            print("Goodbye!")
        else:
            print("Invalid choice.")
    
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()