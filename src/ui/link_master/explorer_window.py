from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeView, QPushButton, 
                             QLabel, QHBoxLayout, QMenu, QFrame, QSizeGrip, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QDir
from PyQt6.QtGui import QFileSystemModel, QAction
from src.core.lang_manager import _
import os

from src.ui.link_master.single_folder_proxy import SingleFolderProxyModel
from src.core.link_master.database import get_lm_db

class ExplorerPanel(QWidget):
    path_selected = pyqtSignal(str) # Navigation (Double Click)
    item_clicked = pyqtSignal(str)  # Selection (Single Click)
    config_changed = pyqtSignal()
    request_properties_edit = pyqtSignal(list) # Phase 28: Piping property edit requests (abs_paths)

    def __init__(self, parent=None):
        super().__init__(parent)
        # No Window settings (Title, Resize) needed for Panel
        
        # Data
        self.storage_root = None
        self.current_app_id = None
        self.db = get_lm_db()
        self.context_menu_provider = None # Callback to build menu
        
        # Init UI
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header (Root Info)
        self.header_frame = QFrame()
        self.header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.header_frame.setStyleSheet("QFrame { background-color: #333; border-radius: 4px; } QLabel { color: #eee; font-weight: bold; }")
        
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(4)
        
        self.lbl_info = QLabel(_("Root: Not Selected"))
        self.lbl_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_info.mousePressEvent = self._on_root_label_clicked
        self.lbl_info.setStyleSheet("padding: 2px;")
        header_layout.addWidget(self.lbl_info)
        
        header_layout.addStretch()
        
        # Smart context button / refresh
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedSize(24, 24)
        self.btn_refresh.setFlat(True)
        self.btn_refresh.setToolTip(_("Refresh Tree"))
        self.btn_refresh.setStyleSheet("QPushButton { border: none; color: #888; } QPushButton:hover { color: #fff; background-color: #444; border-radius: 4px; }")
        self.btn_refresh.clicked.connect(lambda: self.fs_model.setRootPath(self.storage_root) if self.storage_root else None)
        header_layout.addWidget(self.btn_refresh)
        
        # Enable Context Menu on Header for Root Config
        self.header_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.header_frame.customContextMenuRequested.connect(self._show_root_context_menu)
        
        layout.addWidget(self.header_frame)
        
        # Tree View
        self.fs_model = QFileSystemModel()
        self.fs_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot)
        
        self.proxy_model = SingleFolderProxyModel()
        self.proxy_model.setSourceModel(self.fs_model)
        
        self.tree = QTreeView()
        self.tree.setStyleSheet("""
            QTreeView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
            }
            QTreeView::item:hover {
                background-color: #3a3a3a;
            }
            QTreeView::item:selected {
                background-color: #4a4a4a;
            }
        """)
        self.tree.setModel(self.proxy_model)
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        # Enable Multi-Selection with Ctrl/Shift
        from PyQt6.QtWidgets import QAbstractItemView
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Hide Size, Type, Date columns
        for i in range(1, 4):
            self.tree.hideColumn(i)
            
        self.tree.clicked.connect(self._on_tree_clicked)
        self.tree.doubleClicked.connect(self._on_tree_double_clicked)
        
        # Context Menu for Tree Items
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        
        layout.addWidget(self.tree)
        
        # Right-edge resize handle (horizontal resize only)
        self._resize_handle = QFrame(self)
        self._resize_handle.setFixedWidth(5)
        self._resize_handle.setCursor(Qt.CursorShape.SizeHorCursor)
        self._resize_handle.setStyleSheet("QFrame { background: #555; } QFrame:hover { background: #777; }")
        self._resize_handle.raise_()
        self._drag_start = None
        self._init_resize_events()
    
    def _init_resize_events(self):
        """Setup mouse events for resize handle."""
        def mouse_press(e):
            self._drag_start = e.globalPosition().toPoint()
            self._start_width = self.width()
        
        def mouse_move(e):
            if self._drag_start:
                delta = e.globalPosition().toPoint().x() - self._drag_start.x()
                # Max width is 95% of parent window
                max_w = int(self.parent().width() * 0.95) if self.parent() else 800
                new_width = max(150, min(max_w, self._start_width + delta))
                self.setFixedWidth(new_width)
        
        def mouse_release(e):
            self._drag_start = None
        
        self._resize_handle.mousePressEvent = mouse_press
        self._resize_handle.mouseMoveEvent = mouse_move
        self._resize_handle.mouseReleaseEvent = mouse_release
    
    def resizeEvent(self, event):
        """Position resize handle at right edge."""
        if hasattr(self, '_resize_handle'):
            self._resize_handle.setGeometry(self.width() - 5, 0, 5, self.height())

    def retranslate_ui(self):
        """Update strings for internationalization."""
        if not self.storage_root:
            self.lbl_info.setText(_("Root: Not Selected"))
        else:
            self.lbl_info.setText(_("Root: {name}").format(name=os.path.basename(self.storage_root)))
        self.btn_refresh.setToolTip(_("Refresh Tree"))


    
    def focus_on_path(self, rel_path: str):
        """Scroll tree and select the folder at the given relative path."""
        if not self.storage_root: return
        
        full_path = os.path.join(self.storage_root, rel_path) if rel_path else self.storage_root
        if not os.path.exists(full_path): return
        
        src_idx = self.fs_model.index(full_path)
        proxy_idx = self.proxy_model.mapFromSource(src_idx)
        
        if proxy_idx.isValid():
            block = self.tree.blockSignals(True)
            self.tree.setCurrentIndex(proxy_idx)
            self.tree.scrollTo(proxy_idx)
            self.tree.blockSignals(block)
        
    def set_storage_root(self, path: str, app_id: int = None, app_name: str = None):
        """Sets the root folder to display and updates DB to app-specific."""
        if not path or not os.path.exists(path):
            self.lbl_info.setText(_("Invalid Root"))
            self.storage_root = None
            return
            
        self.storage_root = path
        self.current_app_id = app_id
        
        # Use app-specific DB (Phase 18.13 fix for tree-card sync)
        if app_name:
            self.db = get_lm_db(app_name)
        
        self.lbl_info.setText(_("Root: {name}").format(name=os.path.basename(path)))
        self.lbl_info.setToolTip(path)
        
        # Init Model (Async)
        self.fs_model.setRootPath(path)
        self.proxy_model.set_target_path(path)
        
        def _on_loaded(loaded_path):
            if loaded_path == path:
                src_idx = self.fs_model.index(path)
                proxy_idx = self.proxy_model.mapFromSource(src_idx)
                self.tree.setRootIndex(proxy_idx)
                try:
                    self.fs_model.directoryLoaded.disconnect(_on_loaded)
                except: pass

        self.fs_model.directoryLoaded.connect(_on_loaded)
        _on_loaded(path)

    def _on_root_label_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.storage_root:
                 self.path_selected.emit("") # Navigate to Root

    def _on_tree_clicked(self, index):
        """Handle selection (Single Click)."""
        # Phase 22: Suppress navigation click if modifiers (Shift/Ctrl) are active
        # This allows ExtendedSelection to work for multi-selection without navigation
        modifiers = QApplication.keyboardModifiers()
        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            return

        rel_path = self._get_rel_path(index)
        if rel_path is not None:
             self.item_clicked.emit(rel_path)

    def _on_tree_double_clicked(self, index):
        """Handle navigation (Double Click)."""
        rel_path = self._get_rel_path(index)
        if rel_path is not None:
             self.path_selected.emit(rel_path)

    def _show_tree_context_menu(self, position):
        selected_indexes = self.tree.selectedIndexes()
        
        # Collect unique rel_paths (filter out duplicates from multi-column selection)
        rel_paths = []
        seen_paths = set()
        for idx in selected_indexes:
            rel_path = self._get_rel_path(idx)
            if rel_path is not None and rel_path not in seen_paths:
                rel_paths.append(rel_path)
                seen_paths.add(rel_path)
        
        if not rel_paths: return
        
        if len(rel_paths) == 1:
            # Single selection - use centralized menu if available
            if self.context_menu_provider:
                menu = self.context_menu_provider(rel_paths[0])
                if menu:
                    menu.exec(self.tree.viewport().mapToGlobal(position))
                    return
            
            # Fallback to internal if no provider
            abs_path = os.path.join(self.storage_root, rel_paths[0])
            self._open_config_menu(rel_paths[0], self.tree.viewport().mapToGlobal(position))
        else:
            # Multiple selection - batch edit menu
            self._open_batch_config_menu(rel_paths, self.tree.viewport().mapToGlobal(position))

    def _show_root_context_menu(self, position):
        if not self.storage_root or not self.current_app_id: return
        
        # Phase 22: Unify root menu with centralized provider
        if self.context_menu_provider:
            menu = self.context_menu_provider("")
            if menu:
                menu.exec(self.header_frame.mapToGlobal(position))
                return
        
        self._open_config_menu("", self.header_frame.mapToGlobal(position), is_root=True)
    
    def _open_batch_config_menu(self, rel_paths, global_pos):
        """Context menu for batch editing multiple folders."""
        if not self.current_app_id: return
        
        from src.ui.link_master.dialogs import FolderPropertiesDialog
        
        menu = QMenu()
        menu.addAction(_("Batch Edit ({count} folders)").format(count=len(rel_paths))).setEnabled(False)
        menu.addSeparator()
        
        # Batch Properties
        abs_paths = [os.path.join(self.storage_root, p) for p in rel_paths]
        act_props = menu.addAction(_("📝 Edit Properties (Batch)"))
        act_props.triggered.connect(lambda: self.request_properties_edit.emit(abs_paths))
        
        menu.addSeparator()
        
        # Quick batch actions
        type_menu = menu.addMenu("Set Type")
        act_pkg = type_menu.addAction("Package")
        act_pkg.triggered.connect(lambda: self._batch_update_type(rel_paths, 'package'))
        act_cat = type_menu.addAction("Category")
        act_cat.triggered.connect(lambda: self._batch_update_type(rel_paths, 'category'))
        
        style_menu = menu.addMenu(_("Set Style"))
        act_img = style_menu.addAction(_("Image Only"))
        act_img.triggered.connect(lambda: self._batch_update_style(rel_paths, 'image'))
        act_txt = style_menu.addAction(_("Text Only"))
        act_txt.triggered.connect(lambda: self._batch_update_style(rel_paths, 'text'))
        act_it = style_menu.addAction(_("Image + Text"))
        act_it.triggered.connect(lambda: self._batch_update_style(rel_paths, 'image_text'))
        
        # Terminal Flag Removed (Phase 12)
        
        menu.exec(global_pos)
    
    def _batch_update_type(self, rel_paths, folder_type):
        for rel_path in rel_paths:
            self.db.update_folder_display_config(rel_path, folder_type=folder_type)
        self.config_changed.emit()
    
    def _batch_update_style(self, rel_paths, display_style):
        for rel_path in rel_paths:
            self.db.update_folder_display_config(rel_path, display_style=display_style)
        self.config_changed.emit()

    def _open_config_menu(self, rel_path, global_pos, is_root=False):
        if not self.current_app_id: return

        # Get Current Config
        config = self.db.get_folder_config(rel_path)
        # Phase 18.11: Level 1 & 2 are Category by default
        sep_count = rel_path.count(os.sep) + rel_path.count("/")
        # Root (empty rel) is also a category
        default_type = 'category' if (sep_count <= 1) else 'package'
        current_type = config.get('folder_type', default_type) if config else default_type
        current_style = config.get('display_style', 'image') if config else 'image'
        
        menu = QMenu()
        label_text = _("Root Folder") if is_root else _("Folder: {name}").format(name=os.path.basename(rel_path))
        menu.addAction(label_text).setEnabled(False)
        menu.addSeparator()
        
        # Type Actions
        type_menu = menu.addMenu(_("Type ({type})").format(type=current_type))
        
        act_pkg = QAction(_("Package (Bottom)"), self)
        act_pkg.setCheckable(True)
        act_pkg.setChecked(current_type == 'package')
        act_pkg.triggered.connect(lambda: self._update_config(rel_path, folder_type='package'))
        type_menu.addAction(act_pkg)
        
        act_cat = QAction(_("Category (Top)"), self)
        act_cat.setCheckable(True)
        act_cat.setChecked(current_type == 'category')
        act_cat.triggered.connect(lambda: self._update_config(rel_path, folder_type='category'))
        type_menu.addAction(act_cat)
        
        # Style Actions (for Categories when drilling down)
        style_menu = menu.addMenu(_("Category Style ({style})").format(style=current_style))
        
        act_img = QAction(_("Image Only"), self)
        act_img.setCheckable(True)
        act_img.setChecked(current_style == 'image')
        act_img.triggered.connect(lambda: self._update_config(rel_path, display_style='image'))
        style_menu.addAction(act_img)
        
        act_txt = QAction(_("Text Only"), self)
        act_txt.setCheckable(True)
        act_txt.setChecked(current_style == 'text')
        act_txt.triggered.connect(lambda: self._update_config(rel_path, display_style='text'))
        style_menu.addAction(act_txt)

        act_it = QAction(_("Image + Text"), self)
        act_it.setCheckable(True)
        act_it.setChecked(current_style == 'image_text')
        act_it.triggered.connect(lambda: self._update_config(rel_path, display_style='image_text'))
        style_menu.addAction(act_it)
        
        # Package Style Actions (for bottom area)
        pkg_style = config.get('display_style_package', 'image') if config else 'image'
        pkg_style_menu = menu.addMenu(_("Package Style ({style})").format(style=pkg_style))
        
        act_pkg_img = QAction(_("Image Only"), self)
        act_pkg_img.setCheckable(True)
        act_pkg_img.setChecked(pkg_style == 'image')
        act_pkg_img.triggered.connect(lambda: self._update_config(rel_path, display_style_package='image'))
        pkg_style_menu.addAction(act_pkg_img)
        
        act_pkg_txt = QAction(_("Text Only"), self)
        act_pkg_txt.setCheckable(True)
        act_pkg_txt.setChecked(pkg_style == 'text')
        act_pkg_txt.triggered.connect(lambda: self._update_config(rel_path, display_style_package='text'))
        pkg_style_menu.addAction(act_pkg_txt)

        act_pkg_it = QAction(_("Image + Text"), self)
        act_pkg_it.setCheckable(True)
        act_pkg_it.setChecked(pkg_style == 'image_text')
        act_pkg_it.triggered.connect(lambda: self._update_config(rel_path, display_style_package='image_text'))
        pkg_style_menu.addAction(act_pkg_it)

        menu.addSeparator()
        
        # Reset Actions (Relocated to Tools tab, only single reset remains as secondary)
        act_reset_this = menu.addAction(_("Reset This Folder Config"))
        act_reset_this.triggered.connect(lambda: self._reset_config(rel_path))
        
        menu.exec(global_pos)
        
    def _reset_config(self, rel_path):
        if not self.current_app_id: return
        self.db.delete_folder_config(rel_path)
        self.config_changed.emit()


    def _update_config(self, rel_path, folder_type=None, display_style=None):
        if not self.current_app_id: return
        # Phase 19.7 Fix: Only pass non-None values to preserve other settings
        kwargs = {}
        if folder_type is not None:
            kwargs['folder_type'] = folder_type
        if display_style is not None:
            kwargs['display_style'] = display_style
        if kwargs:
            self.db.update_folder_display_config(rel_path, **kwargs)
            self.config_changed.emit()

    def _get_rel_path(self, proxy_index):
        if not self.storage_root: return None
        source_index = self.proxy_model.mapToSource(proxy_index)
        path = self.fs_model.filePath(source_index)
        if not path: return None
        
        try:
            rel = os.path.relpath(path, self.storage_root)
            if rel == ".": rel = ""
            return rel
        except ValueError:
            return None
