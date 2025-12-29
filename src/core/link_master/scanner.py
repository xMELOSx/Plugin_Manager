""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import os
import logging
from src.core import core_handler

class Scanner:
    def __init__(self):
        self.logger = logging.getLogger("LinkMasterScanner")

    def detect_thumbnail(self, abs_path: str):
        """
        Detects a preview image in the given absolute directory path.
        Returns the filename if found, else None.
        """
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            return None
            
        # Standard candidates
        candidates = [
            "cover.jpg", "cover.png", 
            "preview.jpg", "preview.png",
            "icon.jpg", "icon.png",
            "thumb.jpg", "thumb.png",
            "folder.jpg", "folder.png"
        ]
        
        for img_name in candidates:
            possible_path = os.path.join(abs_path, img_name)
            if os.path.exists(possible_path):
                return img_name
                
        # Phase 28: Fallback to ANY image if no standard candidates found
        try:
            with os.scandir(abs_path) as it:
                for entry in it:
                    if entry.is_file() and entry.name.lower().endswith(('.jpg', '.png', '.jpeg', '.webp')):
                        return entry.name
        except: pass
        
        return None

    def scan_directory(self, root_path: str):
        """
        Scans the given directory for scan-able items.
        Returns a list of dicts suitable for 'items' table insertion.
        Current logic: Treat each subfolder as an item.
        """
        if not os.path.exists(root_path):
            self.logger.warning(f"Scan root not found: {root_path}")
            return []
            
        found_items = []
        try:
            with os.scandir(root_path) as it:
                for entry in it:
                    if entry.is_dir() and not entry.name.startswith(('.', '_Backup')):
                        # Detect preview image
                        image_path = self.detect_thumbnail(entry.path)
                        
                        item = {
                            "name": entry.name,
                            "storage_rel_path": entry.name,
                            "image_rel_path": image_path,
                            "last_updated": None
                        }
                        found_items.append(item)
        except Exception as e:
            self.logger.error(f"Scan failed: {e}")
            
        return found_items
