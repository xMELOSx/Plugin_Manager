""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtCore import QSortFilterProxyModel, Qt, QModelIndex
import os

class SingleFolderProxyModel(QSortFilterProxyModel):
    def __init__(self, target_path=None, parent=None):
        super().__init__(parent)
        self.target_path = os.path.normpath(target_path) if target_path else None

    def set_target_path(self, path):
        if path:
            # Use abspath to resolve relative/mixed paths (. and ..)
            # Use normcase for Windows case insensitivity
            self.target_path = os.path.normcase(os.path.abspath(path))
        else:
            self.target_path = None
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self.target_path:
            return True
        
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        
        raw_path = model.filePath(index)
        path = os.path.normcase(os.path.abspath(raw_path))
        
        # 1. Exact Match
        if path == self.target_path:
            return True
        
        # 2. Descendant (Path is inside Target)
        # e.g. Path: C:\Target\Child, Target: C:\Target
        if path.startswith(self.target_path + os.sep):
            return True
            
        # 3. Ancestor (Target is inside Path) -> MUST ACCEPT so we can reach Target
        # e.g. Path: C:\Parent, Target: C:\Parent\Target
        # Ensure regex-like boundary check
        path_with_sep = path if path.endswith(os.sep) else path + os.sep
        if self.target_path.startswith(path_with_sep):
            return True
            
        return False
