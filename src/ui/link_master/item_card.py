""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QMenu, QMessageBox
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRectF, QMimeData, QRect
from src.ui.link_master.clickable_label import ClickableLabel
from PyQt6.QtGui import QPixmap, QCursor, QPainter, QPen, QColor, QDragEnterEvent, QDropEvent
import os
import shutil
import logging
from src.core.lang_manager import _

class ItemCard(QFrame):
    # Static Debug Flag
    SHOW_HITBOXES = False

    # Profiling counters
    _total_style_time = 0.0
    _style_count = 0
    _total_scale_time = 0.0
    _scale_count = 0

    clicked = pyqtSignal(str) # Emits on Double Click (Nav) - Legacy/Alias
    single_clicked = pyqtSignal(str) # Emits on Single Click (Selection)
    selection_changed = pyqtSignal(str, bool) # Emits path, is_selected
    double_clicked = pyqtSignal(str) # Alias for Nav
    deploy_changed = pyqtSignal()  # Emits when link is deployed/removed (for parent refresh)
    property_changed = pyqtSignal(dict) # Phase 30: Emits when a property like favorite changes
    request_deployment_toggle = pyqtSignal(str) # Phase 30: Direct deployment from card
    request_move_to_unclassified = pyqtSignal(str) # Emits path
    request_move_to_trash = pyqtSignal(str)        # Emits path
    request_restore = pyqtSignal(str)              # Phase 18.11: Emits path
    request_reorder = pyqtSignal(str, str)         # New: path, "top" or "bottom"
    request_edit_properties = pyqtSignal(str)      # Phase 28: Alt+Double-Click -> Edit Properties
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
                 show_link: bool = True, show_deploy: bool = True, deploy_button_opacity: float = 0.8):
        super().__init__(parent)
        self.path = path # Source Path (Absolute)
        self.folder_name = os.path.basename(path) # Physical folder name for links
        self.display_name = name # Display name from config or folder name
        self.loader = loader
        self.deployer = deployer
        self.target_dir = target_dir
        self.target_override = target_override
        self.deployment_rules = deployment_rules
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
        self.link_status = 'none' # 'none', 'linked', 'conflict'
        self.has_linked_children = False  # True if any child is linked
        self.has_conflict_children = False  # True if any child has conflict
        self.has_logical_conflict = False
        self.has_physical_conflict = False
        self.conflict_tag = None
        self.conflict_scope = 'disabled'
        self.is_library_alt_version = False  # True if another version of same library is deployed
        
        # Phase 31: Visibility Toggles (Per mode)
        self.show_link_overlay = show_link
        self.show_deploy_btn = show_deploy
        self._deploy_btn_opacity = deploy_button_opacity
        
        self.setFixedSize(160, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)  # Minimal margins, centering by Qt flags
        
        # thumbnail (Placeholder)
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(140, 120)
        self.thumb_label.setStyleSheet("background-color: #222; border-radius: 4px; border: 1px solid #333;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText(_("No Image"))
        
        self.setMouseTracking(True)
        # Async Load
        if image_path and loader:
            self.thumb_label.setText(_("Loading..."))
            loader.load_image(image_path, QSize(256, 256), self.set_pixmap)
        
        # Name (gray if hidden)
        self.name_label = QLabel(self.display_name)
        name_color = "#888" if self.is_hidden else "#ddd"  # Phase 18.14: Gray for hidden
        self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Phase 24 Fix: Top-fixed layout (image at top, text below, no vertical centering)
        # This ensures image position is stable regardless of text length.
        layout.addWidget(self.thumb_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()  # Push content to top
        
        # Icon overlays - CREATED AFTER layout widgets to ensure they're on top (z-order)
        self.star_overlay = QLabel("★", self)
        self.star_overlay.setStyleSheet("color: #ffd700; font-size: 18px; font-weight: bold; background: transparent; padding: 0px 1px 1px 0px; text-align: center;")
        self.star_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.star_overlay.hide()

        # URL Overlay - Using QLabel (emoji displays properly) with click handling via mousePressEvent
        self.url_overlay = QLabel("🌐", self)
        self.url_overlay.setFixedSize(24, 24)
        self.url_overlay.setStyleSheet("QLabel { font-size: 16px; background-color: rgba(30, 30, 30, 0.7); border-radius: 12px; } QLabel:hover { background-color: rgba(52, 152, 219, 0.8); }")
        self.url_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_overlay.setCursor(Qt.CursorShape.PointingHandCursor)
        self.url_overlay.setToolTip(_("Open related URL"))
        # NOTE: Click handled in mousePressEvent by checking geometry
        self.url_overlay.hide()
        
        # Phase 30: Deploy Toggle Overlay
        self.deploy_btn = QPushButton(self)
        self.deploy_btn.setFixedSize(24, 24)
        self.deploy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deploy_btn.clicked.connect(lambda: self.request_deployment_toggle.emit(self.path))
        self.deploy_btn.hide()
        
        # Phase 28: Enable drag-drop for thumbnail images
        self.setAcceptDrops(True)
        
        # Favorite & URL indicators (initialize as False/empty, updated via update_data)
        self.is_favorite = False
        self.score = 0
        self.has_urls = False
        self.url_list = '[]'
        
        self._check_link_status() 
        self._update_name_label()
        self._update_style()
        self._update_icon_overlays()  # Initialize icon visibility

    def update_data(self, **kwargs):
        """Phase 28: Reuse widget by updating its data without reconstruction.
        
        Args:
            **kwargs: Item properties:
                name (str): Display name
                path (str): Absolute source path
                image_path (str): Path to thumbnail
                is_package (bool): True if package, False if category
                is_registered (bool): True if in DB
                is_misplaced (bool): True if in wrong folder
                is_trash_view (bool): True if in trash
                is_hidden (bool): True if hidden
                target_override (str): Manual link target
                deployment_rules (str): JSON rules
                manual_preview_path (str): Path to video/etc
                deploy_type (str): 'folder', 'file', etc
                conflict_policy (str): 'backup', 'overwrite', etc
        """
        from PyQt6 import sip
        if sip.isdeleted(self):
            return

        # 1. Update Core Data & Context
        old_path = self.path
        self.path = kwargs.get('path', self.path)
        self.target_dir = kwargs.get('target_dir', self.target_dir)
        self.storage_root = kwargs.get('storage_root', self.storage_root)
        self.folder_name = os.path.basename(self.path.rstrip('\\/'))
        
        # Support both 'name' and 'display_name' with robust fallback to physical folder name
        self.display_name = kwargs.get('display_name') or kwargs.get('name') or self.folder_name
        
        # 2. Update Session Managers (Optional but safer)
        if 'loader' in kwargs: self.loader = kwargs['loader']
        if 'deployer' in kwargs: self.deployer = kwargs['deployer']
        if 'db' in kwargs: self.db = kwargs['db']
        if 'thumbnail_manager' in kwargs: self.thumbnail_manager = kwargs['thumbnail_manager']
        
        # 3. Update Flags
        self.is_package = kwargs.get('is_package', self.is_package)
        if 'folder_type' in kwargs:
            self.is_package = (kwargs['folder_type'] == 'package')
            
        self.is_registered = kwargs.get('is_registered', True)
        self.is_misplaced = kwargs.get('is_misplaced', False)
        self.is_partial = kwargs.get('is_partial', getattr(self, 'is_partial', False))
        self.is_trash_view = kwargs.get('is_trash_view', False)
        
        # Support 'is_visible' (0/1) mapping to 'is_hidden'
        if 'is_visible' in kwargs:
            self.is_hidden = (kwargs['is_visible'] == 0)
        else:
            self.is_hidden = kwargs.get('is_hidden', getattr(self, 'is_hidden', False))

        # Core Conflict Flags (Preserve during pinpoint updates if not provided)
        self.link_status = kwargs.get('link_status', getattr(self, 'link_status', 'none'))
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
        self.has_conflict_children = kwargs.get('has_conflict_children', getattr(self, 'has_conflict_children', False))
        
        # 4. Update Config/Rules
        self.target_override = kwargs.get('target_override', self.target_override)
        self.deployment_rules = kwargs.get('deployment_rules', self.deployment_rules)
        self.manual_preview_path = kwargs.get('manual_preview_path', self.manual_preview_path)
        self.deploy_type = kwargs.get('deploy_type', self.deploy_type)
        self.conflict_policy = kwargs.get('conflict_policy', self.conflict_policy)
        
        # Phase 28 Fix: Store conflict tag data specifically for UI Red Line logic
        self.conflict_tag = kwargs.get('conflict_tag', getattr(self, 'conflict_tag', None))
        self.conflict_scope = kwargs.get('conflict_scope', getattr(self, 'conflict_scope', 'disabled'))
        
        # Favorite & URL indicators
        self.is_favorite = bool(kwargs.get('is_favorite', getattr(self, 'is_favorite', False)))
        self.score = kwargs.get('score', getattr(self, 'score', 0)) or 0
        url_list = kwargs.get('url_list', getattr(self, 'url_list', '[]'))
        self.has_urls = bool(url_list and url_list != '[]')
        self.url_list = url_list

        # Phase 30: Synchronize Library info
        self.is_library = kwargs.get('is_library', getattr(self, 'is_library', 0))
        self.lib_name = kwargs.get('lib_name', getattr(self, 'lib_name', ''))
        self.is_library_alt_version = kwargs.get('is_library_alt_version', getattr(self, 'is_library_alt_version', False))

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
            
            # Phase 28: Always update image state when card is reused
            self._current_image_path = new_image_path
            
            if new_image_path:
                if new_image_path != old_image_path and self.loader:
                    self.thumb_label.setText(_("Loading..."))
                    # Always load at 256x256 base size for high quality scaling later
                    self.loader.load_image(new_image_path, QSize(256, 256), self.set_pixmap)
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
        self._update_style()
        self._update_icon_overlays()

    def _check_link_status(self):
        if not self.deployer: return
        # IMPORTANT: Use physical folder_name for link detection, NOT display_name
        target_link = self.target_override or (os.path.join(self.target_dir, self.folder_name) if self.target_dir else None)
        if not target_link: return
                
        status = self.deployer.get_link_status(target_link, expected_source=self.path)
        self.link_status = status.get('status', 'none')
        self.has_physical_conflict = (self.link_status == 'conflict')
        
        # Phase 3.6: Reset is_partial before checking.
        # It's only True if rules exist AND its physically linked as partial.
        self.is_partial = False
        if status.get('type') == 'partial':
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
        if getattr(self, 'has_name_conflict', False) or getattr(self, 'has_target_conflict', False):
            final_name = _("[Conflict] {name}").format(name=final_name)
        
        # Color setup
        name_color = "#888" if getattr(self, 'is_hidden', False) else "#ddd"
        if getattr(self, 'has_logical_conflict', False):
            name_color = "#e74c3c"  # Red text
            
        # Prepend yellow ★ for favorites ONLY in text_list mode
        is_text_mode = getattr(self, '_display_mode', 'image_text') == 'text_list'
        
        if getattr(self, 'is_favorite', False) and is_text_mode:
            self.name_label.setText(f'<span style="color: #ffd700;">★</span> <span style="color: {name_color};">{final_name}</span>')
        else:
            self.name_label.setText(final_name)
            self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")
            
    def set_children_status(self, has_linked: bool = False, has_conflict: bool = False):
        """Set child status flags for parent folder color logic."""
        self.has_linked_children = has_linked
        self.has_conflict_children = has_conflict
        self._update_style()

    def _update_icon_overlays(self):
        """Update visibility of ★ and 🌐 icon overlays and their positions."""
        # Determine if we are in an image-displaying mode
        # Mode is 'text_list', 'mini_image', or 'image_text' (default)
        is_text_mode = getattr(self, '_display_mode', 'image_text') == 'text_list'
        use_overlays = not is_text_mode
        
        # Get actual card dimensions - use stored base sizes with scale if available
        # This ensures correct positioning even before the widget is shown
        base_w = getattr(self, '_base_card_w', 160)
        base_h = getattr(self, '_base_card_h', 200)
        scale = getattr(self, '_scale', 1.0)
        w = int(base_w * scale)
        h = int(base_h * scale)
        
        # Fallback to widget size if it's larger (widget might be resized)
        if self.width() > w:
            w = self.width()
        if self.height() > h:
            h = self.height()
        
        # 1. Star Overlay (on image)
        if hasattr(self, 'star_overlay'):
            if getattr(self, 'is_favorite', False) and use_overlays:
                self.star_overlay.setGeometry(6, 8, 24, 24)
                self.star_overlay.show()
                self.star_overlay.raise_()
            else:
                self.star_overlay.hide()
        
        # 2. URL Overlay (Link Button)
        if hasattr(self, 'url_overlay'):
            if getattr(self, 'has_urls', False) and getattr(self, 'show_link_overlay', True):
                # Top-right corner
                self.url_overlay.setGeometry(w - 30, 8, 24, 24)
                self.url_overlay.setText("🌐")  # Ensure text is set
                self.url_overlay.show()
                self.url_overlay.raise_()
            else:
                self.url_overlay.hide()

        # 3. Deploy Toggle Overlay (Phase 30/31)
        if hasattr(self, 'deploy_btn'):
            if getattr(self, 'show_deploy_btn', True):
                # Position depends on mode
                if is_text_mode:
                    # In text mode, place it on the right side, vertically centered
                    self.deploy_btn.setGeometry(w - 30, (h - 24) // 2, 24, 24)
                else:
                    # Bottom-right corner for image modes
                    self.deploy_btn.setGeometry(w - 30, h - 30, 24, 24)
                
                # Update Icon based on status with hover effects
                opacity = getattr(self, '_deploy_btn_opacity', 0.8)
                if self.link_status == 'linked':
                    icon_char = "🔗"
                    base_color = f"rgba(39, 174, 96, {opacity})"
                    hover_color = "rgba(46, 204, 113, 0.95)"
                    border_color = "#1e8449"
                    self.deploy_btn.setToolTip("リンク済み（解除）")
                elif self.link_status == 'conflict':
                    icon_char = "⚠"
                    base_color = f"rgba(231, 76, 60, {opacity})"
                    hover_color = "rgba(241, 100, 85, 0.95)"
                    border_color = "#943126"
                    self.deploy_btn.setToolTip("競合中（占有）")
                else:
                    icon_char = "🚀"
                    base_color = f"rgba(52, 152, 219, {opacity})"
                    hover_color = "rgba(93, 173, 226, 0.95)"
                    border_color = "#2471a3"
                    self.deploy_btn.setToolTip("非リンク（デプロイ）")
                
                style = f"""
                    QPushButton {{ 
                        background-color: {base_color}; 
                        color: white; 
                        border-radius: 12px; 
                        font-size: 11px; 
                        border: 1px solid {border_color}; 
                    }}
                    QPushButton:hover {{ 
                        background-color: {hover_color}; 
                    }}
                """
                self.deploy_btn.setText(icon_char)
                self.deploy_btn.setStyleSheet(style)
                self.deploy_btn.show()
                self.deploy_btn.raise_()
            else:
                self.deploy_btn.hide()

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
        self._update_style()
        self._update_icon_overlays() # Immediate update for button icon

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
        import time
        t0 = time.perf_counter()
        
        # Priority: Conflict (Red) > Linked Children (Orange) > Linked (Green) > Unregistered (Purple) > Normal
        # Note: Misplaced (Pink) is also high priority.
        # SELECTION is now an INNER decoration, status is always OUTER.
        
        status_color = "#444"
        bg_color = "#333"
        width = "2px"
        
        # [Profile] Debug log for special statuses (logic/lib)
        if self.has_logical_conflict:
            # print(f"[Profile] Card {os.path.basename(self.path)}: RED border (Logical Conflict)")
            pass
        if getattr(self, 'is_library_alt_version', False):
            # print(f"[Profile] Card {os.path.basename(self.path)}: YELLOW-GREEN border (Lib Alt)")
            pass

        if self.link_status == 'conflict' or \
             getattr(self, 'has_physical_conflict', False) or \
             self.has_logical_conflict or \
             getattr(self, 'has_name_conflict', False) or \
             getattr(self, 'has_target_conflict', False) or \
             (not self.is_package and self.has_conflict_children):
            # Tag conflicts/Logical conflicts show red (High Priority)
            status_color = "#e74c3c" # Red
            bg_color = "#3d2a2a"
        elif getattr(self, 'is_library_alt_version', False):
            # Alternative version of a deployed library - Yellow-green
            status_color = "#9acd32"
            bg_color = "#2d3d2a"
        elif self.is_misplaced:
            status_color = "#ff69b4" # Pink
            bg_color = "#3d2a35"     # Dark Pink Tint
        # Phase 3.6: Partial status must check BEFORE general linked to show yellow
        elif self.is_partial and (self.link_status == 'linked' or self.link_status == 'partial'):
            status_color = "#f1c40f" # Yellow (Feature 6: Partial Deployment)
            bg_color = "#3d3d2a"     # Dark Yellow Tint
        elif self.link_status == 'linked':
            status_color = "#27ae60" # Green
            bg_color = "#2a332a"
        elif self.has_linked_children:
            status_color = "#e67e22" # Orange
            bg_color = "#3d322a" 
        elif not self.is_registered:
            status_color = "#9b59b6" # Amethyst Purple
            bg_color = "#322a3d"
            
        # Selection Background Tint
        if self.is_selected:
            bg_color = "#2a3b4d" # Blue-ish background
            if self.is_focused:
                 bg_color = "#34495e" # Slightly lighter if focused
        
        radius = "8px"
        if getattr(self, 'display_mode', 'standard') == 'mini_image':
            radius = "4px"
        
        new_style = f"""
            ItemCard {{
                background-color: {bg_color};
                border: {width} solid {status_color};
                border-radius: {radius};
            }}
            ItemCard:hover {{
                background-color: #3d4a59;
            }}
            QPushButton {{
                border: none;
                border-radius: 12px;
                color: white;
            }}
            QLabel {{
                background: transparent;
            }}
        """
        
        # Performance Optimization: Only apply if string actually changed
        if not hasattr(self, "_current_stylesheet_str") or self._current_stylesheet_str != new_style:
            self.setStyleSheet(new_style)
            self._current_stylesheet_str = new_style
        
        # Update name label color for hidden state
        name_color = "#888" if getattr(self, 'is_hidden', False) else "#ddd"
        if hasattr(self, 'name_label'):
            self.name_label.setStyleSheet(f"color: {name_color}; font-weight: bold;")
            
        self.update()  # Force immediate repaint
        
        dt = time.perf_counter() - t0
        ItemCard._total_style_time += dt
        ItemCard._style_count += 1

    def paintEvent(self, event):
        """Draw Dual-Layered Border: Status (Outer) + Selection/Hover (Inner)."""
        super().paintEvent(event)
        
        # ===== Selection/Hover Border =====
        if not self.is_selected and not self.is_hovered:
            # Debug hitbox still runs
            if ItemCard.SHOW_HITBOXES:
                debug_painter = QPainter(self)
                debug_painter.setPen(QPen(QColor(255, 0, 0, 150), 2))
                debug_painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Inner Selection/Hover Frame
        pen_width = 2 if self.is_selected else 1
        inner_offset = 4
        
        if self.is_selected:
            if self.is_focused:
                pen = QPen(QColor("#5DADE2"), pen_width, Qt.PenStyle.SolidLine)
            else:
                pen = QPen(QColor("#3498DB"), pen_width, Qt.PenStyle.SolidLine)
        elif self.is_hovered:
            pen = QPen(QColor("#666666"), pen_width, Qt.PenStyle.SolidLine)
        else:
            return
            
        painter.setPen(pen)
        
        base_radius = 8
        if getattr(self, '_display_mode', 'standard') == 'mini_image':
             base_radius = 4
             
        inner_radius = max(0, base_radius - inner_offset)
        inner_rect = QRectF(self.rect()).adjusted(inner_offset, inner_offset, -inner_offset, -inner_offset)
        
        painter.drawRoundedRect(inner_rect, inner_radius, inner_radius)
        
        if self.is_focused:
            painter.setPen(QPen(QColor("#AED6F1"), 1, Qt.PenStyle.DotLine))
            inner_rect_2 = inner_rect.adjusted(1, 1, -1, -1)
            painter.drawRoundedRect(inner_rect_2, max(0, inner_radius-1), max(0, inner_radius-1))

        # Debug Hitbox
        if ItemCard.SHOW_HITBOXES:
            debug_painter = QPainter(self)
            debug_painter.setPen(QPen(QColor(255, 0, 0, 150), 2))
            debug_painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def set_pixmap(self, pixmap):
        if not pixmap.isNull():
            self._original_pixmap = pixmap # Preserve for real-time scaling
            
            # Scale to fit the thumb_label's current size
            label_size = self.thumb_label.size()
            scaled = pixmap.scaled(
                label_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText("")
        else:
            self.thumb_label.setText(_("No Image"))

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Phase 28: Accept image file drag events."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ['.webp', '.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Phase 28: Handle dropped image files as custom thumbnails."""
        if not event.mimeData().hasUrls(): return
        
        urls = event.mimeData().urls()
        if not urls: return  # Guard against None
        
        for url in urls:
            if not url.isLocalFile(): continue
            
            src_path = url.toLocalFile()
            ext = os.path.splitext(src_path)[1].lower()
            if ext not in ['.webp', '.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                continue
            
            # Process and register thumbnail
            try:
                # Comprehensive null checks
                if not getattr(self, 'thumbnail_manager', None):
                    logging.getLogger("ItemCard").warning("Thumbnail drop: thumbnail_manager not set")
                    continue
                if not getattr(self, 'storage_root', None):
                    logging.getLogger("ItemCard").warning("Thumbnail drop: storage_root not set")
                    continue
                if not getattr(self, 'db', None):
                    logging.getLogger("ItemCard").warning("Thumbnail drop: db not set")
                    continue
                if not getattr(self, 'path', None):
                    logging.getLogger("ItemCard").warning("Thumbnail drop: path not set")
                    continue
                if not getattr(self, 'app_name', None):
                    logging.getLogger("ItemCard").warning("Thumbnail drop: app_name not set")
                    continue
                    
                # Get relative path for this card
                rel = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
                if not rel:
                    logging.getLogger("ItemCard").warning("Thumbnail drop: rel_path is empty")
                    continue
                
                # Destination path in resource directory
                dest_path = self.thumbnail_manager.get_thumbnail_path(self.app_name, rel)
                if not dest_path:
                    logging.getLogger("ItemCard").warning("Thumbnail drop: dest_path not returned")
                    continue
                dest_dir = os.path.dirname(dest_path)
                os.makedirs(dest_dir, exist_ok=True)
                
                # Copy and resize via thumbnail manager (or direct copy for quality)
                shutil.copy2(src_path, dest_path)
                
                # Update database - IMPORTANT: Register both image_path AND manual_preview_path
                # image_path is used for card thumbnail display and RegionEdit
                # manual_preview_path is for multi-preview functionality
                self.manual_preview_path = dest_path
                self.db.update_folder_display_config(rel, manual_preview_path=dest_path, image_path=dest_path)
                
                # Refresh card display
                if self.loader:
                    self.thumb_label.setText(_("Loading..."))
                    self.loader.load_image(dest_path, QSize(256, 256), self.set_pixmap)
                    
            except Exception as e:
                import traceback
                logging.getLogger("ItemCard").error(f"Failed to register dropped thumbnail: {e}")
                traceback.print_exc()
            
            break  # Only handle first valid image

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

    def update_hidden(self, is_hidden: bool):
        """Update the hidden state and refresh visual style."""
        self.is_hidden = is_hidden
        self._update_style()

    def mousePressEvent(self, event):
        """Pass click event to parent for centralized multi-selection handling."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is on URL overlay (QLabel)
            if hasattr(self, 'url_overlay') and self.url_overlay.isVisible():
                if self.url_overlay.geometry().contains(event.pos()):
                    self._open_first_working_url()
                    return
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
        from src.ui.link_master.dialogs_legacy import URLListDialog
        
        rel_path = None
        if self.db and self.storage_root and self.path:
            try:
                rel_path = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
            except:
                pass
        
        current_json = getattr(self, 'url_list', '[]') or '[]'
        
        dialog = URLListDialog(self, url_list_json=current_json)
        if dialog.exec():
            new_json = dialog.get_data()
            self.url_list = new_json
            
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

    def _deploy_link(self):
        if not self.deployer: return
        
        target_link = self.target_override or os.path.join(self.target_dir, self.folder_name)
        if not target_link: return
            
        # Use deploy_with_rules for Phase 16 & 18.15
        if self.deployer.deploy_with_rules(self.path, target_link, self.deployment_rules, 
                                           deploy_type=self.deploy_type, 
                                           conflict_policy=self.conflict_policy):
            self._check_link_status()
            self._update_style()
            self.deploy_changed.emit()  # Notify parent to refresh
        else:
             QMessageBox.warning(self, "Error", "Deploy failed. Check logs or permissions.")


    def _remove_link(self):
        if not self.deployer: return
        
        if self.target_override:
            target_link = self.target_override
        elif self.target_dir:
            target_link = os.path.join(self.target_dir, self.folder_name)
        else:
            return
            
        if self.deployer.remove_link(target_link, source_path_hint=self.path):
             self._check_link_status()
             self._update_style()
             self.deploy_changed.emit()  # Notify parent to refresh
        else:
             QMessageBox.warning(self, "Error", "Remove failed.")

             
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
        # print(f"[Profiling] ItemCard._toggle_visibility: path={self.path}, is_hidden={self.is_hidden}")
        
        if self.db:
            try:
                # Standardize path for DB
                rel = self.path
                if hasattr(self, 'storage_root') and self.storage_root:
                    rel = os.path.relpath(self.path, self.storage_root).replace('\\', '/')
                else:
                    rel = rel.replace('\\', '/')

                self.db.update_folder_display_config(rel, is_visible=(0 if self.is_hidden else 1))
                # print(f"[Profiling] DB Updated: {rel} is_visible={0 if self.is_hidden else 1}")
            except Exception as e:
                print(f"Error updating visibility: {e}")
        
        # Use partial update instead of full refresh
        self.update_hidden(self.is_hidden)
        # print("[Profiling] Used update_hidden for partial update (no deploy_changed emit)")

    def toggle_deployment(self):
        """Phase 19.5: Public API to toggle deployment state."""
        if not self.deployer or not self.target_dir: return
        self._check_link_status()
        if self.link_status == 'linked':
            self._remove_link()
        elif self.link_status == 'none':
            self._deploy_link()
    
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
        
        # Re-scale original pixmap to display size (high quality)
        if hasattr(self, '_original_pixmap') and self._original_pixmap:
            label_size = self.thumb_label.size()
            
            # Optimization: Skip if already scaled to this size
            if hasattr(self, "_last_scaled_size") and self._last_scaled_size == label_size:
                pass
            elif self._original_pixmap and not self._original_pixmap.isNull():
                t_scale = time.perf_counter()
                scaled = self._original_pixmap.scaled(
                    label_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumb_label.setPixmap(scaled)
                dt_s = time.perf_counter() - t_scale
                ItemCard._total_scale_time += dt_s
                ItemCard._scale_count += 1
                self._last_scaled_size = label_size
        
        self._update_style()  # Apply border/background based on link status
        self._update_icon_overlays() # Ensure icons are positioned for new size
        self.update()
        
        # --- Phase 24: Mode-specific layout ---
        mode = getattr(self, '_display_mode', 'image_text')
        is_mini = mode == 'mini_image'
        is_text_only = mode == 'text_list'
        
        # Set margins - centering is handled by Qt.AlignCenter on widget add
        margin_h = 4
        margin_t = 2
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
