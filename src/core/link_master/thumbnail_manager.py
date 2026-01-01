""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import os
import logging
import hashlib
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, QSize, Qt
from PyQt6.QtGui import QImage

class ThumbnailGenWorker(QRunnable):
    def __init__(self, source_path: str, target_path: str, target_size: QSize):
        super().__init__()
        self.source_path = source_path
        self.target_path = target_path
        self.target_size = target_size

    def run(self):
        try:
            # Ensure target directory exists
            target_dir = os.path.dirname(self.target_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
                
            image = QImage(self.source_path)
            if not image.isNull():
                # Scale smoothly
                scaled = image.scaled(self.target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                scaled.save(self.target_path, "JPG", 90)
        except Exception as e:
            logging.getLogger("ThumbnailGenWorker").error(f"Failed to generate thumbnail: {e}")

class ThumbnailManager(QObject):
    def __init__(self, resource_root: str):
        super().__init__()
        self.logger = logging.getLogger("ThumbnailManager")
        self.resource_root = resource_root # should be ProjectRoot/resource/app
        # Ensure base dir
        if not os.path.exists(self.resource_root):
            os.makedirs(self.resource_root, exist_ok=True)
            
        self.thread_pool = QThreadPool()
        self.target_size = QSize(256, 256) # Standard square thumbnail size

    def get_thumbnail_path(self, app_name: str, rel_path: str) -> str:
        """
        Returns the absolute path where the thumbnail SHOULD be.
        rel_path is assumed to be the item's path relative to storage_root.
        """
        # Santize app_name generic safe
        safe_app_name = "".join([c for c in app_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        
        # Flatten rel_path: e.g. "Category/Item" -> "Category_Item"
        # Using hash for very long paths could be safer, but readable is nice.
        # Let's use a hybrid or just flattened if short enough.
        
        flat_name = rel_path.replace(os.sep, "_").replace("/", "_").replace("\\", "_")
        
        # Prevent too long filenames
        if len(flat_name) > 100:
            # use hash
            hash_str = hashlib.md5(rel_path.encode('utf-8')).hexdigest()
            flat_name = f"{flat_name[:50]}_{hash_str}"
            
        filename = f"{flat_name}.jpg"
        target_dir = os.path.join(self.resource_root, safe_app_name, "thumbnail")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, filename)

    def queue_generation(self, source_path: str, app_name: str, rel_path: str):
        """
        Queues a task to generate a thumbnail from source_path.
        """
        if not source_path or not os.path.exists(source_path):
            return
            
        target_path = self.get_thumbnail_path(app_name, rel_path)
        
        # Don't regenerate if already exists (double check, though caller might have checked)
        if os.path.exists(target_path):
            return
            
        worker = ThumbnailGenWorker(source_path, target_path, self.target_size)
        self.thread_pool.start(worker)

