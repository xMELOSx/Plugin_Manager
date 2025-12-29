from PyQt6.QtCore import QThread, pyqtSignal
import os
import datetime
from src.core.link_master.utils import get_package_size_fast

class SizeScannerWorker(QThread):
    """バックグラウンドでパッケージ容量を計算するワーカースレッド"""
    progress = pyqtSignal(int, int) # current, total
    finished_item = pyqtSignal(str, int) # rel_path, size
    all_finished = pyqtSignal()

    def __init__(self, db, storage_root, paths_to_scan=None):
        super().__init__()
        self.db = db
        self.storage_root = storage_root
        self.paths_to_scan = paths_to_scan # List of rel_paths, if None, scans all
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        if self.paths_to_scan is None:
            # Get all configurations to find packages
            configs = self.db.get_all_folder_configs()
            self.paths_to_scan = list(configs.keys())

        total = len(self.paths_to_scan)
        for i, rel_path in enumerate(self.paths_to_scan):
            if not self._is_running:
                break
            
            abs_path = os.path.join(self.storage_root, rel_path)
            if os.path.isdir(abs_path):
                size = get_package_size_fast(abs_path)
                now = datetime.datetime.now().isoformat()
                
                # Update DB immediately
                self.db.update_folder_display_config(rel_path, size_bytes=size, scanned_at=now)
                
                self.finished_item.emit(rel_path, size)
            
            self.progress.emit(i + 1, total)

        self.all_finished.emit()
