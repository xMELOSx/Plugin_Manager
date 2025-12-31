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
        Optimized: Get all filenames once with scandir and check against candidates.
        Reduces os.path.exists calls from 10+ per folder to 1 scan.
        """
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            return None
            
        try:
            # Get all filenames at once
            files = set()
            with os.scandir(abs_path) as it:
                for entry in it:
                    if entry.is_file():
                        files.add(entry.name)
            
            # Standard candidates (priority order)
            candidates = [
                "cover.jpg", "cover.png", 
                "preview.jpg", "preview.png",
                "icon.jpg", "icon.png",
                "thumb.jpg", "thumb.png",
                "folder.jpg", "folder.png"
            ]
            
            for img_name in candidates:
                if img_name in files:
                    return img_name
                    
            # Fallback to ANY image
            for filename in files:
                if filename.lower().endswith(('.jpg', '.png', '.jpeg', '.webp')):
                    return filename
        except: pass
        
        return None

    def scan_directory(self, root_path: str):
        """
        Scans the given directory for scan-able items.
        Returns a list of dicts suitable for 'items' table insertion.
        Current logic: Treat each subfolder as an item.
        """
        import time
        t_start = time.perf_counter()
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
            
        t_end = time.perf_counter()
        self.logger.info(f"[ScannerProfile] scan_directory path='{os.path.basename(root_path)}' items={len(found_items)} took {t_end-t_start:.3f}s")
        return found_items
