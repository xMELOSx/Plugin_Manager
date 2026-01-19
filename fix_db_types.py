
import os
import sqlite3
import glob

def fix_dbs():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    db_pattern = os.path.join(root_dir, "resource", "app", "*", "dyonis.db")
    dbs = glob.glob(db_pattern)
    
    print(f"Found {len(dbs)} databases.")
    
    for db_path in dbs:
        print(f"Checking {db_path}...")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get storage root for this app
            # Storage root is usually in valid_folders or we have to guess relative to DB?
            # Actually, the paths in lm_folder_config are relative to storage_root.
            # We need the storage root to verify existence.
            # But the app config (storage_root) is in the Main Registry (window.json or separate DB).
            # Limitation: We might not know the absolute path easily.
            # However, looking at the paths in the logs: C:/Games Folder/...
            # We can try to deduce it if the relative paths match what's on disk.
            
            # ALTERNATIVE: Just look for folders with subfolders in the known locations?
            # Or assume we can't fully verify disk and just rely on the user's claim?
            # "Because of this, categories were registered as packages"
            # It's better to verify.
            
            # Let's try to get the 'storage_root' from the PARENT folder if possible? No.
            # Let's try to get it from 'lm_apps' table in the MAIN registry if available?
            # We don't know where the main registry is easily without parsing config.
            
            # Workaround: Check if 'rel_path' exists relative to the App Folder? No.
            # We will use a heuristic:
            # If we find a 'package' that has 'rel_path' which looks like a folder (no extension, etc), we flag it.
            # User said "folders added newly".
            
            cursor.execute("SELECT id, rel_path, folder_type FROM lm_folder_config WHERE folder_type='package'")
            rows = cursor.fetchall()
            
            updates = []
            
            # We need the base path.
            # Let's try to find 'window.json' and parse it to find app paths?
            # Too complex for a quick fix.
            
            # Let's just update ALL 'package' items that clearly should be categories based on name?
            # No, that's dangerous.
            
            # Let's assume the user is running this on the machine where paths are valid.
            # We need the App ID to look up in Registry.
            # But we are in the App DB.
            
            # New Plan: We will just update the specific DB for Genshin Impact if we can find the path.
            # "Genshin Impact" folder in resource/app
            if "Genshin Impact" in db_path:
                 # Try to guess storage root from logs? 
                 # C:/Games Folder/Mods File/Genshin Impact 3dmigoto/Mods/SkinSelectImpact
                 storage_root = r"C:/Games Folder/Mods File/Genshin Impact 3dmigoto/Mods/SkinSelectImpact"
                 
                 for row in rows:
                     rel = row['rel_path']
                     full_path = os.path.join(storage_root, rel)
                     
                     if os.path.isdir(full_path):
                         # Check for subdirs
                         try:
                             has_subdirs = any(os.path.isdir(os.path.join(full_path, d)) for d in os.listdir(full_path))
                             if has_subdirs:
                                 print(f"  [FIX] Changing {rel} from package to category (has subdirs).")
                                 updates.append(row['id'])
                         except Exception as e:
                             print(f"  Error checking {full_path}: {e}")

            if updates:
                cursor.executemany("UPDATE lm_folder_config SET folder_type='category' WHERE id=?", [(uid,) for uid in updates])
                conn.commit()
                print(f"  Updated {len(updates)} records in {os.path.basename(db_path)}")
            
            conn.close()
        except Exception as e:
            print(f"Error processing {db_path}: {e}")

if __name__ == "__main__":
    fix_dbs()
