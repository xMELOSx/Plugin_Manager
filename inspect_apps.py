import sqlite3
import os

DB_PATH = os.path.join("config", "global.db")

def check_apps():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM lm_apps")
        apps = [dict(row) for row in cursor.fetchall()]
        
        print(f"Found {len(apps)} apps.")
        for app in apps:
            print(f"ID: {app['id']}, Name: {app['name']}, Path: {app['storage_root']}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_apps()
