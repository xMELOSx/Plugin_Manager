import sqlite3
import os

# Find all app databases
app_dir = r'c:\Users\xMELOSx\.gemini\antigravity\scratch\Projects\Plugin_Manager\resource\app'

for app_name in os.listdir(app_dir):
    db_path = os.path.join(app_dir, app_name, 'dyonis.db')
    if not os.path.exists(db_path):
        db_path = os.path.join(app_dir, app_name, 'link_master.db')
    
    if os.path.exists(db_path):
        print(f"\n=== {app_name} ===")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            # Find suspect entries (paths starting with ..)
            rows = conn.execute("""
                SELECT rel_path FROM lm_folder_config 
                WHERE rel_path LIKE '%..%' OR rel_path LIKE '%14Folder/Collei%'
                LIMIT 30
            """).fetchall()
            
            for r in rows:
                print(f"  SUSPECT: {r['rel_path']}")
            
            if not rows:
                print("  No suspect entries.")
                
        except Exception as e:
            print(f"  Error: {e}")
        
        conn.close()
