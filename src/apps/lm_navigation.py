""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を経由すること。
"""
"""
Link Master: Navigation Mixin
パンくずリストとパスナビゲーションのロジック。

依存するコンポーネント:
- ClickableLabel (src/ui/link_master/clickable_label.py)

依存する親クラスの属性:
- storage_root: str
- current_view_path, current_path: str
- breadcrumb_layout: QHBoxLayout
- db: LMDatabase
- logger: logging.Logger
- explorer_panel: ExplorerPanel
- app_combo: QComboBox
"""
import os
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

from src.core.link_master.core_paths import get_trash_dir
from src.core.lang_manager import _


class LMNavigationMixin:
    """パンくずリストとパスナビゲーションを担当するMixin。"""
    
    def _get_current_rel_path(self):
        """現在のナビゲーションパスを相対パス（storage_root基準）で取得する。"""
        # Note: current_path は絶対パスとして保持されている想定
        curr = getattr(self, 'current_path', None)
        root = getattr(self, 'storage_root', None)
        if not curr or not root:
            return ""
        try:
            rel = os.path.relpath(curr, root).replace('\\', '/')
            return "" if rel == "." else rel
        except:
            return ""
    
    def _update_breadcrumbs(self, path, active_selection=None):
        """Update breadcrumb trail based on current path."""
        from src.ui.link_master.clickable_label import ClickableLabel
        
        # Clear existing
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Home
        home_lbl = ClickableLabel("Home 🏠", parent=self)
        home_lbl.setStyleSheet("color: #3498db; font-weight: bold; font-size: 14px;")
        
        def on_home_clicked():
            self.current_path = None 
            self._load_items_for_path(self.storage_root, force=True)  # Force refresh to show root packages
            self._clear_selection()

        home_lbl.clicked.connect(on_home_clicked)
        
        # Breadcrumb context menu
        home_lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        home_lbl.customContextMenuRequested.connect(
            lambda pos: self._show_breadcrumb_menu("", home_lbl.mapToGlobal(pos))
        )
        
        self.breadcrumb_layout.addWidget(home_lbl)
        
        # Determine trail
        trail_rel = ""
        target_rel = ""
        
        if path == "" or path == self.storage_root:
            if active_selection and active_selection != self.storage_root:
                try:
                    trail_rel = os.path.relpath(active_selection, self.storage_root).replace('\\', '/')
                    if trail_rel == ".": trail_rel = ""
                    target_rel = trail_rel
                except:
                    trail_rel = ""
                    target_rel = ""
            else:
                self.breadcrumb_layout.addStretch()
                return
        else:
            # Check if path is the Trash folder - show simplified "Root > Trash"
            path_norm = path.replace('\\', '/')
            app_data = self.app_combo.currentData() if hasattr(self, 'app_combo') else None
            if app_data:
                trash_path = get_trash_dir(app_data['name']).replace('\\', '/')
                if path_norm == trash_path or path_norm.startswith(trash_path + '/'):
                    # Simplified breadcrumb for Trash
                    sep_lbl = QLabel(">", self)
                    sep_lbl.setStyleSheet("color: #888; font-size: 13px;")
                    self.breadcrumb_layout.addWidget(sep_lbl)
                    
                    trash_lbl = ClickableLabel(_("Trash"), parent=self)
                    trash_lbl.setStyleSheet("color: #3498db; font-weight: bold; font-size: 13px; text-decoration: underline;")
                    # Capture trash_path with default argument to avoid late binding issue
                    trash_lbl.clicked.connect(lambda checked=False, tp=trash_path: self._load_items_for_path(tp, force=True))
                    
                    # Context menu for Trash breadcrumb
                    trash_lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    trash_lbl.customContextMenuRequested.connect(
                        lambda pos, tp=trash_path, l=trash_lbl: self._show_trash_breadcrumb_menu(tp, l.mapToGlobal(pos))
                    )
                    
                    self.breadcrumb_layout.addWidget(trash_lbl)
                    self.breadcrumb_layout.addStretch()
                    return
            
            try:
                trail_rel = os.path.relpath(path, self.storage_root).replace('\\', '/')
                if trail_rel == ".": trail_rel = ""
                
                if active_selection and active_selection != path:
                    selection_rel = os.path.relpath(active_selection, self.storage_root).replace('\\', '/')
                    if selection_rel == ".": selection_rel = ""
                    if len(selection_rel) > len(trail_rel):
                        trail_rel = selection_rel
                
                target_rel = trail_rel
                    
            except: 
                trail_rel = ""
                target_rel = ""
        
        self.logger.info(f"[Breadcrumb] path={path}, active_selection={active_selection}, trail_rel={trail_rel}")
        
        if trail_rel:
            parts = trail_rel.split('/')
            accumulated = ""
            for i, part in enumerate(parts):
                sep_lbl = QLabel(">", self)
                sep_lbl.setStyleSheet("color: #888; font-size: 13px;")
                self.breadcrumb_layout.addWidget(sep_lbl)
                accumulated = os.path.join(accumulated, part).replace('\\', '/')
                
                # Use display name from DB if available
                config = self.db.get_folder_config(accumulated)
                display_name = (config.get('display_name') if config else None) or part
                
                lbl = ClickableLabel(display_name, parent=self)
                lbl.setStyleSheet("color: #ddd; font-size: 13px;")
                lbl.clicked.connect(lambda checked=False, p=accumulated: 
                                    self._on_breadcrumb_clicked(p))
                
                # Context menu
                lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                lbl.customContextMenuRequested.connect(
                    lambda pos, p=accumulated, l=lbl: self._show_breadcrumb_menu(p, l.mapToGlobal(pos))
                )
                
                self.breadcrumb_layout.addWidget(lbl)
                
                # Highlight target segment
                if target_rel == accumulated:
                    lbl.setStyleSheet("color: #3498db; font-weight: bold; font-size: 13px; text-decoration: underline;")

        self.breadcrumb_layout.addStretch()

    def _on_breadcrumb_clicked(self, rel_path):
        """Navigate to a breadcrumb segment with contextual backtracking."""
        if not self.storage_root: return
        abs_path = os.path.normpath(os.path.join(self.storage_root, rel_path))
        
        if abs_path == self.storage_root:
            self.current_path = None
            self._load_items_for_path(self.storage_root)
            return
        # View the parent so the segment itself is shown as a card
        parent_abs = os.path.dirname(abs_path)
        self._load_items_for_path(parent_abs)
        self._on_category_selected(abs_path)

    def _show_breadcrumb_menu(self, rel_path, global_pos):
        """Show context menu for a breadcrumb segment."""
        menu = self._create_item_context_menu(rel_path)
        if menu:
            menu.exec(global_pos)

    def _show_trash_breadcrumb_menu(self, trash_path, global_pos):
        """Show context menu for Trash breadcrumb segment."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #2b2b2b; color: #ddd; border: 1px solid #444; } "
                           "QMenu::item:selected { background-color: #3d4a59; }")
        
        open_explorer_act = QAction(_("📁 Open in Explorer"), self)
        open_explorer_act.triggered.connect(lambda: os.startfile(trash_path))
        menu.addAction(open_explorer_act)
        
        menu.exec(global_pos)

    def _navigate_to_path(self, path):
        """Called by ItemCard click for directory navigation."""
        if os.path.isdir(path):
            # Phase 28: Skip if already at this path to prevent duplicate scans
            current_view = getattr(self, 'current_view_path', None)
            if current_view:
                # Normalize paths for comparison
                current_normalized = os.path.normpath(current_view).replace('\\', '/')
                path_normalized = os.path.normpath(path).replace('\\', '/')
                if current_normalized == path_normalized:
                    logging.debug(f"Skipping duplicate navigation to: {path}")
                    return
            
            # Safety: Do not navigate into packages
            if self.db and self.storage_root:
                try:
                    rel = os.path.relpath(path, self.storage_root)
                    if rel == ".": rel = ""
                    rel = rel.replace('\\', '/')
                    config = self.db.get_folder_config(rel)
                    sep_count = rel.count('/')
                    default_type = 'category' if (sep_count <= 1) else 'package'
                    folder_type = config.get('folder_type', default_type) if config else default_type
                    
                    detected = self._detect_folder_type(path)
                    if detected == 'package':
                        folder_type = 'package'

                    if folder_type == 'package':
                        self.logger.info(f"Navigation blocked: {rel} is a package. Opening property view.")
                        if hasattr(self, '_show_property_view_for_card'):
                            self._show_property_view_for_card(path)
                        return
                except Exception as e:
                    self.logger.debug(f"Navigation safety check failed: {e}")
                    pass

            # Phase 28: Clear category selection before navigation
            # This prevents the view scan from thinking there's still a contents selection,
            # and avoids duplicate package displays from both view and contents contexts
            self.current_path = None
            self._load_items_for_path(path)
            
            # Sync Explorer Panel
            app_data = self.app_combo.currentData()
            if app_data:
                storage_root = app_data.get('storage_root')
                try:
                    rel_path = os.path.relpath(path, storage_root)
                    if rel_path == ".": rel_path = ""
                    self.explorer_panel.focus_on_path(rel_path)
                except:
                    pass

    def _navigate_back(self):
        """Navigate to the previous path in history."""
        if self.nav_index > 0:
            self.nav_index -= 1
            path = self.nav_history[self.nav_index]
            self._is_navigating_history = True
            self._load_items_for_path(path)
            self._is_navigating_history = False
            self._update_nav_buttons()

    def _navigate_forward(self):
        """Navigate to the next path in history."""
        if self.nav_index < len(self.nav_history) - 1:
            self.nav_index += 1
            path = self.nav_history[self.nav_index]
            self._is_navigating_history = True
            self._load_items_for_path(path)
            self._is_navigating_history = False
            self._update_nav_buttons()

    def _update_nav_buttons(self):
        """Enable/Disable back/forward buttons based on history state."""
        if hasattr(self, 'btn_back'):
            self.btn_back.setEnabled(self.nav_index > 0)
        if hasattr(self, 'btn_forward'):
            self.btn_forward.setEnabled(self.nav_index < len(self.nav_history) - 1)
