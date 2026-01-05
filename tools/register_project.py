import sqlite3
import os

DB_PATH = os.path.join("config", "global.db")
PROJECT_ROOT = os.path.abspath(os.getcwd())
# Ensure path format matches what DB expects (forward slashes often safer)
PROJECT_ROOT = PROJECT_ROOT.replace("\\", "/")

def register_project():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute("SELECT id FROM lm_apps WHERE storage_root = ?", (PROJECT_ROOT,))
        if cursor.fetchone():
            print("Project already registered.")
            return

        # Insert new app
        # We need a target root. We'll create a 'dist' folder if it doesn't exist, or just use project root/ignore
        target_root = os.path.join(PROJECT_ROOT, "dist_target").replace("\\", "/")
        if not os.path.exists(target_root):
            os.makedirs(target_root, exist_ok=True)

        sql = '''INSERT INTO lm_apps (name, storage_root, target_root, conflict_policy, deployment_type, is_favorite, score)
                 VALUES (?, ?, ?, 'backup', 'folder', 1, 100)'''
        
        cursor.execute(sql, ("Plugin Manager (Self)", PROJECT_ROOT, target_root))
        conn.commit()
        print(f"Registered 'Plugin Manager (Self)' at {PROJECT_ROOT}")
        
        # Determine the NEW ID
        new_id = cursor.lastrowid
        
        # Set this as the LAST OPENED app so it opens immediately
        conn.execute("INSERT OR REPLACE INTO lm_settings (key, value) VALUES ('last_app_id', ?)", (str(new_id),))
        # Clear path/subpath to ensure root load
        conn.execute("DELETE FROM lm_settings WHERE key LIKE 'last_path_%'")
        conn.execute("DELETE FROM lm_settings WHERE key LIKE 'last_subpath_%'")
        conn.execute("INSERT OR REPLACE INTO lm_settings (key, value) VALUES (?, '1')", (f"last_is_root_{new_id}",))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    register_project()
