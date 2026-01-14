""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMenu, QFrame, QSizePolicy, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRectF, QMimeData, QRect, QPoint, QTimer, QThreadPool
from PyQt6.QtGui import QPixmap, QCursor, QPainter, QPen, QColor, QDragEnterEvent, QDropEvent, QIcon, QBrush, QFont, QAction, QPalette
import os
import shutil
import logging
from PyQt6 import sip
from src.core.lang_manager import _

from .item_card_utils import AsyncScaler
from .item_card_style import get_card_colors, get_card_stylesheet, COLOR_HIDDEN, COLOR_NORMAL_TEXT
from .item_card_overlays import update_overlays_geometry
from .card_overlays import (
    StarOverlay, UrlOverlay, LibOverlay, DeployOverlay, 
    CardBorderPainter, ThumbnailWidget, ElidedLabel
)

logger = logging.getLogger(__name__)

# Load debug settings from file at class definition time
def _load_debug_settings_at_startup():
    import os, json
    try:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        path = os.path.join(base, 'resource', 'debug_settings.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('allow_folder_deploy_pkg_view', True)
    except:
        pass
    return True  # Default to True

_STARTUP_FOLDER_DEPLOY_VALUE = _load_debug_settings_at_startup()

class ItemCard(QFrame):
    # Static Debug Flag
    SHOW_HITBOXES = False
    ALLOW_FOLDER_DEPLOY_IN_PKG_VIEW = _STARTUP_FOLDER_DEPLOY_VALUE
    image_ready_signal = pyqtSignal(str) # Async image ready signal

    # Profiling counters
    _total_style_time = 0.0
    _style_count = 0

    _pool = QThreadPool.globalInstance()
    _total_scale_time = 0.0
    _scale_count = 0
    _last_request_id = 0

    clicked = pyqtSignal(str) # Emits on Double Click (Nav) - Legacy/Alias
    single_clicked = pyqtSignal(str) # Emits on Single Click (Selection)
    selection_changed = pyqtSignal(str, bool) # Emits path, is_selected
    double_clicked = pyqtSignal(str) # Alias for Nav
    deploy_changed = pyqtSignal()  # Emits when link is deployed/removed (for parent refresh)
    property_changed = pyqtSignal(dict) # Phase 30: Emits when a property like favorite changes
    request_deployment_toggle = pyqtSignal(str, bool) # Phase 30: Direct deployment from card (path, is_package)
    request_move_to_unclassified = pyqtSignal(str) # Emits path
    request_move_to_trash = pyqtSignal(str)        # Emits path
    request_restore = pyqtSignal(str)              # Phase 18.11: Emits path
    request_reorder = pyqtSignal(str, str)         # New: path, "top" or "bottom"
    request_edit_properties = pyqtSignal(str)      # Phase 28: Alt+Double-Click -> Edit Properties
    request_focus_library = pyqtSignal(str)        # Phase 32: Focus library in library tab
    request_redeploy = pyqtSignal(str)             # Phase 51: Partial -> Redeploy
    def __init__(self, name: str, path: str, image_path: str = None, loader = None,
                 deployer = None, target_dir: str = None, parent=None,
                 storage_root: str = None, db = None,
                 is_package: bool = False, target_override: str = None,
                 deployment_rules: str = None, manual_preview_path: str = None,
                 app_name: str = None, thumbnail_manager = None, is_registered: bool = True,
                 is_misplaced: bool = False, is_trash_view: bool = False, is_hidden: bool = False, is_partial: bool = False,
                 deploy_type: str = 'folder', conflict_policy: str = 'backup',
                 app_deploy_default: str = 'folder', app_conflict_default: str = 'backup',
                 app_cat_style_default: str = 'image', app_pkg_style_default: str = 'image',
                 show_link: bool = True, show_deploy: bool = True,
                 deploy_button_opacity: float = 0.8,
                 is_library: int = 0, lib_name: str = '', is_intentional: bool = False, **kwargs):
        super().__init__(parent)
        self.setObjectName("ItemCard")
        self.path = path # Source Path (Absolute)
        self.norm_path = (path or "").replace('\\', '/')
        self.folder_name = os.path.basename(path) # Physical folder name for links
        self.display_name = name # Display name from config or folder name
        self.loader = loader
        self.deployer = deployer
        self.target_dir = target_dir
        self.target_override = target_override
        self.deployment_rules = deployment_rules
        self.deploy_rule = deployment_rules # Direct alias for check_link_status
        self.deploy_type = deploy_type # Phase 18.15 (Resolved)
        self.conflict_policy = conflict_policy # Phase 18.15 (Resolved)
        self.app_deploy_default = app_deploy_default # Phase 18.15
        self.app_conflict_default = app_conflict_default # Phase 18.15
        self.app_cat_style_default = app_cat_style_default
        self.app_pkg_style_default = app_pkg_style_default

        self.deploy_type = deploy_type # Phase 18.15
        self.conflict_policy = conflict_policy # Phase 18.15
        self.manual_preview_path = manual_preview_path
        self.storage_root = storage_root
        self.db = db
        self.app_name = app_name
        self.thumbnail_manager = thumbnail_manager
        self.is_selected = False
        self.is_focused = False
        self.is_hovered = False # Phase 4: Manual hover tracking for inner border
        self.is_package = is_package  # Package folders don't navigate on double-click
        self.is_registered = is_registered
        self.is_misplaced = is_misplaced # Pink mark if True
        self.is_trash_view = is_trash_view # Phase 18.11
        self.is_hidden = is_hidden  # Phase 18.14: Hidden folder (gray text)
        self.is_partial = is_partial # Feature 6: Yellow mark if True
        self.is_intentional = is_intentional
        self.link_status = 'none' # 'none', 'linked', 'conflict'
        self.has_linked_children = False  # True if any child is linked
        self.has_unlinked_children = False # NEW: True if any child is unlinked
        self.has_partial_children = False # True if any child is partial
        self.has_favorite = False  # True if any child is favorited (hierarchical)
        self.has_conflict_children = False  # True if any child has conflict
        self.has_logical_conflict = False
        self.has_physical_conflict = False
        self.conflict_tag = None
        self.conflict_scope = 'disabled'
        self.is_library_alt_version = False  # True if another version of same library is deployed
        self.is_library = is_library  # Phase 30: Library flag (from DB, 0 or 1)
        self.lib_name = lib_name   # Phase 30: Library name for grouping
        self.has_category_conflict = False # Phase 35: Category deployment blocked by logic conflict
        self.missing_samples = [] # Phase 51: Sampled missing files for Partial status
        self.is_intentional = False # Phase 51: Intentional partial (Custom/Tree)
        self.has_intentional_children = False # Hierarchy variant

        # Phase 31: Visibility Toggles (Per mode)
        self.show_link_overlay = show_link
        self.show_deploy_btn = show_deploy
        self._deploy_btn_opacity = deploy_button_opacity

        self.setFixedSize(160, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 2)  # Top margin for selection border visibility

        # thumbnail - Using ThumbnailWidget component
        self.thumb_label = ThumbnailWidget(self)
        self.thumb_label.setFixedSize(140, 120)
        self.thumb_label.setTargetSize(QSize(140, 120))
        self.thumb_label.setStyleSheet("background-color: #222; border-radius: 4px; border: 1px solid #333;")

        self.setMouseTracking(True)
        self.image_ready_signal.connect(self._register_dropped_image)
        # Async Load
        if image_path and loader:
            self.thumb_label.loadFromPath(image_path, loader, QSize(256, 256))

        # Name - Using ElidedLabel component
        self.name_label = ElidedLabel(self.display_name, self)
        name_color = "#888" if self.is_hidden else "#ddd"  # Phase 18.14: Gray for hidden
        self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")

        # Phase 24 Fix: Top-fixed layout (image at top, text below, no vertical centering)
        # This ensures image position is stable regardless of text length.
        layout.addWidget(self.thumb_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        layout.addStretch()  # Push content to top

        # Star Overlay - Using component
        self.star_overlay = StarOverlay(self)

        # URL Overlay - Using component
        self.url_overlay = UrlOverlay(self)
        self.url_overlay.clicked.connect(self._open_first_working_url)

        # Library Overlay - Using component
        self.lib_overlay = LibOverlay(self)
        self.lib_overlay.clicked.connect(lambda: self.request_focus_library.emit(getattr(self, 'lib_name', '')))

        # Phase 30: Deploy Toggle Overlay - Using component
        self.deploy_btn = DeployOverlay(self)
        self.deploy_btn.clicked.connect(self.toggle_deployment)

        # Phase 28: Enable drag-drop for thumbnail images
        self.setAcceptDrops(True)

        # Favorite & URL indicators (initialize as False/empty, updated via update_data)
        self.is_favorite = False
        self.score = 0
        self.has_urls = False
        self.url_list = '[]'

        # Phase 1.1.7: Async tracking
        self._current_scale_id = 0
        self.missing_samples = []

        self._check_link_status()
        self._update_name_label()
        self._update_style()
        self._update_icon_overlays()  # Initialize icon visibility

    def toggle_deployment(self, path=None, is_package=None):
        """Phase 30: Direct deployment trigger from card button or public API."""
        if not self.deployer: return
        
        # Phase 51: Handle Partial Status with Warning Dialog
        if self.link_status == 'partial':
            from src.ui.common_widgets import FramelessMessageBox
            msg = FramelessMessageBox(self.window() if hasattr(self, 'window') else self)
            msg.setWindowTitle(_("Partial Deployment"))
            msg.setIcon("Warning")
            
            # Phase 51: Improved Partial Deployment Dialog with Ratio and Japanese snippets
            base_txt = _("This item is partially deployed (some files missing).")
            
            # Show the deployment ratio (e.g. "12 / 15 items deployed")
            counts_txt = _("{found} / {total} items deployed").format(
                found=getattr(self, 'files_found', 0), total=getattr(self, 'files_total', 0)
            )
            
            msg_content = f"{base_txt}\n\n{counts_txt}"
            
            missing_samples = getattr(self, 'missing_samples', [])
            if missing_samples:
                # Japanese translation fallback for the missing items label
                missing_label = _("Missing items:")
                samples = "\n".join([f"- {s}" for s in missing_samples])
                msg_content += f"\n\n{missing_label}\n{samples}"
            
            msg.setText(msg_content)
            
            # Safe codes to prevent "X" (0) from triggering redeploy
            REDEPLOY = 10
            UNLINK = 20
            CANCEL = 30
            
            msg.addButton(_("⚠ Re-deploy (Repair)"), REDEPLOY, "Blue")
            msg.addButton(_("🔗 Unlink (Remove Safe)"), UNLINK, "Red")
            msg.addButton(_("Cancel"), CANCEL, "Gray")
            
            res = msg.exec()
            if res == REDEPLOY:
                self.request_redeploy.emit(self.path)
            elif res == UNLINK:
                self.request_deployment_toggle.emit(self.path, self.is_package)
            return
        
        # If this is a category (folder) but we are in Package View, 
        # it might be allowed to deploy as a package via debug flag.
        is_acting_as_package = is_package if is_package is not None else self.is_package
        if not is_acting_as_package:
             if getattr(ItemCard, 'ALLOW_FOLDER_DEPLOY_IN_PKG_VIEW', False):
                  is_acting_as_package = True
        
        # Emit signal to parent with path and type. 
        # Window's LMDeploymentOpsMixin should catch this and run unified logic.
        target_path = path if path else self.path
        self.request_deployment_toggle.emit(target_path, is_acting_as_package)


    def _calculate_has_urls(self, url_list_raw):
        """Helper to determine if an item has valid, active URLs."""
        if not url_list_raw or url_list_raw in ('[]', '""', 'null', '{}'):
            return False
            
        try:
            import json
            parsed = json.loads(url_list_raw)
            if isinstance(parsed, list):
                # Valid if at least one entry has a non-empty URL
                return any((item.get('url', '').strip() if isinstance(item, dict) else str(item).strip()) 
                           for item in parsed)
            elif isinstance(parsed, dict):
                # Handle {"urls": [...]} or similar
                urls = parsed.get('urls', [])
                if not urls and 'url' in parsed: # Single URL legacy dict
                    return bool(parsed.get('url', '').strip())
                return any(u.get('url', '').strip() for u in urls if isinstance(u, dict))
            return bool(parsed)
        except:
            return False # Conservative fallback

    def update_data(self, **kwargs):
        """Phase 28: Reuse widget by updating its data without reconstruction."""
        if sip.isdeleted(self):
            return

        import logging
        if 'link_status' in kwargs:
             logging.getLogger("ItemCard").debug(f"[UpdateData] {os.path.basename(kwargs.get('path', self.path))} status={kwargs['link_status']} cat_deploy={kwargs.get('category_deploy_status')}")

        # 1. Update Core Data & Context
        old_path = self.path
        if 'path' in kwargs:
            self.path = kwargs['path']
            self.folder_name = os.path.basename(self.path.rstrip('\\/'))
        
        self.target_dir = kwargs.get('target_dir', self.target_dir)
        self.storage_root = kwargs.get('storage_root', self.storage_root)

        # Support 'name' and 'display_name' with robust fallback
        if 'display_name' in kwargs or 'name' in kwargs:
            self.display_name = kwargs.get('display_name') or kwargs.get('name') or self.folder_name
            # Ensure display_name is updated in the card state immediately
            if 'name' in kwargs and 'display_name' not in kwargs:
                kwargs['display_name'] = kwargs['name']
        elif self.path != old_path:
            # If path changed and no name provided, reset to folder name
            self.display_name = self.folder_name

        # 2. Update Session Managers (Optional but safer)
        if 'loader' in kwargs: self.loader = kwargs['loader']
        if 'deployer' in kwargs: self.deployer = kwargs['deployer']
        if 'db' in kwargs: self.db = kwargs['db']
        if 'thumbnail_manager' in kwargs: self.thumbnail_manager = kwargs['thumbnail_manager']
        
        if 'context' in kwargs:
             self.context = kwargs['context']

        if 'folder_type' in kwargs:
            self.is_package = (kwargs['folder_type'] == 'package')
        elif 'is_package' in kwargs:
            self.is_package = bool(kwargs['is_package'])

        self.is_registered = kwargs.get('is_registered', getattr(self, 'is_registered', True))
        self.is_misplaced = kwargs.get('is_misplaced', getattr(self, 'is_misplaced', False))
        self.is_partial = kwargs.get('is_partial', getattr(self, 'is_partial', False))
        self.is_trash_view = kwargs.get('is_trash_view', getattr(self, 'is_trash_view', False))
        self.missing_samples = kwargs.get('missing_samples', getattr(self, 'missing_samples', []))
        self.files_found = kwargs.get('files_found', getattr(self, 'files_found', 0))
        self.files_total = kwargs.get('files_total', getattr(self, 'files_total', 0))
        self.is_intentional = kwargs.get('is_intentional', getattr(self, 'is_intentional', False))

        # Support 'is_visible' (0/1) mapping to 'is_hidden'
        if 'is_visible' in kwargs:
            self.is_hidden = (kwargs['is_visible'] == 0)
        else:
            self.is_hidden = kwargs.get('is_hidden', getattr(self, 'is_hidden', False))

        # Core Conflict Flags (Preserve during pinpoint updates if not provided)
        self.link_status = kwargs.get('link_status', getattr(self, 'link_status', 'none'))
        self.category_deploy_status = kwargs.get('category_deploy_status', getattr(self, 'category_deploy_status', None))
        self.has_physical_conflict = (self.link_status == 'conflict')

        # Support multiple keywords for logical/tag conflicts
        incoming_logical = kwargs.get('has_logical_conflict')
        if incoming_logical is None:
            incoming_logical = kwargs.get('has_conflict')
        if incoming_logical is None:
            incoming_logical = kwargs.get('has_tag_conflict')

        self.has_logical_conflict = bool(incoming_logical) if incoming_logical is not None else getattr(self, 'has_logical_conflict', False)

        # If successfully linked, clear any persistent logical conflict marker
        if self.link_status == 'linked':
            self.has_logical_conflict = False

        self.has_name_conflict = kwargs.get('has_name_conflict', getattr(self, 'has_name_conflict', False))
        self.has_target_conflict = kwargs.get('has_target_conflict', getattr(self, 'has_target_conflict', False))

        # Child Status Flags (Folders)
        self.has_linked_children = kwargs.get('has_linked', getattr(self, 'has_linked_children', False))
        self.has_unlinked_children = kwargs.get('has_unlinked', getattr(self, 'has_unlinked_children', False))
        self.has_partial = kwargs.get('has_partial', getattr(self, 'has_partial_children', False)) # This is for children, not self.is_partial
        self.has_favorite = kwargs.get('has_favorite', getattr(self, 'has_favorite', False))
        self.has_conflict_children = kwargs.get('has_conflict_children', getattr(self, 'has_conflict_children', False))
        
        # Category Deploy Status (for deep blue border)
        self.category_deploy_status = kwargs.get('category_deploy_status', getattr(self, 'category_deploy_status', None))
        self.has_category_conflict = kwargs.get('has_category_conflict', getattr(self, 'has_category_conflict', False))

        # 4. Update Config/Rules
        self.target_override = kwargs.get('target_override', self.target_override)
        self.deployment_rules = kwargs.get('deployment_rules', self.deployment_rules)
        self.manual_preview_path = kwargs.get('manual_preview_path', self.manual_preview_path)
        # 4. Standardized Rule Resolution for UI state
        deploy_rule = kwargs.get('deploy_rule')
        if not deploy_rule or deploy_rule in ("default", "inherit"):
            # Fallback to legacy deploy_type if set
            legacy_type = kwargs.get('deploy_type')
            if legacy_type and legacy_type != 'folder':
                deploy_rule = legacy_type
            else:
                deploy_rule = getattr(self, 'app_deploy_default', 'folder')
        
        self.deploy_type = deploy_rule
        self.conflict_policy = kwargs.get('conflict_policy', self.conflict_policy)

        # Phase 28 Fix: Store conflict tag data specifically for UI Red Line logic
        self.conflict_tag = kwargs.get('conflict_tag', getattr(self, 'conflict_tag', None))
        self.conflict_scope = kwargs.get('conflict_scope', getattr(self, 'conflict_scope', 'disabled'))

        # Favorite & URL indicators
        self.is_favorite = bool(kwargs.get('is_favorite', getattr(self, 'is_favorite', False)))
        self.score = kwargs.get('score', getattr(self, 'score', 0)) or 0

        # Phase 1.1.7: More robust URL detection (Consolidated)
        # BUG FIX: If 'url_list' is not provided in a pinpoint update, keep current has_urls.
        # But if it IS provided, we MUST update has_urls and overlay.
        if 'url_list' in kwargs:
            self.url_list = kwargs.get('url_list', '[]') or '[]'
            self.has_urls = self._calculate_has_urls(self.url_list)
        elif 'url' in kwargs: # Legacy single URL field support
            self.url_list = f'["{kwargs["url"]}"]' if kwargs['url'] else '[]'
            self.has_urls = bool(kwargs['url'])
        else:
            # Pinpoint update, preserve current url_list/has_urls if not changed
            # But ensure has_urls matches current self.url_list just in case
            if not hasattr(self, 'has_urls'):
                self.has_urls = self._calculate_has_urls(getattr(self, 'url_list', '[]'))

        # Phase 30: Synchronize Library info
        self.is_library = kwargs.get('is_library', getattr(self, 'is_library', 0))
        self.lib_name = kwargs.get('lib_name', getattr(self, 'lib_name', ''))
        self.is_library_alt_version = kwargs.get('is_library_alt_version', getattr(self, 'is_library_alt_version', False))

        # Phase 1.0.9: Store raw data for Quick View Manager
        if 'tags_raw' in kwargs:
            self.tags_raw = kwargs.get('tags_raw', '')
        elif 'tags' in kwargs:
            # Sync 'tags' (from dialogs) to 'tags_raw' (for QuickViewManager source)
            self.tags_raw = kwargs.get('tags', '')

        if 'image_path' in kwargs:
            self.image_path_raw = kwargs.get('image_path', '')

        # Phase 31: Visibility Toggles & Opacity
        self.show_link_overlay = kwargs.get('show_link', getattr(self, 'show_link_overlay', True))
        self.show_deploy_btn = kwargs.get('show_deploy', getattr(self, 'show_deploy_btn', True))
        self._deploy_btn_opacity = kwargs.get('deploy_button_opacity', getattr(self, '_deploy_btn_opacity', 0.8))

        # 4. Reset Interaction State (ALWAYS reset when card is reused for a different path)
        if self.path != old_path:
            self.is_selected = False
            self.is_focused = False

        # 5. Update UI Labels (style/overlays deferred to set_card_params for performance)
        self._update_name_label()

        # 6. Image Update (ALWAYS process to prevent stale images from pooled cards)
        # BUG FIX: Only update or clear if 'image_path' is explicitly provided in kwargs.
        # If it's missing, we are doing a pinpoint update (e.g. link toggle) and should preserve current image.
        if 'image_path' in kwargs:
            new_image_path = kwargs.get('image_path')
            old_image_path = getattr(self, '_current_image_path', None)

            # Phase 33: CRITICAL - Always update the expected path FIRST
            # This is used to validate async callbacks
            self._current_image_path = new_image_path

            # Phase 33: CRITICAL - Always clear old image immediately when path changes
            # This prevents "ghost images" from appearing in empty slots
            if new_image_path != old_image_path:
                self.thumb_label.clear()
                self._original_pixmap = None

            if new_image_path:
                if new_image_path != old_image_path and self.loader:
                    self.thumb_label.setText(_("Loading..."))
                    # Phase 33: Use request validator to prevent stale image callbacks
                    expected_path = new_image_path  # Capture for closure
                    def validate_request():
                        return getattr(self, '_current_image_path', None) == expected_path
                    
                    self.loader.load_image(new_image_path, QSize(256, 256), self.set_pixmap, validate_request)
                # If same path, keep existing pixmap (no-op)
            else:
                # Explicitly No image: Clear any existing pixmap
                self.thumb_label.setText(_("No Image"))
                self.thumb_label.setPixmap(QPixmap())
                self._original_pixmap = None  # Phase 28: Clear cached pixmap
        else:
            # pinpoint update: image is already set, just ensure it's re-scaled if needed (handled in update_data tail)
            pass

        # 7. Refresh Detection
        if 'link_status' not in kwargs:
            self._check_link_status()

        # 8. Force Style/Overlay Update (Fixes 'Ghost' state)
        if hasattr(self, 'favorite_btn'):
            self.favorite_btn.setChecked(self.is_favorite)
        if hasattr(self, 'score_dial'):
            self.score_dial.setValue(self.score)

        self._update_style()
        self._update_icon_overlays()
        self.update() # Phase 4955: Force repaint to prevent update lag in batch operations


    def _check_link_status(self):
        if not self.deployer: return
        
        # Phase 14/33: Categories derive status from children, NOT from physical symlink check
        # Physical check on a category folder would return 'none' and wipe its orange/green frame.
        # Phase 33.5: If in 'contents' context, we treat EVERYTHING like a package for detection.
        force_pkg_check = getattr(self, 'context', None) == 'contents'
        if not getattr(self, 'is_package', True) and not force_pkg_check:
             return

        # Final rule resolution for detection
        deploy_rule = self.deploy_type
        if deploy_rule == 'flatten': deploy_rule = 'files'

        target_link = None
        if self.target_override:
            target_link = self.target_override
        elif deploy_rule == 'files' and self.target_dir:
            target_link = self.target_dir
        elif deploy_rule == 'tree' and self.target_dir:
            # Reconstruct hierarchy
            import json
            skip_val = 0
            if self.deployment_rules:
                try:
                    rules_obj = json.loads(self.deployment_rules)
                    skip_val = int(rules_obj.get('skip_levels', 0))
                except: pass
            
            try:
                item_rel = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
                if item_rel == ".": item_rel = ""
                parts = item_rel.split('/')
                if len(parts) > skip_val:
                    mirrored = "/".join(parts[skip_val:])
                    target_link = os.path.join(self.target_dir, mirrored)
                else:
                    target_link = self.target_dir
            except:
                target_link = os.path.join(self.target_dir, self.folder_name)
        elif self.target_dir:
            target_link = os.path.join(self.target_dir, self.folder_name)
        
        if not target_link: return
        
        # Determine transfer_mode for Physical Tree detection
        transfer_mode = 'symlink'
        if self.db:
            try:
                # 1. Check self config first (though usually inheritance handles it)
                # But ItemCard props might be partial.
                # 2. Check Parent config if needed
                parent_config = {}
                rel = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
                parent_rel = os.path.dirname(rel)
                if parent_rel and parent_rel != '.':
                     parent_config = self.db.get_folder_config(parent_rel) or {}
                
                # Resolve transfer_mode: Child Override > Parent > App Default
                tm = None
                # Child override check:
                my_cfg = self.db.get_folder_config(rel) or {}
                tm = my_cfg.get('transfer_mode')
                
                if not tm or tm == 'KEEP':
                     tm = parent_config.get('transfer_mode')
                
                # 3. Check App Default
                if not tm:
                    # We need access to app_data. Unfortunately ItemCard doesn't hold full app_data usually.
                    # But we can try to get it from DB settings?
                    # Or rely on what passed in __init__?
                    # ItemCard stores self.app_deploy_default but not transfer mode default.
                    # Fallback to 'symlink' default if unknown.
                     tm = 'symlink' 

                transfer_mode = tm
            except: pass

        # Phase 51: Parse rules for exclude-aware status check
        rules_dict = {}
        if self.deployment_rules:
            try:
                import json
                rules_dict = json.loads(self.deployment_rules)
            except: pass

        status = self.deployer.get_link_status(
            target_link, 
            expected_source=self.path, 
            expected_transfer_mode=transfer_mode, 
            deploy_rule=deploy_rule,
            rules=rules_dict # Phase 51: Pass rules for EXCLUDE awareness
        )
        self.link_status = status.get('status', 'none')
        self.missing_samples = status.get('missing_samples', [])
        self.files_found = status.get('files_found', 0)
        self.files_total = status.get('files_total', 0)

        # Phase 35: Multi-root Fallback
        # If not found in primary target, check target_root_2 and target_root_3
        if self.link_status == 'none' and self.db:
            try:
                app_data = self.db.get_app_by_id(getattr(self, 'current_app_id', None))
                if app_data:
                    for root_key in ['target_root_2', 'target_root_3']:
                        other_root = app_data.get(root_key)
                        if other_root and other_root != self.target_dir:
                            # Re-calculate target path for this root
                            alt_target = os.path.join(other_root, self.folder_name)
                            alt_status = self.deployer.get_link_status(
                                alt_target, 
                                expected_source=self.path, 
                                expected_transfer_mode=transfer_mode, 
                                deploy_rule=deploy_rule,
                                rules=rules_dict
                            )
                            if alt_status.get('status') == 'linked':
                                self.link_status = 'linked'
                                status = alt_status
                                self.missing_samples = []
                                self.files_found = status.get('files_found', 0)
                                self.files_total = status.get('files_total', 0)
                                break
            except: pass
        # status is already updated if fallback succeeded
        
        # Debug: Log detection result
        import logging
        cat_deploy = getattr(self, 'category_deploy_status', 'None')
        logging.debug(f"[UpdateData] {os.path.basename(self.path)} (Status: {self.link_status}, Deploy: {self.deploy_type})")
        
        self.has_physical_conflict = (self.link_status == 'conflict')


        # Emit change signal if we detected a link (to update parent Category UI)
        # Note: We should ideally only emit if CHANGED.
        # But for now, ensuring it fires on check is safe for refresh.
        # Better: check if status changed.
        old_status = getattr(self, '_prev_link_status', 'none')
        if self.link_status != old_status:
             self._prev_link_status = self.link_status
             self.deploy_changed.emit()

        # Phase 28/51: is_partial logic
        # 1. True if actually missing files
        self.is_partial = (self.link_status == 'partial')
        
        # 2. ALSO True if Custom Mode returned is_intentional=True (calculated based on real exclusions)
        if not self.is_partial and status.get('is_intentional'):
             self.is_partial = True
             
        # 3. Fallback: If Custom Mode and rules exist, assume partial if not conflicted (Legacy/Visual safety)
        if not self.is_partial and deploy_rule == 'custom' and self.link_status != 'conflict':
             if rules_dict.get('exclude') or rules_dict.get('overrides') or rules_dict.get('rename'):
                 self.is_partial = True

        # Phase 28: Sync status to DB for fast total count lookups
        if self.db:
            try:
                rel = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
                self.db.update_folder_display_config(rel, last_known_status=self.link_status)
            except: pass

    def _update_name_label(self):
        """Update the name label text, including conflict prefix and favorite star."""
        if not hasattr(self, 'name_label'): return

        final_name = self.display_name
        # DISABLED: [競合] label feature was not desired functionality.
        # Keeping this code commented for reference but it is no longer active.
        # if getattr(self, 'has_name_conflict', False) or getattr(self, 'has_target_conflict', False):
        #     final_name = _("[Conflict] {name}").format(name=final_name)

        # Color setup
        name_color = "#888" if getattr(self, 'is_hidden', False) else "#ddd"
        if getattr(self, 'has_logical_conflict', False):
            name_color = "#e74c3c"  # Red text

        # Prepend yellow ★ for favorites ONLY in text_list mode
        display_mode = getattr(self, '_display_mode', 'standard')
        is_text_mode = display_mode == 'text_list'

        is_fav = getattr(self, 'is_favorite', False)
        
        # Build state tuple to detect changes
        current_state = (final_name, name_color, display_mode, is_fav)
        if hasattr(self, '_last_name_label_state') and self._last_name_label_state == current_state:
            return
        self._last_name_label_state = current_state

        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if is_fav and is_text_mode:
            self.name_label.setText(f'<span style="color: #ffd700;">★</span> <span style="color: {name_color};">{final_name}</span>')
        else:
            self.name_label.setText(final_name)
            self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")

    def set_children_status(self, has_linked: bool = False, has_conflict: bool = False, 
                            has_unlinked_children: bool = False, has_partial: bool = False,
                            has_category_conflict: bool = False, missing_samples: list = None,
                            files_found: int = 0, files_total: int = 0, 
                            has_intentional: bool = False):
        """Set child status flags for parent folder color logic.
        Also updates link_status for category cards to enable Unlink button.
        """
        self.has_linked_children = has_linked
        self.has_conflict_children = has_conflict
        self.has_unlinked_children = has_unlinked_children
        self.has_partial_children = has_partial
        self.has_intentional_children = has_intentional
        self.has_category_conflict = has_category_conflict
        self.missing_samples = missing_samples if missing_samples else []
        self.files_found = files_found
        self.files_total = files_total
        
        # Phase 14 Fix: For categories, update link_status based on children
        # This enables the Unlink button to appear when children are linked
        # PRIORITY: conflict > partial > linked > none
        if not getattr(self, 'is_package', True):  # Category card
            cat_deployed = getattr(self, 'category_deploy_status', None) == 'deployed'
            
            # Phase 4987 Fix: Prioritize states. 
            # If the folder itself is physically linked (📁 mode) it is 'linked'.
            # Otherwise follow hierarchical rules.
            if has_conflict:
                self.link_status = 'conflict'
            elif has_partial:
                self.link_status = 'partial'
            elif has_linked or cat_deployed:
                self.link_status = 'linked'
            else:
                self.link_status = 'none'
        
        self._update_style()
        self._update_icon_overlays()  # Refresh button visibility

    def _update_icon_overlays(self):
        """Update visibility of ★ and 🌐 icon overlays and their positions."""
        display_mode = getattr(self, '_display_mode', 'image_text')
        is_fav = getattr(self, 'is_favorite', False)
        has_urls = getattr(self, 'has_urls', False)
        status = getattr(self, 'link_status', 'none')
        
        # FIX: Category Deployed overrides children-based status for the button logic
        cat_status = getattr(self, 'category_deploy_status', None)
        if not getattr(self, 'is_package', True) and cat_status == 'deployed':
            status = 'linked'

        is_lib = bool(getattr(self, 'is_library', 0))
        
        # Performance Guard: Skip if nothing changed
        current_state = (
            display_mode, is_fav, has_urls, status, is_lib, self.width(), self.height(),
            getattr(self, '_deploy_btn_opacity', 0.8),
            getattr(self, 'show_link_overlay', True),
            getattr(self, 'show_deploy_btn', True),
            self.has_category_conflict,
            getattr(self, 'category_deploy_status', None) # Phase 4987: Track category deploy status change
        )
        if hasattr(self, '_last_icon_overlay_state') and self._last_icon_overlay_state == current_state:
            return
        self._last_icon_overlay_state = current_state

        # Get actual card dimensions
        base_w = getattr(self, '_base_card_w', 160)
        base_h = getattr(self, '_base_card_h', 200)
        scale = getattr(self, '_scale', 1.0)
        w = max(self.width(), int(base_w * scale))
        h = max(self.height(), int(base_h * scale))

        # Folder as Package Context Logic for Icon
        is_acting_as_package = getattr(self, 'is_package', True)
        if not is_acting_as_package and getattr(self, 'context', '') == "contents":
             # In Package View (contents), we always treat folders as packages visually.
             is_acting_as_package = True

        update_overlays_geometry(
            w, h, display_mode,
            is_favorite=is_fav,
            has_urls=has_urls,
            show_link=getattr(self, 'show_link_overlay', True),
            show_deploy=getattr(self, 'show_deploy_btn', True),
            link_status=status,
            star_label=getattr(self, 'star_overlay', None),
            url_label=getattr(self, 'url_overlay', None),
            deploy_btn=getattr(self, 'deploy_btn', None),
            lib_btn=getattr(self, 'lib_overlay', None),
            is_library=is_lib,
            opacity=getattr(self, '_deploy_btn_opacity', 0.8),
            is_package=is_acting_as_package,
            has_category_conflict=self.has_category_conflict
        )

    def set_deploy_button_opacity(self, opacity: float):
        """Update deployment button opacity dynamically."""
        self._deploy_btn_opacity = max(0.0, min(1.0, opacity))
        self._update_icon_overlays()

    def update_link_status(self, status: str = None):
        """Partial update: Re-check link status and update border color only."""
        if status is not None:
            self.link_status = status
        else:
            self._check_link_status()

        # Phase 28/Debug: If successfully linked, clear any persistent logical conflict marker 
        # to ensure immediate visual feedback without waiting for background worker.
        if self.link_status == 'linked':
            self.has_logical_conflict = False
            self.is_library_alt_version = False
            
        self._update_style()
        # Clear cache to force overlay update (fixes none→linked not reflecting)
        if hasattr(self, '_last_icon_overlay_state'):
            del self._last_icon_overlay_state
        # Defer overlay update to end of event loop to run AFTER any concurrent
        # _update_parent_category_status calls that might otherwise overwrite our state
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._update_icon_overlays)

    def update_hidden(self, is_hidden: bool):
        """Partial update: Update hidden state and text color only."""
        self.is_hidden = is_hidden
        name_color = "#888" if is_hidden else "#ddd"
        if hasattr(self, 'name_label'):
            self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")
        self._update_style()

    def update_trashed(self, is_trashed: bool, restore_callback=None):
        """Partial update: Show strikethrough for trashed items, with optional undo.

        Args:
            is_trashed: If True, show strikethrough and dim the card
            restore_callback: Optional callback for restore action
        """
        self.is_trashed = is_trashed
        self._restore_callback = restore_callback

        if hasattr(self, 'name_label'):
            if is_trashed:
                self.name_label.setStyleSheet("color: #666; font-weight: bold; text-decoration: line-through;")
                self.setStyleSheet(self.styleSheet() + " ItemCard { opacity: 0.5; }")
            else:
                name_color = "#888" if getattr(self, 'is_hidden', False) else "#ddd"
                self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")
        self._update_style()


    def set_selected(self, selected: bool, focused: bool = False):
        self.is_selected = selected
        self.is_focused = focused
        self._update_style()
        self.selection_changed.emit(self.path, self.is_selected)

    def set_scales(self, width_scale: float, height_scale: float):
        """Set independent scale factors and refresh display."""
        self.width_scale = width_scale
        self.height_scale = height_scale
        self.set_display_mode(getattr(self, 'display_mode', 'standard'))
        self._update_style()

    def _update_style(self):
        """Update card visual style and store colors for paintEvent."""
        is_sel = self.is_selected
        is_foc = self.is_focused
        mode = getattr(self, '_display_mode', 'standard')
        
        # Build state tuple for color-relevant parameters
        current_state = (
            self.link_status, self.is_misplaced, self.is_partial,
            self.has_logical_conflict, self.has_conflict_children,
            getattr(self, 'is_library_alt_version', False), self.is_registered,
            self.is_package, is_sel, is_foc,
            getattr(self, 'has_name_conflict', False),
            getattr(self, 'has_target_conflict', False),
            getattr(self, 'has_linked_children', False),
            getattr(self, 'has_unlinked_children', False),
            getattr(self, 'has_partial_children', False),
            getattr(self, 'has_intentional_children', False),
            getattr(self, 'is_intentional', False),
            getattr(self, 'is_hidden', False), # Phase 33: Track visibility for immediate color change
            getattr(self, 'category_deploy_status', None), # Phase 5: Ensure deep blue border updates
            mode
        )
        
        # Performance Guard: Skip if nothing changed
        if hasattr(self, '_last_style_state') and self._last_style_state == current_state:
            return
        self._last_style_state = current_state

        # Phase 35: Standardized acting as package logic
        is_acting_pkg = self.is_package
        if not is_acting_pkg and getattr(self, 'context', '') == "contents":
             is_acting_pkg = True

        # Calculate colors using broken out logic
        self._status_color, self._bg_color = get_card_colors(
            link_status=self.link_status,
            is_misplaced=getattr(self, 'is_misplaced', False),
            is_partial=getattr(self, 'is_partial', False),
            has_logical_conflict=getattr(self, 'has_logical_conflict', False),
            has_conflict_children=getattr(self, 'has_conflict_children', False),
            is_library_alt_version=getattr(self, 'is_library_alt_version', False),
            is_registered=self.is_registered,
            is_package=is_acting_pkg,
            is_selected=is_sel,
            is_focused=is_foc,
            has_name_conflict=getattr(self, 'has_name_conflict', False),
            has_target_conflict=getattr(self, 'has_target_conflict', False),
            has_linked_children=getattr(self, 'has_linked_children', False),
            has_unlinked_children=getattr(self, 'has_unlinked_children', False),
            has_partial_children=getattr(self, 'has_partial_children', False),
            has_intentional_children=getattr(self, 'has_intentional_children', False),
            is_intentional=getattr(self, 'is_intentional', False),
            category_deploy_status=getattr(self, 'category_deploy_status', None),
            context=getattr(self, 'context', None)
        )

        # Update name label color for hidden state
        name_color = COLOR_HIDDEN if getattr(self, 'is_hidden', False) else COLOR_NORMAL_TEXT
        if hasattr(self, 'name_label'):
            self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")

        # Minimized card stylesheet (only non-painter elements)
        new_style = f"ItemCard {{ background: transparent; border: none; }}"
        if not hasattr(self, "_current_stylesheet_str") or self._current_stylesheet_str != new_style:
            self.setStyleSheet(new_style)
            self._current_stylesheet_str = new_style

        self.update()  # Force repaint via paintEvent

    def paintEvent(self, event):
        """Draw Background, Status Border, and Selection/Hover."""
        # Note: Avoid calling super().paintEvent(event) which draws QSS border/bg
        
        painter = QPainter(self)
        if not painter.isActive():
            return
            
        # 1. Background and Status Border
        radius = 4 if getattr(self, 'display_mode', 'standard') == 'mini_image' else 8
        status_color = getattr(self, '_status_color', '#444')
        bg_color = getattr(self, '_bg_color', '#333')
        
        CardBorderPainter.draw_status_border(
            painter, QRectF(self.rect()), status_color, bg_color, radius=radius
        )

        # 2. Debug hitbox
        if ItemCard.SHOW_HITBOXES:
             CardBorderPainter.draw_debug_hitbox(painter, QRectF(self.rect()))

        # 3. Selection/Hover Border
        if self.is_selected or self.is_hovered:
            CardBorderPainter.draw_selection_border(
                painter, QRectF(self.rect()),
                is_selected=self.is_selected,
                is_focused=self.is_focused,
                is_hovered=self.is_hovered,
                display_mode=getattr(self, '_display_mode', 'standard')
            )
        
        painter.end()

    def set_pixmap(self, pixmap):
        """Set pixmap via ThumbnailWidget component."""
        if not pixmap.isNull():
            self._original_pixmap = pixmap  # Preserve for real-time scaling
            self.thumb_label.setImage(pixmap)
        else:
            self.thumb_label.clear()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Phase 28: Accept image file drag events from local or web."""
        mime = event.mimeData()
        if mime.hasImage():
            event.acceptProposedAction()
            return
            
        if mime.hasUrls():
            # Accept if it looks like an image or is a local file
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ['.webp', '.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        event.acceptProposedAction()
                        return
                else:
                    # Web URL - Accept almost anything to try downloading
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Phase 28: Handle dropped image files (local, web, or raw data)."""
        mime = event.mimeData()
        
        # 1. Direct Image Data (e.g. from browser copy/drag)
        if mime.hasImage():
            image = mime.imageData()
            if image and not image.isNull():
                import time
                temp_dir = os.path.join(os.environ.get('TEMP', ''), 'LinkMaster')
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f"dropped_image_{int(time.time())}.png")
                image.save(temp_path)
                self._register_dropped_image(temp_path)
                event.accept()
                return

        # 2. URLs (Local or Web)
        if mime.hasUrls():
            urls = mime.urls()
            if not urls: return
            
            for url in urls:
                if url.isLocalFile():
                    # Local File
                    src_path = url.toLocalFile()
                    ext = os.path.splitext(src_path)[1].lower()
                    if ext in ['.webp', '.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        self._register_dropped_image(src_path)
                        event.accept()
                        return # Only handle first valid
                else:
                    # Web URL
                    self._download_and_register(url.toString())
                    event.accept()
                    return # Only handle first valid

    def _download_and_register(self, url_str):
        """Download image from URL in background and register."""
        import threading
        import urllib.request
        import urllib.error
        
        def run():
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                req = urllib.request.Request(url_str, headers=headers)
                
                # Use standard library for downloading
                with urllib.request.urlopen(req, timeout=10) as r:
                    if r.status == 200:
                        import time
                        temp_dir = os.path.join(os.environ.get('TEMP', ''), 'LinkMaster')
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        # Guess extension
                        ext = ".png"
                        # In urllib, headers.get_content_type() returns 'image/jpeg' etc.
                        ctype = r.headers.get_content_type().lower()
                        if 'jpeg' in ctype: ext = '.jpg'
                        elif 'gif' in ctype: ext = '.gif'
                        elif 'webp' in ctype: ext = '.webp'
                        
                        temp_path = os.path.join(temp_dir, f"web_image_{int(time.time())}{ext}")
                        with open(temp_path, 'wb') as f:
                            f.write(r.read())
                        
                        # Emit signal to main thread
                        self.image_ready_signal.emit(temp_path)
            except Exception as e:
                logging.getLogger("ItemCard").error(f"Download failed: {url_str} - {e}")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _register_dropped_image(self, src_path):
        """Internal method to register a local image path as the icon."""
        try:
            if not os.path.exists(src_path): return

            # Comprehensive null checks
            if not getattr(self, 'thumbnail_manager', None):
                logging.getLogger("ItemCard").warning("Thumbnail drop: thumbnail_manager not set")
                return
            if not getattr(self, 'storage_root', None): return
            if not getattr(self, 'db', None): return
            if not getattr(self, 'path', None): return
            if not getattr(self, 'app_name', None): return

            # Get relative path for this card
            rel = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
            if not rel: return

            # Destination path in resource directory
            # Use timestamp to prevent overwrite and allow accumulation
            default_thumb_path = self.thumbnail_manager.get_thumbnail_path(self.app_name, rel)
            if not default_thumb_path: return
            
            dest_dir = os.path.dirname(default_thumb_path)
            os.makedirs(dest_dir, exist_ok=True)

            import time
            import shutil
            timestamp = int(time.time())
            base, fext = os.path.splitext(os.path.basename(src_path))
            if not fext: fext = ".png"
            new_filename = f"{base}_{timestamp}{fext}"
            dest_path = os.path.join(dest_dir, new_filename)

            # Copy and resize via thumbnail manager (or direct copy for quality)
            shutil.copy2(src_path, dest_path)

            # Update database - IMPORTANT: Register both image_path AND manual_preview_path
            # Accumulate manual_preview_path
            current_previews = [p.strip() for p in (self.manual_preview_path or "").split(';') if p.strip()]
            if dest_path not in current_previews:
                current_previews.append(dest_path)
            
            new_preview_str = ";".join(current_previews)
            self.manual_preview_path = new_preview_str
            
            # Image path updates to the latest dropped one (Icon behavior)
            self.db.update_folder_display_config(rel, manual_preview_path=new_preview_str, image_path=dest_path)

            # Refresh card display
            if self.loader:
                self.thumb_label.setText(str(_("Loading...")))
                self.loader.load_image(dest_path, QSize(256, 256), self.set_pixmap)

        except Exception as e:
            import traceback
            logger.error(f"Failed to register dropped thumbnail: {e}")
            logger.error(f"Error drawing card border: {e}", exc_info=True)

    def enterEvent(self, event):
        """Manual hover tracking for border drawing."""
        self.is_hovered = True
        self.update() # Trigger repaint for border
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Manual hover tracking for border drawing."""
        self.is_hovered = False
        self.update() # Trigger repaint for border
        super().leaveEvent(event)


    def mousePressEvent(self, event):
        """Pass click event to parent for centralized multi-selection handling."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.single_clicked.emit(self.path)
        elif event.button() == Qt.MouseButton.RightButton:
            # Propagate to parent container for customContextMenuRequested
            event.ignore()

    def _open_first_working_url(self):
        """Check all URLs and open the prioritized one (marked > first active)."""
        import os
        from src.utils.url_utils import open_first_working_url, URL_OPENED, URL_OPEN_MANAGER, URL_NO_URLS

        url_raw = getattr(self, 'url_list', '[]')

        # Get rel_path for DB persistence
        rel_path = None
        if self.db and self.storage_root and self.path:
            try:
                rel_path = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
            except:
                pass

        # Use shared utility with DB persistence support
        result = open_first_working_url(
            url_raw,
            parent=self,
            db=self.db,
            rel_path=rel_path
        )

        if result == URL_OPENED:
            # Refresh local url_list from DB if marked changed
            if rel_path and self.db:
                try:
                    config = self.db.get_folder_config(rel_path) or {}
                    new_url_list = config.get('url_list', self.url_list)
                    if new_url_list != self.url_list:
                        self.url_list = new_url_list
                        self._sync_url_icon() # Phase 1.0.9 Fix: Sync icon immediately
                        self.property_changed.emit({
                            'path': self.path,
                            'url_list': self.url_list
                        })
                except:
                    pass
        elif result in (URL_OPEN_MANAGER, URL_NO_URLS):
            # User chose to open URL manager, or no URLs exist
            self._open_url_manager()

    def _open_url_manager(self):
        """Open URL management dialog for this item."""
        import os
        from src.ui.link_master.dialogs.url_list_dialog import URLListDialog

        rel_path = None
        if self.db and self.storage_root and self.path:
            try:
                rel_path = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
            except:
                pass

        current_json = getattr(self, 'url_list', '[]') or '[]'

        dialog = URLListDialog(self, url_list_json=current_json, caller_id="item_card")
        if dialog.exec():
            new_json = dialog.get_data()
            self.url_list = new_json
            self._sync_url_icon()

            # Save to DB
            if rel_path and self.db:
                try:
                    self.db.update_folder_display_config(rel_path, url_list=new_json)
                    self.property_changed.emit({
                        'path': self.path,
                        'url_list': self.url_list
                    })
                except:
                    pass

    def _sync_url_icon(self):
        """Update has_urls and refresh icons based on current url_list."""
        url_raw = getattr(self, 'url_list', '[]')
        import json
        if not url_raw or url_raw == '[]' or url_raw == '""':
            self.has_urls = False
        else:
            try:
                import json
                parsed = json.loads(url_raw)
                if isinstance(parsed, list):
                    # Filter out empty strings or entries without a 'url' key
                    self.has_urls = any((item.get('url').strip() if isinstance(item, dict) else item.strip()) for item in parsed if (isinstance(item, dict) and item.get('url')) or (isinstance(item, str) and item.strip()))
                else:
                    self.has_urls = bool(parsed)
            except:
                self.has_urls = bool(url_raw and url_raw != '[]')
        self._update_icon_overlays()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Phase 28: Alt+Double-Click opens property editor for ANY item
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.request_edit_properties.emit(self.path)
                return
            # Phase 28: Emitting double_clicked even for packages!
            # Parents (like LinkMasterWindow) will decide what to do (navigate or show properties)
            self.double_clicked.emit(self.path)
            self.clicked.emit(self.path)

    def _open_in_explorer(self):
        import subprocess
        import sys
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', self.path])

    def _open_properties_dialog(self):
        """Request property edit via parent window (LMBatchOpsMixin)."""
        # Ensure this item is selected so _batch_edit_properties_selected picks it up
        self.set_selected(True, focused=True)

        # Traverse up to find LinkMasterWindow
        curr = self.parent()
        while curr:
            if hasattr(curr, '_batch_edit_properties_selected'):
                curr._batch_edit_properties_selected()
                return
            curr = curr.parent()

    def _show_full_preview(self):
        """Show the high-res preview dialog (supporting multiple files)."""
        import os
        if not self.manual_preview_path:
            QMessageBox.warning(self, "Error", "No preview path configured.")
            return

        # Split multiple paths
        raw_paths = [p.strip() for p in self.manual_preview_path.split(';') if p.strip()]
        valid_paths = [p for p in raw_paths if os.path.exists(p)]

        if not valid_paths:
            QMessageBox.warning(self, "Error", "None of the configured preview files exist.")
            return

        # If it's just one file and a video, open it directly
        if len(valid_paths) == 1:
            ext = os.path.splitext(valid_paths[0])[1].lower()
            if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv']:
                os.startfile(valid_paths[0])
                return

        # Otherwise use the new gallery dialog
        from src.ui.link_master.dialogs import FullPreviewDialog
        dialog = FullPreviewDialog(self, paths=valid_paths, name=self.display_name)
        dialog.exec()

    def _toggle_visibility(self):
        """Toggle is_visible attribute in DB and update card display (no full refresh)."""
        self.is_hidden = not self.is_hidden
        # logger.debug(f"[Profiling] ItemCard._toggle_visibility: path={self.path}, is_hidden={self.is_hidden}")

        if self.db:
            try:
                # Standardize path for DB
                rel = self.path
                if hasattr(self, 'storage_root') and self.storage_root:
                    rel = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
                else:
                    rel = rel.replace('\\', '/')

                self.db.update_folder_display_config(rel, is_visible=(0 if self.is_hidden else 1))
                # logger.debug(f"[Profiling] DB Updated: {rel} is_visible={0 if self.is_hidden else 1}")
            except Exception as e:
                logger.error(f"Error updating visibility: {e}")

        # Use partial update instead of full refresh
        self.update_hidden(self.is_hidden)
        # logger.debug("[Profiling] Used update_hidden for partial update (no deploy_changed emit)")

    def set_display_mode(self, mode: str):
        """Set display mode: 'text_list', 'mini_image', 'image_text'.

        This only controls visibility of elements, NOT sizes.
        Use set_card_params for size control.
        """
        self._display_mode = mode

        if mode == 'text_list':
            # Hide image, show text only
            self.thumb_label.hide()
            self.name_label.show()
        elif mode == 'mini_image':
            # Show image only, hide text
            self.thumb_label.show()
            self.name_label.hide()
        else:  # 'image_text' or default
            # Show both image and text
            self.thumb_label.show()
            self.name_label.show()

        self._update_name_label()      # Refresh text (handle star prefix)
        self._update_icon_overlays() # Refresh overlay positions for new mode
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_icon_overlays() # Reposition icons on resize



    def set_card_params(self, base_card_w: int, base_card_h: int,
                        base_img_w: int, base_img_h: int, scale: float = 1.0):
        import time
        t_start = time.perf_counter()
        """Set card size parameters with proper base/display separation.

        Following the pattern: DisplaySize = BaseSize × Scale

        Args:
            base_card_w: Card base width in pixels
            base_card_h: Card base height in pixels
            base_img_w: Image base width in pixels
            base_img_h: Image base height in pixels
            scale: Global scale multiplier (1.0 = 100%)
        """
        # Parameter Guard: Skip if nothing changed
        if (getattr(self, '_last_params', None) ==
            (base_card_w, base_card_h, base_img_w, base_img_h, scale)):
            return
        self._last_params = (base_card_w, base_card_h, base_img_w, base_img_h, scale)

        # Store base values (these are the "source of truth")
        self._base_card_w = base_card_w
        self._base_card_h = base_card_h
        self._base_img_w = base_img_w
        self._base_img_h = base_img_h
        self._scale = scale

        # Calculate display sizes (BaseSize × Scale) - ONE-DIRECTION ONLY
        display_card_w = int(base_card_w * scale)
        display_card_h = int(base_card_h * scale)
        display_img_w = int(base_img_w * scale)
        display_img_h = int(base_img_h * scale)

        # Apply card size
        self.setFixedSize(display_card_w, display_card_h)

        # Apply image container size
        self.thumb_label.setFixedSize(display_img_w, display_img_h)
        self.thumb_label.setTargetSize(QSize(display_img_w, display_img_h))

        # Re-scale original pixmap to display size (via ThumbnailWidget)
        if hasattr(self, '_original_pixmap') and self._original_pixmap:
            if self._original_pixmap and not self._original_pixmap.isNull():
                self.thumb_label.setImage(self._original_pixmap)

        self._update_style()  # Apply border/background based on link status
        self._update_icon_overlays() # Ensure icons are positioned for new size
        self.update()

        # --- Phase 24: Mode-specific layout ---
        mode = getattr(self, '_display_mode', 'image_text')
        is_mini = mode == 'mini_image'
        is_text_only = mode == 'text_list'

        # Set margins - centering is handled by Qt.AlignCenter on widget add
        margin_h = 4
        margin_t = 4  # Top margin for selection border visibility
        margin_b = 2
        spacing = 2

        # Mode-specific visibility and alignment
        if is_text_only:
            # Text-only mode: hide image, center text both vertically and horizontally
            self.thumb_label.hide()
            self.name_label.show()
            self.name_label.setWordWrap(True)
            self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Use full card height for text area, allowing multi-line
            self.name_label.setFixedHeight(display_card_h - margin_t - margin_b)
            self.name_label.setMaximumWidth(display_card_w - margin_h * 2)
            margin_h = 6  # Slightly more padding for text list
        elif is_mini:
            # Image-only mode: show image, HIDE name
            self.thumb_label.show()
            self.name_label.hide()
        else:
            # Image+Text mode: show both, center name
            self.thumb_label.show()
            self.name_label.show()
            self.name_label.setWordWrap(True)
            self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Calculate available height for text (card height - image height - margins - spacing)
            text_area_h = max(24, display_card_h - display_img_h - 8)
            self.name_label.setFixedHeight(text_area_h)
            self.name_label.setMaximumWidth(display_card_w - 4)

        self.layout().setContentsMargins(margin_h, margin_t, margin_h, margin_b)
        self.layout().setSpacing(spacing)

        self.updateGeometry()

    def _on_async_scale_done(self, pixmap, request_id):
        """Callback for high-quality background scaling."""
        if request_id == self._current_scale_id:
            from PyQt6 import sip
            if not sip.isdeleted(self):
                self.thumb_label.setPixmap(pixmap)
