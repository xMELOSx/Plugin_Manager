""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import os
import json
import logging
import copy
import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QLineEdit, QPushButton, QTreeView, QSplitter, QScrollArea, QMessageBox,
                             QTabWidget, QInputDialog, QFileDialog, QMenu, QApplication, QDialog,
                             QWidgetAction, QSlider, QFrame, QSpinBox)
from PyQt6.QtCore import Qt, QDir, QSize, QEvent
from PyQt6.QtGui import QFileSystemModel, QPixmap, QIcon, QColor, QImage
from src.core.lang_manager import _

from src.ui.frameless_window import FramelessWindow
from src.ui.title_bar_button import TitleBarButton
from src.ui.window_mixins import OptionsMixin
from src.components.sub_windows import OptionsWindow, HelpWindow
from src.ui.link_master.dialogs import AppRegistrationDialog, ImportTypeDialog
from src.core.image_loader import ImageLoader
from src.core.link_master.database import get_lm_registry, get_lm_db
from src.core.link_master.scanner import Scanner
from src.ui.flow_layout import FlowLayout
from src.ui.link_master.item_card import ItemCard
from src.core.link_master.deployer import Deployer
from src.ui.link_master.single_folder_proxy import SingleFolderProxyModel
from src.ui.link_master.explorer_window import ExplorerPanel # Renamed
from src.ui.link_master.presets_panel import PresetsPanel
from src.ui.link_master.notes_panel import NotesPanel
from src.ui.link_master.library_panel import LibraryPanel
from src.core.link_master.thumbnail_manager import ThumbnailManager
from src.apps.scanner_worker import ScannerWorker
from src.apps.size_scanner_worker import SizeScannerWorker
from PyQt6.QtCore import QThread, QTimer

# Refactoring Phase 4: Functional Mixin split
from src.apps.lm_batch_deployment_ops import LMDeploymentOpsMixin
from src.apps.lm_batch_file_ops import LMFileOpsMixin
from src.apps.lm_presets import LMPresetsMixin
from src.apps.lm_trash import LMTrashMixin
from src.apps.lm_search import LMSearchMixin
from src.apps.lm_selection import LMSelectionMixin
from src.apps.lm_card_settings import LMCardSettingsMixin
from src.apps.lm_display import LMDisplayMixin
from src.apps.lm_navigation import LMNavigationMixin
from src.apps.lm_scan_handler import LMScanHandlerMixin
from src.apps.lm_import import LMImportMixin
from src.apps.lm_tags import LMTagsMixin
from src.apps.lm_card_pool import LMCardPoolMixin
from src.apps.lm_portability import LMPortabilityMixin
from src.ui.link_master.help_sticky import StickyHelpWidget
from src.core.link_master.help_manager import StickyHelpManager
from src.apps.lm_file_management import LMFileManagementMixin

# Factory Modules
from .lm_ui_factory import setup_ui
from .lm_context_menu_factory import create_item_context_menu

from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

from src.ui.toast import Toast

class LinkMasterWindow(LMCardPoolMixin, LMTagsMixin, LMFileManagementMixin, LMPortabilityMixin, LMImportMixin, LMScanHandlerMixin, LMNavigationMixin, LMDisplayMixin, LMCardSettingsMixin, LMDeploymentOpsMixin, LMFileOpsMixin, LMPresetsMixin, LMTrashMixin, LMSearchMixin, LMSelectionMixin, FramelessWindow, OptionsMixin):
    def __init__(self):
        self._init_start_t = time.perf_counter()
        super().__init__()
        self.setObjectName("LinkMasterWindow")
        self.logger = logging.getLogger("LinkMasterWindow")
        self.logger.info(f"[Profile] super().__init__() took {time.perf_counter()-self._init_start_t:.3f}s")
        t_base = time.perf_counter()
        self.registry = get_lm_registry()
        self.db = get_lm_db() # App DB (Initializes with current app later)
        self.scanner = Scanner()
        self.image_loader = ImageLoader()
        self.deployer = Deployer()
        self.logger.info(f"[Profile] Core (Scanner/Deployer) init took {time.perf_counter()-t_base:.3f}s")
        t_pool = time.perf_counter()
        
        # Phase 19: Multi-Selection State
        self.selected_paths = set()
        self._last_selected_path = None
        
        # Phase 28: Card Pooling
        self._init_card_pool()
        self.logger.info(f"[Profile] _init_card_pool took {time.perf_counter()-t_pool:.3f}s")
        t_misc = time.perf_counter()
        
        # Initialize Thumbnail Manager (resource/app in Project Root)
        # Initialize Thumbnail Manager (resource/app in Project Root)
        import sys
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resource_path = os.path.join(project_root, "resource", "app")
        
        t_thumb = time.perf_counter()
        self.thumbnail_manager = ThumbnailManager(resource_path)
        self.logger.info(f"[Profile] ThumbnailManager init took {time.perf_counter()-t_thumb:.3f}s")
        t_thread = time.perf_counter()
        
        # Threaded Scanner Setup
        self.scanner_thread = QThread()
        # Phase 19.x: Dual-Worker Scanning (Prevents race conditions on simultaneous area refreshes)
        self.cat_scanner_worker = ScannerWorker(self.scanner, self.deployer, self.db)
        self.pkg_scanner_worker = ScannerWorker(self.scanner, self.deployer, self.db)
        
        self.cat_scanner_worker.moveToThread(self.scanner_thread)
        self.pkg_scanner_worker.moveToThread(self.scanner_thread)
        
        # Connect the run method to the thread's started signal for both workers
        self.scanner_thread.started.connect(self.cat_scanner_worker.run)
        self.scanner_thread.started.connect(self.pkg_scanner_worker.run)

        self.cat_scanner_worker.results_ready.connect(self._on_scan_results_ready)
        self.pkg_scanner_worker.results_ready.connect(self._on_scan_results_ready)
        self.cat_scanner_worker.finished.connect(self._on_scan_finished)
        self.pkg_scanner_worker.finished.connect(self._on_scan_finished)
        
        self.scanner_thread.start()
        self.logger.info(f"[Profile] Scanner thread start took {time.perf_counter()-t_thread:.3f}s")
        t_icon = time.perf_counter()
        
        # Icon Setup (User Request)
        icon_path = os.path.abspath(os.path.join("src", "resource", "icon", "icon.jpg"))
        if os.path.exists(icon_path):
            self.set_window_icon_from_path(icon_path)
            self.icon_label.mousePressEvent = self._icon_mouse_press
        self.logger.info(f"[Profile] Icon setup took {time.perf_counter()-t_icon:.3f}s")
        t_win_state = time.perf_counter()
        
        # State
        self.current_app_id = None
        self.current_target_key = "target_root" # target_root or target_root_2
        self.selected_paths = set()
        self.non_inheritable_tags = set()
        self.current_path = None  # Track current path for reload

        self.storage_root = None  # Unified storage root path
        
        # Preset Filter State
        self.preset_filter_mode = False  # When True, only show preset items
        self.preset_filter_paths = set()  # Set of storage_rel_paths in the preset
        self.preset_filter_categories = set()  # Parent categories of preset items
        
        # Link Filter State (for linked/unlinked category filtering)
        self.link_filter_mode = None  # 'linked', 'unlinked', or None
        self.favorite_filter_mode = False
        self.show_hidden = False  # Show hidden folders toggle

        # Phase 4 Style Sync: Base Button Styles
        self.btn_normal_style = "background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 2px;"
        self.btn_selected_style = "background-color: #3498db; color: #fff; border: 1px solid #5dade2; border-radius: 4px; padding: 2px; font-weight: bold;"
        self.btn_no_override_style = "background-color: #2c3e50; color: #888; border: 1px solid #444; border-radius: 4px; padding: 2px;"

        # Initialize panel attributes to None to avoid early Access AttributeError
        self.library_panel = None
        self.presets_panel = None
        self.notes_panel = None
        self.tools_panel = None
        self.explorer_panel = None

        
        self.resize(1400, 850)
        self.logger.info(f"[Profile] Window/State setup took {time.perf_counter()-t_win_state:.3f}s")
        
        # Explorer is now embedded, not a window
        
        self._init_title_buttons()
        # Drag & Drop Support
        self.setAcceptDrops(True)
        self.logger.info(f"[Profile] Misc setup took {time.perf_counter()-t_misc:.3f}s")
        
        self._init_ui()
        
        # Initialize Toast for notifications
        # Position below header/tag bar (approx 100px)
        self._toast = Toast(self, y_offset=100)
        
        
        # Sub Windows - Moved to lazy loading in toggle_options to prevent alpha stacking on startup
        self.options_window = None
        self.help_manager = None 
        
        # self.help_window = HelpWindow()
        # self.help_window.setParent(self, self.help_window.windowFlags())
        # self.help_window.closed.connect(self._on_help_window_closed)

        t_load = time.perf_counter()
        self._load_apps()
        # Connect to language change signal for real-time translation
        from src.core.lang_manager import get_lang_manager
        get_lang_manager().language_changed.connect(self.retranslate_ui)
        
        self.logger.info(f"[Profile] _load_apps took {time.perf_counter()-t_load:.3f}s")
        
        t_options = time.perf_counter()
        self.load_options("link_master")
        # Fix double opacity: Reset global window opacity to 1.0
        # We handle transparency via paintEvent (bg_opacity) and stylesheets (content_opacity)
        self.setWindowOpacity(1.0)
        self._load_opacity_settings()  # Load opacity without needing OptionsWindow
        
        self.setWindowOpacity(1.0)
        self._load_opacity_settings()  # Load opacity without needing OptionsWindow
        
        # User Instruction: Print transparency values at window creation
        # print(f"DEBUG: Window Creation - Transparency 1 (windowOpacity): {self.windowOpacity()}")
        # print(f"DEBUG: Window Creation - Transparency 2 (bg_opacity): {getattr(self, '_bg_opacity', 'N/A')}")
        
        self.logger.info(f"[Profile] load_options took {time.perf_counter()-t_options:.3f}s")
        
        self.logger.info(f"[Profile] Total LinkMasterWindow startup took {time.perf_counter()-self._init_start_t :.3f}s")
        
        # Centralized Card Settings State (Phase 19.x)
        self.card_settings = {}
        self._load_card_settings()
        
        # Sane Defaults for each mode (Base Sizes)
        self._init_mode_settings()
        
        # Restore last selected app and path (Handled by _restore_last_state via QTimer)

        
        # Display Overrides & Lock State (Phase 25)
        self.cat_display_override = None
        self.pkg_display_override = None
        self.display_mode_locked = False
        
        # Restore window/view state (Phase 18.12 + 25)
        self._always_on_top = False # Initialize state
        self._restore_ui_state()
        
        t_init_end = time.perf_counter()
        self.logger.info(f"[Profile] _init_ui total took {t_init_end - self._init_start_t:.3f}s")
        
        # Navigation History (Phase 28)
        self.nav_history = []
        self.nav_index = -1
        self._is_navigating_history = False
        
        # Optimization: QuickView Caching (Separated by Scope)
        self.cat_quick_view_dialog = None
        self.pkg_quick_view_dialog = None
        # Override btn_quick_manage behavior if it exists
        if hasattr(self, 'btn_quick_manage'):
            try:
                self.btn_quick_manage.clicked.disconnect()
            except: pass
            self.btn_quick_manage.installEventFilter(self)
            
        # Phase 15: Override btn_pkg_quick_manage behavior
        if hasattr(self, 'btn_pkg_quick_manage'):
            try:
                self.btn_pkg_quick_manage.clicked.disconnect()
            except: pass
            self.btn_pkg_quick_manage.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle custom events, specifically Right Click on Quick Manage buttons."""
        # Category Quick Manage
        if hasattr(self, 'btn_quick_manage') and obj == self.btn_quick_manage:
            if event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.RightButton:
                    self._open_quick_view_delegate(scope="category")
                    return True
        
        # Package Quick Manage
        if hasattr(self, 'btn_pkg_quick_manage') and obj == self.btn_pkg_quick_manage:
            if event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.RightButton:
                    self._open_quick_view_delegate(scope="package")
                    return True
                    
        return super().eventFilter(obj, event)

    def _save_card_settings(self):
        """Save card settings dictionary to Global DB as JSON.
        
        Phase 25: Continued using Registry (DB) for card sizes/scales as requested.
        """
        try:
            blob = json.dumps(self.card_settings)
            self.registry.set_setting('link_master_card_config', blob)
        except Exception as e:
            self.logger.error(f"Failed to save card settings: {e}")

    def save_options(self, key_prefix: str):
        """Override to include display overrides and lock state in JSON (config/window.json)"""
        # Check if OptionsWindow's 'Remember Position/Size' is enabled
        save_geo = True
        if hasattr(self, 'options_window') and self.options_window:
            save_geo = self.options_window.get_remember_geo()
        
        extra_data = {
            'display_mode_locked': self.display_mode_locked,
            'save_window_state': save_geo
        }
        if self.display_mode_locked:
            extra_data['cat_display_override'] = self.cat_display_override
            extra_data['pkg_display_override'] = self.pkg_display_override
        
        # Save sidebar splitter sizes
        if hasattr(self, 'sidebar_splitter'):
            # Preference: 1. Current sizes if visible, 2. Last cached sizes, 3. Empty (last resort)
            drawer_visible = self.drawer_widget.isVisible()
            has_cached = hasattr(self, '_last_splitter_sizes') and self._last_splitter_sizes
            
            if drawer_visible:
                # Use real-time sizes when visible
                sizes = self.sidebar_splitter.sizes()
                extra_data['sidebar_splitter_sizes'] = sizes
                self._last_splitter_sizes = sizes # Update cache
                # self.logger.info(f"[save_options] Saving visible splitter sizes: {sizes}")
            elif has_cached:
                # Use cache if hidden (splitter returns [0, X] when collapsed/hidden)
                extra_data['sidebar_splitter_sizes'] = self._last_splitter_sizes
                # self.logger.info(f"[save_options] Saving cached splitter sizes: {self._last_splitter_sizes}")
            else:
                self.logger.warning("[save_options] No splitter sizes to save!")
        
        # Save explorer panel width
        if hasattr(self, '_explorer_panel_width'):
            extra_data['explorer_panel_width'] = self._explorer_panel_width
            
        super().save_options(key_prefix, extra_data=extra_data)

    def load_options(self, key_prefix: str):
        """Override to restore display overrides and lock state from JSON"""
        data = super().load_options(key_prefix)
        if data:
            self.display_mode_locked = data.get('display_mode_locked', False)
            if self.display_mode_locked:
                # Only restore overrides if they were actually set (not None)
                saved_cat = data.get('cat_display_override')
                saved_pkg = data.get('pkg_display_override')
                if saved_cat:
                    self.cat_display_override = saved_cat
                if saved_pkg:
                    self.pkg_display_override = saved_pkg
                    
                # Update UI only if overrides were loaded
                if saved_cat or saved_pkg:
                    self._update_override_buttons()
            
            # Sync Pin button state
            if 'always_on_top' in data and hasattr(self, 'pin_btn'):
                is_pinned = data['always_on_top']
                if self.pin_btn.toggled_state != is_pinned:
                    self.pin_btn._force_state(is_pinned) # Avoid triggering clicked signal
            
            # Restore sidebar splitter sizes (deferred to after UI is ready)
            splitter_sizes = data.get('sidebar_splitter_sizes')
            if splitter_sizes and hasattr(self, 'sidebar_splitter'):
                self._pending_splitter_sizes = splitter_sizes
                self._last_splitter_sizes = splitter_sizes # Phase 1.0.8: Initialize cache on startup!
            
            # Restore explorer panel width
            explorer_width = data.get('explorer_panel_width')
            if explorer_width:
                self._explorer_panel_width = explorer_width
                    
            return data
        return None

    def _load_opacity_settings(self):
        """Load opacity settings directly from window.json without needing OptionsWindow."""
        try:
            import json
            import os
            from src.core.file_handler import FileHandler
            
            project_root = FileHandler().project_root
            path = os.path.join(project_root, "config", "window.json")
            if not os.path.exists(path):
                return
                
            content = FileHandler().read_text_file(path)
            all_config = json.loads(content)
            settings = all_config.get('options_window', {})
            
            if settings:
                bg_opacity = settings.get('bg_opacity', 90) / 100.0
                text_opacity = settings.get('text_opacity', 100) / 100.0
                self.set_background_opacity(bg_opacity)
                self.set_content_opacity(text_opacity)
        except Exception as e:
            self.logger.warning(f"Failed to load opacity settings: {e}")


    def _load_card_settings(self):
        """Load card settings dictionary from Global DB."""
        try:
            import json
            blob = self.registry.get_setting('link_master_card_config')
            if blob:
                self.card_settings = json.loads(blob)
            else:
                self.card_settings = {}
        except Exception as e:
            self.logger.error(f"Failed to load card settings: {e}")
            self.card_settings = {}

    def _get_card_setting(self, key, default):
        """Helper to get a card setting with a default value."""
        return self.card_settings.get(key, default)

    
    def _init_mode_settings(self):
        """Initialize base size settings for all display modes using centralized dictionary."""
        defaults = {
            # Category Defaults
            'cat_text_list_card_w': 280, 'cat_text_list_card_h': 40,
            'cat_text_list_img_w': 0, 'cat_text_list_img_h': 0,
            'cat_mini_image_card_w': 120, 'cat_mini_image_card_h': 120,
            'cat_mini_image_img_w': 100, 'cat_mini_image_img_h': 100,
            'cat_image_text_card_w': 160, 'cat_image_text_card_h': 220,
            'cat_image_text_img_w': 140, 'cat_image_text_img_h': 140,
            
            # Package Defaults
            'pkg_text_list_card_w': 280, 'pkg_text_list_card_h': 40,
            'pkg_text_list_img_w': 0, 'pkg_text_list_img_h': 0,
            'pkg_mini_image_card_w': 120, 'pkg_mini_image_card_h': 120,
            'pkg_mini_image_img_w': 100, 'pkg_mini_image_img_h': 100,
            'pkg_image_text_card_w': 160, 'pkg_image_text_card_h': 220,
            'pkg_image_text_img_w': 140, 'pkg_image_text_img_h': 140,
            
            # Independent Scales per Mode (Requirement)
            'cat_text_list_scale': 1.0,
            'cat_mini_image_scale': 1.0,
            'cat_image_text_scale': 1.0,
            'pkg_text_list_scale': 1.0,
            'pkg_mini_image_scale': 1.0,
            'pkg_image_text_scale': 1.0,
            
            # Phase 31: Visibility Toggles
            'cat_text_list_show_link': True, 'cat_text_list_show_deploy': True,
            'cat_mini_image_show_link': True, 'cat_mini_image_show_deploy': True,
            'cat_image_text_show_link': True, 'cat_image_text_show_deploy': True,
            'pkg_text_list_show_link': True, 'pkg_text_list_show_deploy': True,
            'pkg_mini_image_show_link': True, 'pkg_mini_image_show_deploy': True,
            'pkg_image_text_show_link': True, 'pkg_image_text_show_deploy': True,
        }
        
        # Merge defaults into card_settings if keys are missing
        for k, v in defaults.items():
            if k not in self.card_settings:
                self.card_settings[k] = v
        
        # Phase 19.x: Map dictionary keys to instance attributes for legacy code/UI compatibility
        # This allows self.cat_scale etc to still work while being backed by card_settings
        for k, v in self.card_settings.items():
            setattr(self, k, v)


    
    
    def closeEvent(self, event):
        """Save geometry and UI state on close, and close subwindows."""
        # 1. Save last viewed app/path
        self._save_last_state()
        
        # 2. Save category view height (Persistent per system)
        if hasattr(self, '_category_fixed_height'):
            self.registry.set_global("category_view_height", self._category_fixed_height)
        
        # 3. Save persistent window options (JSON)
        self.save_options("link_master")
        
        # 4. Save UI layout states (Splitters, Panel columns) to DB
        self._save_ui_state()
        
        # 5. Close help (and save help data via help_manager if needed)
        if hasattr(self, 'help_manager') and self.help_manager:
            if self.help_manager.is_edit_mode:
                self.help_manager.save_all()
            self.help_manager.hide_all()

        # 6. Close subwindows
        if hasattr(self, 'options_window') and self.options_window:
            self.options_window.close()
        if hasattr(self, 'help_window') and self.help_window:
            self.help_window.close()
        if hasattr(self, 'debug_window') and self.debug_window:
            self.debug_window.close()
            
        super().closeEvent(event)
    
    def _on_splitter_moved(self, pos, index):
        """Save category view height when splitter is moved by user."""
        if hasattr(self, 'v_splitter'):
            sizes = self.v_splitter.sizes()
            if sizes and len(sizes) >= 1:
                self._category_fixed_height = sizes[0]
                self.registry.set_global("category_view_height", self._category_fixed_height)
    
    def _on_sidebar_splitter_moved(self, pos, index):
        """Cache sidebar splitter sizes when user resizes."""
        if hasattr(self, 'sidebar_splitter'):
            self._last_splitter_sizes = self.sidebar_splitter.sizes()
    
    def resizeEvent(self, event):
        """Maintain fixed category height on window resize."""
        super().resizeEvent(event)
        # Apply fixed category height after resize using timer to ensure layout is complete
        if hasattr(self, 'v_splitter') and hasattr(self, '_category_fixed_height'):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._apply_fixed_category_height)
    
    def _apply_fixed_category_height(self):
        """Force-apply the fixed category height to the splitter."""
        if not hasattr(self, 'v_splitter') or not hasattr(self, '_category_fixed_height'):
            return
        total_height = self.v_splitter.height()
        cat_height = self._category_fixed_height
        # Ensure category doesn't exceed total height minus minimum package area
        cat_height = min(cat_height, total_height - 100)
        cat_height = max(50, cat_height)  # Minimum 50px for category
        pkg_height = total_height - cat_height
        self.v_splitter.setSizes([cat_height, pkg_height])

    
    def _read_version(self):
        """Read version from src/core/version.py."""
        from src.core.version import VERSION
        return VERSION
    
    def _restore_last_app(self):
        """Restore last selected app from registry."""
        try:
            last_app_id = self.registry.get_setting("linkmaster_last_app")
            if last_app_id:
                app_id = int(last_app_id)
                for i in range(self.app_combo.count()):
                    data = self.app_combo.itemData(i)
                    if data and data.get('id') == app_id:
                        self.app_combo.setCurrentIndex(i)
                        break
        except:
            pass

    def _init_title_buttons(self):
        # 1. Deploy Mode Indicator (Symlink vs Copy)
        self.mode_indicator = QLabel("●")
        self.mode_indicator.setObjectName("deploy_mode_indicator")
        self.mode_indicator.setContentsMargins(0, 0, 8, 0)
        self.add_title_bar_widget(self.mode_indicator, index=0)

        # Runs initial baseline test (temp dir)
        self._update_deploy_mode_indicator(None)

        # 2. Pin Button
        self.pin_btn = TitleBarButton("📌", is_toggle=True)
        self.pin_btn.setObjectName("titlebar_pin_btn")
        self.pin_btn.clicked.connect(self.toggle_pin_click)
        self.add_title_bar_button(self.pin_btn, index=1)
        
        # 3. Help Button
        self.help_btn = TitleBarButton("?", is_toggle=True)
        self.help_btn.setObjectName("titlebar_help_btn")
        self.help_btn.clicked.connect(self.toggle_help)
        self.help_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.help_btn.customContextMenuRequested.connect(self._show_help_button_menu)
        self.add_title_bar_button(self.help_btn, index=2)

        # 4. Option Button
        self.opt_btn = TitleBarButton("⚙", is_toggle=True)
        self.opt_btn.setObjectName("titlebar_options_btn")
        self.opt_btn.clicked.connect(self.toggle_options)
        self.add_title_bar_button(self.opt_btn, index=3)

        # 5. Favorite Switcher Area (Next to Title)
        # We insert this after the title label in the title bar layout
        # index 0: icon_label, index 1: title_label, index 2: STRETCH
        self.fav_switcher_container = QWidget()
        self.fav_switcher_container.setObjectName("fav_switcher_container")
        self.fav_switcher_layout = QHBoxLayout(self.fav_switcher_container)
        self.fav_switcher_layout.setContentsMargins(5, 0, 5, 0)
        self.fav_switcher_layout.setSpacing(2)
        
        # In FramelessWindow._init_frameless_ui:
        # self.title_bar_layout.addWidget(self.icon_label) # index 0
        # self.title_bar_layout.addWidget(self.title_label) # index 1
        # self.title_bar_layout.addStretch() # index 2
        # We want it between title and stretch.
        self.title_bar_layout.insertWidget(2, self.fav_switcher_container)

    def _update_deploy_mode_indicator(self, target_dir: str = None):
        """Re-test symlink capability and update UI indicator."""
        self._symlink_available = self._test_symlink_capability(target_dir)
        
        if self._symlink_available:
            self.mode_indicator.setStyleSheet("color: #27ae60; font-size: 14px;")  # Green
            self.mode_indicator.setToolTip(_("シンボリックリンクが作成できる状態です"))
        else:
            self.mode_indicator.setStyleSheet("color: #888888; font-size: 14px;")  # Gray
            msg = _("シンボリックリンクが使用できない（またはこのドライブで制限されている）ため、自動でコピーモードになります")
            self.mode_indicator.setToolTip(msg)
        
        # Propagate to deployer
        if hasattr(self, 'deployer'):
            self.deployer.allow_symlinks = self._symlink_available

    def _test_symlink_capability(self, target_dir: str = None) -> bool:
        """
        Test if the application can create symbolic links.
        If target_dir is provided, tests inside it to account for filesystem constraints.
        """
        import os
        import tempfile
        import uuid
        
        # Determine where to test
        base_dir = target_dir if target_dir and os.path.isdir(target_dir) else tempfile.gettempdir()
        
        src_path = None
        link_path = os.path.join(base_dir, f"lm_sym_test_src_{uuid.uuid4()}")
        link_target = os.path.join(base_dir, f"lm_sym_test_link_{uuid.uuid4()}")
        
        try:
            # Step 1: Create a source file in the base dir
            with open(link_path, 'w') as f:
                f.write("test")
            src_path = link_path
            
            try:
                # Step 2: Try to create a symlink to it
                os.symlink(src_path, link_target)
                # Success! Clean up immediately
                if os.path.exists(link_target):
                    os.remove(link_target)
                return True
            except (OSError, AttributeError):
                # Failed (e.g., privilege error or filesystem limitation like FAT32/exFAT)
                return False
            finally:
                # Cleanup src
                if src_path and os.path.exists(src_path):
                    os.remove(src_path)
                if os.path.exists(link_target):
                    try: os.remove(link_target)
                    except: pass
        except:
            # Probably no write permission in the target folder
            return False


    def _restore_ui_state(self):
        """Restore UI persistent state (splitters, panels)."""
        if not self.db: return
        try:
            # Restore Sidebar Splitter
            splitter_state = self.db.get_setting('sidebar_splitter_state')
            if splitter_state and hasattr(self, 'sidebar_splitter'):
                from PyQt6.QtCore import QByteArray
                self.sidebar_splitter.restoreState(QByteArray.fromHex(splitter_state.encode()))
            
            # Restore Library Panel
            if hasattr(self, 'library_panel') and self.library_panel is not None:
                self.library_panel.restore_state()
                
        except Exception as e:
            self.logger.error(f"Failed to restore UI state: {e}")

    def _save_ui_state(self):
        """Save UI persistent state (splitters, panels)."""
        if not self.db: return
        try:
            # Save Sidebar Splitter
            if hasattr(self, 'sidebar_splitter'):
                state = self.sidebar_splitter.saveState().toHex().data().decode()
                self.db.set_setting('sidebar_splitter_state', state)
            
            # Save Library Panel
            if hasattr(self, 'library_panel') and self.library_panel is not None:
                self.library_panel.save_state()
                
            self.logger.info("Saved UI state (splitter/columns).")
        except Exception as e:
            self.logger.error(f"Failed to save UI state: {e}")

    def _init_ui(self):
        """Build the UI using the factory."""
        setup_ui(self)
        
    def retranslate_ui(self):
        """Update all UI strings when language changes."""
        # Header
        if hasattr(self, 'target_app_lbl'): self.target_app_lbl.setText(_("Target App:"))
        if hasattr(self, 'edit_app_btn'): self.edit_app_btn.setText(_("Edit"))
        if hasattr(self, 'register_app_btn'): self.register_app_btn.setToolTip(_("Register New App"))
        
        # Search
        if hasattr(self, 'search_logic'):
            self.search_logic.setItemText(0, _("OR"))
            self.search_logic.setItemText(1, _("AND"))
        if hasattr(self, 'search_bar'): self.search_bar.setPlaceholderText(_("Search by name or tags..."))
        if hasattr(self, 'search_global_chk'): self.search_global_chk.setText(_("Global"))
        
        # Sidebar Toggles
        if hasattr(self, 'btn_drawer'): self.btn_drawer.setToolTip(_("Toggle Explorer Panel"))
        if hasattr(self, 'btn_libraries'): self.btn_libraries.setToolTip(_("Library Management"))
        if hasattr(self, 'btn_presets'): self.btn_presets.setToolTip(_("Toggle Presets"))
        if hasattr(self, 'btn_notes'): self.btn_notes.setToolTip(_("Toggle Quick Notes"))
        if hasattr(self, 'btn_tools'): self.btn_tools.setToolTip(_("Special Actions"))
        
        # Nav etc
        if hasattr(self, 'btn_filter_linked'): self.btn_filter_linked.setToolTip(_("Show linked folders"))
        if hasattr(self, 'btn_filter_unlinked'): self.btn_filter_unlinked.setToolTip(_("Show unlinked folders"))
        if hasattr(self, 'btn_unlink_all'): self.btn_unlink_all.setToolTip(_("Unlink All"))
        if hasattr(self, 'btn_trash'): self.btn_trash.setToolTip(_("Open Trash"))
        
        # Main Area
        if hasattr(self, 'cat_title_lbl'): self.cat_title_lbl.setText(_("<b>Categories</b>"))
        if hasattr(self, 'btn_import_cat'): self.btn_import_cat.setToolTip(_("Import Folder or Zip to Categories"))
        if hasattr(self, 'btn_show_hidden'): self.btn_show_hidden.setToolTip(_("Show/Hide hidden folders"))
        if hasattr(self, 'btn_card_settings'): self.btn_card_settings.setToolTip(_("Card Size Settings"))
        
        if hasattr(self, 'pkg_title_lbl'): self.pkg_title_lbl.setText(_("<b>Packages</b>"))
        if hasattr(self, 'btn_import_pkg'): self.btn_import_pkg.setToolTip(_("Import Folder or Zip to Packages"))
        
        if hasattr(self, 'total_link_count_label'):
            self.total_link_count_label.setToolTip(_("Total Link Count"))
            # We need to maintain the current count
            count = getattr(self, '_last_total_links', 0)
            self.total_link_count_label.setText(_("Total Links: {count}").format(count=count))
        if hasattr(self, 'pkg_link_count_label'): self.pkg_link_count_label.setToolTip(_("Link Count In Category"))
        if hasattr(self, 'pkg_result_label'): self.pkg_result_label.setToolTip(_("Package Count"))
        
        # Update panels if they exist (using getattr for safety against uninitialized attributes)
        if getattr(self, 'library_panel', None): self.library_panel.retranslate_ui()
        if getattr(self, 'presets_panel', None): self.presets_panel.retranslate_ui()
        if getattr(self, 'notes_panel', None): self.notes_panel.retranslate_ui()
        if getattr(self, 'tools_panel', None): self.tools_panel.retranslate_ui()
        
        # Search & Logic
        if hasattr(self, 'search_bar'):
            self.search_bar.setPlaceholderText(_("Search by name or tags..."))
            if self.search_bar.text():
                self._perform_search()
        
        if hasattr(self, 'search_logic'):
            self.search_logic.setItemText(0, _("OR"))
            self.search_logic.setItemText(1, _("AND"))
            
        if hasattr(self, 'search_mode'):
            self.search_mode.setItemText(0, _("📦 All Packages"))
            self.search_mode.setItemText(1, _("📁 Categories Only"))
            self.search_mode.setItemText(2, _("📁+📦 Cats with Pkgs"))
        
        # Update explorer panel if it exists
        if hasattr(self, 'explorer_panel'):
            self.explorer_panel.retranslate_ui()
            
        # Reset card settings panel if it exists so it recreates with new language
        if hasattr(self, '_settings_panel'):
            self._settings_panel.deleteLater()
            delattr(self, '_settings_panel')
            
        # Phase 32: Force refresh of dynamic counts/labels
        self._apply_card_filters()

    def _on_tag_icon_updated(self, tag_value: str, image_path: str):
        """Persist tag icon change to the database and optionally copy/resize image."""
        if not self.db:
            return
        
        import json
        config_str = self.db.get_setting('frequent_tags_config', '[]')
        try:
            tags = json.loads(config_str)
        except:
            tags = []
            
        updated = False
        for tag in tags:
            # FIX: Use name as fallback if value is missing for backward compatibility
            vid = tag.get('value') or tag.get('name')
            if vid == tag_value:
                # Update image path
                if image_path:
                    # EXE compatibility: copy to resource if not already there? 
                    # For now just record the absolute path as requested.
                    tag['icon'] = image_path
                
                # We need to find the widget to get its current display_mode/prefer_emoji state
                if hasattr(self, 'tag_bar') and tag_value in self.tag_bar.widget_map:
                    w = self.tag_bar.widget_map[tag_value]
                    # FIX: Sync both path AND mode
                    tag['icon'] = image_path
                    tag['prefer_emoji'] = (getattr(w, 'display_mode', 'text') == 'text')
                
                updated = True
                break
        
        if updated:
            self.db.set_setting('frequent_tags_config', json.dumps(tags))
            self.logger.info(f"[TagIcon] Persisted icon/mode for tag '{tag_value}'")
            # Signal change to registry for other windows if necessary
            self.registry.set_setting('frequent_tags_config', json.dumps(tags))
        
        # Refresh tag bar if available
        if hasattr(self, 'tag_bar'):
            self.tag_bar.refresh_tags()

    def _save_card_settings_window(self):
        """Handle save from independent window."""
        self._save_card_settings()
        if hasattr(self, 'btn_card_settings'): self.btn_card_settings.setChecked(False)
        if self.card_settings_window: self.card_settings_window.hide()
        
        # Show Toast on Main Window (User Request)
        if hasattr(self, '_toast') and self._toast:
            self._toast.show_message(_("Card size saved!"), color="#5dade2", duration=2000)

    def _on_card_settings_closed(self):
        """Handle independent window closed via X button."""
        if hasattr(self, 'btn_card_settings'):
            self.btn_card_settings.setChecked(False)

    def _cancel_settings_window(self):
        """Handle cancel/reset from independent window."""
        self._cancel_settings()
        if hasattr(self, 'btn_card_settings'): self.btn_card_settings.setChecked(False)
        if self.card_settings_window: self.card_settings_window.hide()

    def _on_setting_param_changed(self, type_, mode, param, value):
        """Handle parameter changes from settings window."""
        if type_ == 'global' and param == 'deploy_button_opacity':
             self.deploy_button_opacity = value
             self.card_settings['deploy_button_opacity'] = value
             self._apply_card_params_to_layout('category', self.cat_display_override or 'mini_image')
             self._apply_card_params_to_layout('package', self.pkg_display_override or 'mini_image')
        else:
             self._set_mode_param(type_, mode, param, value)

    def _on_setting_scale_changed(self, type_, mode, scale):
        self._update_mode_scale(type_, mode, scale)

    def _on_setting_check_changed(self, type_, mode, param, value):
        self._set_mode_check_param(type_, mode, param, value)

    def _on_settings_tab_changed(self, index):
        """Automatically switch display mode when settings tab is changed."""
        modes = ["text_list", "mini_image", "image_text"]
        target_mode = modes[index]
        self._toggle_cat_display_mode(target_mode, force=True)
        self._toggle_pkg_display_mode(target_mode, force=True)

    def _show_settings_menu(self):
        """Show/toggle independent settings window."""
        # Cleanup legacy QFrame logic if exists
        if hasattr(self, '_settings_panel') and isinstance(self._settings_panel, QFrame):
             self._settings_panel.hide()
             self._settings_panel.deleteLater()
             del self._settings_panel

        if hasattr(self, 'card_settings_window') and self.card_settings_window and self.card_settings_window.isVisible():
            self.card_settings_window.hide()
            if hasattr(self, 'btn_card_settings'): self.btn_card_settings.setChecked(False)
            return

        if hasattr(self, 'btn_card_settings'): self.btn_card_settings.setChecked(True)

        if not hasattr(self, 'card_settings_window') or self.card_settings_window is None:
            from src.ui.link_master.card_settings_window import CardSettingsWindow
            
            # Prepare settings including volatile ones
            current_settings = self.card_settings 
            current_settings['deploy_button_opacity'] = getattr(self, 'deploy_button_opacity', 0.8)
            
            self.card_settings_window = CardSettingsWindow(current_settings, getattr(self, 'display_mode_locked', False))
            
            # Connect Signals
            self.card_settings_window.paramChanged.connect(self._on_setting_param_changed)
            self.card_settings_window.scaleChanged.connect(self._on_setting_scale_changed)
            self.card_settings_window.checkChanged.connect(self._on_setting_check_changed)
            self.card_settings_window.lockToggled.connect(self._on_display_lock_toggled)
            self.card_settings_window.saveRequested.connect(self._save_card_settings_window)
            self.card_settings_window.cancelRequested.connect(self._cancel_settings_window)
            self.card_settings_window.closed.connect(self._on_card_settings_closed)
            
            # Connect Tab Change (Directly access tabs widget)
            if hasattr(self.card_settings_window, 'tabs'):
                self.card_settings_window.tabs.currentChanged.connect(self._on_settings_tab_changed)

            # Initial Tab Selection
            cur_mode = self.cat_display_override
            if not cur_mode:
                if hasattr(self, 'btn_cat_text') and 'selected' in self.btn_cat_text.styleSheet(): cur_mode = "text_list"
                elif hasattr(self, 'btn_cat_image') and 'selected' in self.btn_cat_image.styleSheet(): cur_mode = "mini_image"
                else: cur_mode = "image_text"

            mode_to_tab = {"text_list": 0, "mini_image": 1, "image_text": 2}
            self.card_settings_window.tabs.setCurrentIndex(mode_to_tab.get(cur_mode, 1))

        # Always update backup on show (Start of transaction)
        self._settings_backup = copy.deepcopy(self.card_settings)
        self._overrides_backup = (self.cat_display_override, self.pkg_display_override)

        self.card_settings_window.show()
        self.card_settings_window.activateWindow()



    

    def _get_quick_view_data(self, scope="all"):
        """Prepare items data for QuickView. Scope can be 'all', 'category', or 'package'."""
        from src.ui.link_master.item_card import ItemCard
        from src.core.lang_manager import _
        import os
        import re
        from PyQt6.QtWidgets import QMessageBox

        # Helper to traverse layout
        def get_all_widgets(layout):
            widgets = []
            if not layout: return widgets
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item.widget():
                    widgets.append(item.widget())
                elif item.layout():
                    widgets.extend(get_all_widgets(item.layout()))
            return widgets

        # Determine layouts based on scope
        ui_obj = self # window itself
        target_layouts = []
        if scope in ["all", "category"]:
            if hasattr(ui_obj, 'cat_layout'): target_layouts.append(ui_obj.cat_layout)
        if scope in ["all", "package"]:
            if hasattr(ui_obj, 'pkg_layout'): target_layouts.append(ui_obj.pkg_layout)
        
        items_data = []
        
        for lay in target_layouts:
            widgets = get_all_widgets(lay)
            for w in widgets:
                if not isinstance(w, ItemCard):
                    continue
                if not w.isVisible(): # Skip filtered out items
                    continue
                
                # Extract current state from card
                rel_path = None
                if self.storage_root:
                    try:
                        rel_path = os.path.relpath(w.path, self.storage_root).replace('\\', '/')
                    except: continue
                
                if not rel_path: continue
                
                # Exclude _Trash and hidden folders
                if "_Trash" in rel_path or "_hidden" in rel_path:
                    continue
                
                items_data.append({
                    'rel_path': rel_path,
                    'display_name': getattr(w, 'display_name', ''),
                    'tags': getattr(w, 'tags_raw', ''),
                    'image_path': getattr(w, 'image_path_raw', getattr(w, '_current_image_path', '')),
                    'is_favorite': getattr(w, 'is_favorite', False),
                    'score': getattr(w, 'score', 0)
                })
        
        # Sort items_data
        def natural_sort_key(d):
            path = d.get('rel_path', '').lower()
            return [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', path)]
        items_data.sort(key=natural_sort_key)
        
        return items_data

    def _open_quick_view_cached(self, scope="category"):
        """Mode 1: Cached QuickView (Reuse instance). scope=('category'|'package')"""
        from PyQt6.QtWidgets import QMessageBox
        from src.core.lang_manager import _

        items_data = self._get_quick_view_data(scope=scope)
        if not items_data:
            if not hasattr(self, "_toast"):
                self._toast = Toast(self, "", y_offset=140)
            
            msg = _("No visible categories to manage.") if scope == "category" else _("No visible packages to manage.")
            self._toast.show_message(msg, preset="warning")
            return

        # Get frequent tags
        frequent_tags = []
        if hasattr(self, '_load_frequent_tags'):
            frequent_tags = self._load_frequent_tags()

        # Determine target cache attribute
        dialog_attr = "cat_quick_view_dialog" if scope == "category" else "pkg_quick_view_dialog"
        dialog = getattr(self, dialog_attr, None)

        # Check if cached dialog still exists
        try:
            if dialog and not dialog.isHidden():
                # Already open, just bring to front
                dialog.raise_()
                dialog.activateWindow()
                return
        except RuntimeError:
            # C++ object was deleted, reset reference
            setattr(self, dialog_attr, None)
            dialog = None
            
        # Get current context (view path, not selection path)
        current_context = getattr(self, 'current_view_path', None)

        if dialog:
            # Reuse existing: Reload data
            if hasattr(dialog, 'reload_data'):
                dialog.reload_data(items_data, frequent_tags, context_id=current_context, scope=scope)
            dialog.show()
        else:
            # Create new
            self._open_quick_view_manager_internal(items_data, frequent_tags, mode="cached", context_id=current_context, scope=scope)

    def _open_quick_view_delegate(self, scope="category"):
        """Mode 2: Delegate QuickView (New Class). scope=('category'|'package')"""
        from src.ui.link_master.dialogs.quick_view_delegate import QuickViewDelegateDialog
        from src.core.lang_manager import _
        
        items_data = self._get_quick_view_data(scope=scope)
        if not items_data:
            if not hasattr(self, "_toast"):
                self._toast = Toast(self, "", y_offset=140)
            self._toast.show_message(_("No visible items to manage."), preset="warning")
            return

        # Get frequent tags
        frequent_tags = []
        if hasattr(self, '_load_frequent_tags'):
            frequent_tags = self._load_frequent_tags()
        
        # Phase 1.1.80: Reuse existing delegate dialog to prevent infinite windows
        dialog_attr = f'quick_view_delegate_{scope}'
        existing = getattr(self, dialog_attr, None)
        if existing and not existing.isHidden():
            # Bring existing window to front
            existing.raise_()
            existing.activateWindow()
            return
            
        # Create new Delegate Dialog
        dialog = QuickViewDelegateDialog(
            self, 
            items_data=items_data, 
            frequent_tags=frequent_tags,
            db=self.db, 
            storage_root=self.storage_root,
            show_hidden=getattr(self, 'show_hidden', True),
            scope=scope
        )
        # Modeless
        dialog.finished.connect(lambda: self._on_quick_view_finished(scope))
        dialog.show()
        
        # Keep reference to prevent GC and enable reuse
        setattr(self, dialog_attr, dialog)

    def _open_quick_view_manager(self):
        """Legacy access (if any) - redirects to cached mode."""
        self._open_quick_view_cached()

    def _open_quick_view_manager_internal(self, items_data, frequent_tags, mode="cached", context_id=None, scope="category"):
        """Internal launcher."""
        from src.ui.link_master.dialogs.quick_view_manager import QuickViewManagerDialog
        
        dialog_attr = "cat_quick_view_dialog" if scope == "category" else "pkg_quick_view_dialog"
        
        dialog = QuickViewManagerDialog(
            self, 
            items_data=items_data, 
            frequent_tags=frequent_tags,
            db=self.db, 
            storage_root=self.storage_root,
            show_hidden=getattr(self, 'show_hidden', True),
            scope=scope
        )
        setattr(self, dialog_attr, dialog)
        
        # Phase 1.1.25: Initialize context ID for cache handling
        dialog._last_context_id = context_id
        
        dialog.finished.connect(self._on_quick_view_finished)
        dialog.show()

    def _on_quick_view_finished(self, result_code):
        """Handle QuickView dialog closure/save."""
        dialog = self.sender()
        if not dialog: return
        
        # Determine scope from dialog if possible (Phase Multi-Delegate)
        scope = getattr(dialog, 'scope', 'category')
        
        # Determine if it's one of the cached ones
        is_cached = (hasattr(self, 'cat_quick_view_dialog') and dialog == self.cat_quick_view_dialog) or \
                    (hasattr(self, 'pkg_quick_view_dialog') and dialog == self.pkg_quick_view_dialog)
        
        if is_cached:
            # CACHED MODE: Do NOT clear reference.
            pass
        else:
            # DELEGATE or Dynamic MODE: Clear specific reference
            dialog_attr = f'quick_view_delegate_{scope}'
            if getattr(self, dialog_attr, None) == dialog:
                setattr(self, dialog_attr, None)
            
            # Legacy/Fallback cleanup
            if getattr(self, 'quick_view_delegate_dialog', None) == dialog:
                self.quick_view_delegate_dialog = None

        # Refresh Main Window if changes were made
        # Check if we need to reload ANY item cards.
        # QuickView applies changes to DB directly.
        # We should refresh the view or at least the affected cards.
        # Ideally, we reload all visible cards to reflect tag changes/Fav changes.
        if result_code == QDialog.DialogCode.Accepted:
            # Refresh current view
            # self._refresh_current_view() # Is this method available?
            # Or just trigger a rescan/redraw?
            # For now, let's assume direct object update or DB reload needed.
            if hasattr(self, '_on_refresh_triggered'):
                self._on_refresh_triggered()
        
        if result_code == QDialog.DialogCode.Accepted and dialog.results:
            # Phase 1.1.15: Optimized pinpoint update instead of full re-scan
            # This immediately reflects changes on active cards
            
            # Phase 1.1.27: Handle both list (Mode 1) and dict (Mode 2) results
            results_iter = []
            if isinstance(dialog.results, list):
                results_iter = dialog.results
            elif isinstance(dialog.results, dict):
                # Convert dict {rel_path: changes} to list of changes with rel_path included
                for rel_path, changes in dialog.results.items():
                    if isinstance(changes, dict):
                        c = changes.copy()
                        c['rel_path'] = rel_path
                        results_iter.append(c)

            for changes in results_iter:
                rel_path = changes.get('rel_path')
                if not rel_path or not self.storage_root: continue
                
                full_path = os.path.join(self.storage_root, rel_path)
                card = self._get_active_card_by_path(full_path)
                if card:
                    # Update the card directly with the new data
                    card.update_data(**changes)
                    # Ensure visibility/filters are re-evaluated if tags or name changed
                    self._apply_card_filters()
            
            # Still trigger a background re-scan just to be safe and update other Mixins
            # but use force=False to avoid UI flicker if nothing else changed
            self._refresh_current_view(force=False)
            
            from src.core.lang_manager import _
            # Optional: Show small notification or status log
            self.logger.info(f"QuickView updated {len(dialog.results)} items.")
            
            if not hasattr(self, '_toast'):
                self._toast = Toast(self, "", y_offset=140)  # Below QuickTag bar
            
            msg = _("{count}件 変更しました！").format(count=len(dialog.results))
            self._toast.show_message(msg, preset='success')

    def _make_widget_action(self, menu, widget):
        act = QWidgetAction(menu)
        act.setDefaultWidget(widget)
        return act
    
    def _make_slider_action(self, menu, label, min_v, max_v, value, callback):
        from src.ui.custom_slider import CustomSlider
        slider = CustomSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(value)
        slider.setFixedWidth(110)
        slider.valueChanged.connect(callback)
        
        h = QWidget()
        h_layout = QHBoxLayout(h)
        h_layout.setContentsMargins(10, 0, 5, 0)
        h_layout.addWidget(QLabel(label))
        h_layout.addWidget(slider)
        
        return self._make_widget_action(menu, h)
    
    def _set_card_param(self, type_, param, value):
        """Set card parameter and update cards."""
        attr_name = f"{type_[:3]}_{param}"
        setattr(self, attr_name, value)
        
        layout = self.cat_layout if type_ == 'category' else self.pkg_layout
        if hasattr(self, 'cat_layout' if type_ == 'category' else 'pkg_layout'):
            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if hasattr(widget, 'set_card_params'):
                    widget.set_card_params(
                        card_w=getattr(self, f"{type_[:3]}_card_w", 100) / 100.0,
                        card_h=getattr(self, f"{type_[:3]}_card_h", 100) / 100.0,
                        img_w=getattr(self, f"{type_[:3]}_img_w", 100) / 100.0,
                        img_h=getattr(self, f"{type_[:3]}_img_h", 100) / 100.0
                    )

    
    def _update_image_scale(self, type_, scale):
        """Update image size within cards."""
        if type_ == 'category':
            self.cat_img_scale = scale
            if hasattr(self, 'cat_layout'):
                for i in range(self.cat_layout.count()):
                    widget = self.cat_layout.itemAt(i).widget()
                    if hasattr(widget, 'set_image_scale'):
                        widget.set_image_scale(scale)
        else:
            self.pkg_img_scale = scale
            if hasattr(self, 'pkg_layout'):
                for i in range(self.pkg_layout.count()):
                    widget = self.pkg_layout.itemAt(i).widget()
                    if hasattr(widget, 'set_image_scale'):
                        widget.set_image_scale(scale)

    
    def _update_text_height(self, type_, height):
        """Update text area height for cards."""
        if type_ == 'category':
            self.cat_text_height = height
            if hasattr(self, 'cat_layout'):
                for i in range(self.cat_layout.count()):
                    widget = self.cat_layout.itemAt(i).widget()
                    if hasattr(widget, 'set_text_height'):
                        widget.set_text_height(height)
        else:
            self.pkg_text_height = height
            if hasattr(self, 'pkg_layout'):
                for i in range(self.pkg_layout.count()):
                    widget = self.pkg_layout.itemAt(i).widget()
                    if hasattr(widget, 'set_text_height'):
                        widget.set_text_height(height)



    def resizeEvent(self, event):
        """Handle window resize and update floating panel positions."""
        super().resizeEvent(event)
        if hasattr(self, 'explorer_panel') and self.explorer_panel.isVisible():
            self._update_drawer_geometry()
        if hasattr(self, '_settings_panel') and self._settings_panel.isVisible():
            self._show_settings_menu()  # Re-clamp position
        if hasattr(self, 'options_window') and self.options_window and not self.options_window.isHidden():
            self.options_window.update_size_from_parent()

    def _save_last_state(self):
        """Save current app and folder to global settings."""
        # Phase 28: Skip saving during restore phase to prevent overwriting saved state
        if getattr(self, '_is_restoring', False):
            self.logger.debug("_save_last_state SKIPPED: restore in progress")
            return
            
        self.logger.debug(f"_save_last_state called: view_path={getattr(self, 'current_view_path', None)}, current_path={getattr(self, 'current_path', None)}")
        if not self.registry: return
        try:
            app_data = self.app_combo.currentData()
            if app_data:
                app_id = app_data['id']
                self.logger.debug(f"Saving for app_id={app_id}")
                self.registry.set_setting("last_app_id", str(app_id))
            if app_data:
                app_id = app_data['id']
                self.registry.set_setting("last_app_id", str(app_id))
                
                # Determine if we are at root level
                storage_root = app_data.get('storage_root', '')
                is_at_root = (self.current_view_path == storage_root or 
                              self.current_view_path is None or 
                              self.current_view_path == '')
                
                # Save root flag
                self.registry.set_setting(f"last_is_root_{app_id}", "1" if is_at_root else "0")
                
                # Save view path (even if it's storage_root for root)
                if self.current_view_path:
                    self.registry.set_setting(f"last_path_{app_id}", self.current_view_path)
                elif is_at_root and storage_root:
                    self.registry.set_setting(f"last_path_{app_id}", storage_root)
                    
                if self.current_path:
                    self.registry.set_setting(f"last_subpath_{app_id}", self.current_path)
                else:
                    self.registry.set_setting(f"last_subpath_{app_id}", "")
        except Exception as e:
            self.logger.error(f"Failed to save last state: {e}")

    def _restore_last_state(self):
        """Restore last opened app and folder."""
        self.logger.debug("_restore_last_state called")
        # Phase 28: Set flag to prevent save calls during restore
        self._is_restoring = True
        if not self.registry: 
            self._is_restoring = False
            return
        try:
            last_app_id = self.registry.get_setting("last_app_id")
            self.logger.debug(f"last_app_id={last_app_id}")
            if last_app_id:
                index = -1
                for i in range(self.app_combo.count()):
                    data = self.app_combo.itemData(i)
                    if data and str(data['id']) == last_app_id:
                        index = i
                        break
                if index != -1:
                    self.app_combo.setCurrentIndex(index)
                    app_data = self.app_combo.currentData()
                    storage_root = app_data.get('storage_root', '') if app_data else ''
                    
                    # Check if we were at root
                    is_at_root = self.registry.get_setting(f"last_is_root_{last_app_id}") == "1"
                    self.logger.debug(f"is_at_root={is_at_root}, storage_root={storage_root}")
                    
                    if is_at_root:
                        # Restore to root - load storage_root directly
                        self.logger.debug(f"Restoring to root: {storage_root}")
                        if storage_root and os.path.exists(storage_root):
                            self._load_items_for_path(storage_root)
                            self.current_path = None  # Clear selection
                    else:
                        # Restore to specific folder
                        last_path = self.registry.get_setting(f"last_path_{last_app_id}")
                        last_sub = self.registry.get_setting(f"last_subpath_{last_app_id}")
                        self.logger.debug(f"Restoring to path: last_path={last_path}, last_sub={last_sub}")
                        if last_path and os.path.exists(last_path):
                            self._load_items_for_path(last_path)
                        
                        if last_sub and os.path.exists(last_sub):
                            from PyQt6.QtCore import QTimer
                            QTimer.singleShot(300, lambda: self._on_category_selected(last_sub))
        except Exception as e:
            self.logger.error(f"Failed to restore last state: {e}")
        finally:
            # Phase 28: Clear restore flag after a delay to allow async operations to complete
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._clear_restoring_flag)
    
    def _clear_restoring_flag(self):
        """Clear the restoring flag after restore completes."""
        self._is_restoring = False
        self.logger.debug("_is_restoring flag cleared")
    
    def _open_target_folder(self):
        app_data = self.app_combo.currentData()
        if not app_data: return
        # Default to primary target_root
        target_root = app_data.get("target_root")
        if target_root and os.path.isdir(target_root):
            os.startfile(target_root)
        else:
            QMessageBox.warning(self, "Error", f"Invalid target folder: {target_root}")

    def _load_apps(self):
        apps = self.registry.get_apps()
        # Sort: Favorites first by score desc, then others by name
        favs = sorted([a for a in apps if a.get('is_favorite')], key=lambda x: x.get('score', 0), reverse=True)
        others = sorted([a for a in apps if not a.get('is_favorite')], key=lambda x: x.get('name', ''))
        sorted_apps = favs + others
        
        self.app_combo.clear()
        self.app_combo.addItem("Select App...", None)
        for app in sorted_apps:
            display_name = f"★ {app['name']}" if app.get('is_favorite') else app['name']
            self.app_combo.addItem(display_name, app)
            
        # Update quick switcher buttons in title bar
        self._update_favorite_quick_switcher(favs)
            
        # Restore last opened state
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._restore_last_state)

    def _update_favorite_quick_switcher(self, fav_apps):
        """Update the quick switch buttons immediately after the title!"""
        # Clear existing in fav_switcher_layout
        while self.fav_switcher_layout.count() > 0:
            item = self.fav_switcher_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        from src.ui.title_bar_button import TitleBarButton
        from PyQt6.QtGui import QIcon, QPixmap
        import os

        for app in fav_apps:
            app_id = app.get('id')
            app_name = app.get('name', '?')
            initials = app_name[0].upper() if app_name else '?'
            is_active = (self.current_app_id == app_id)
            
            btn = TitleBarButton(initials, is_toggle=True)
            btn.setToolTip(app_name)
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(btn.styleSheet() + f"QPushButton {{ font-size: 13px; border-radius: 16px; border: 1px solid #444; }}")
            
            cover_img = app.get('cover_image')
            if cover_img and os.path.exists(cover_img):
                pixmap = QPixmap(cover_img)
                if not pixmap.isNull():
                    scaled_pix = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    btn.setIconSize(QSize(24, 24)) # Ensure icon size is set
                    if not is_active:
                        scaled_pix = self._create_grayscale_icon(scaled_pix)
                    btn.setIcon(QIcon(scaled_pix))
                    btn.setText("")
                    # If image exists, avoid blue background even if active to make icon prominent
                    btn.set_colors(active="transparent")

            app_id = app.get('id')
            btn.clicked.connect(lambda _, aid=app_id: self._switch_to_app_by_id(aid))
            
            if is_active:
                btn._force_state(True)

            self.fav_switcher_layout.addWidget(btn)

    def _create_grayscale_icon(self, pixmap):
        """Helper to create a desaturated version of an icon."""
        from PyQt6.QtGui import QImage, QColor, QPixmap
        img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.alpha() > 0:
                    gray = int(c.red() * 0.299 + c.green() * 0.587 + c.blue() * 0.114)
                    img.setPixelColor(x, y, QColor(gray, gray, gray, int(c.alpha() * 0.6)))
        return QPixmap.fromImage(img)

    def _switch_to_app_by_id(self, app_id):
        """Find the app in combo box and switch to it."""
        for i in range(self.app_combo.count()):
            data = self.app_combo.itemData(i)
            if data and data.get('id') == app_id:
                if self.app_combo.currentIndex() != i:
                    self.app_combo.setCurrentIndex(i)
                break

    # --- Drag & Drop ---
    # Import/drop methods moved to LMImportMixin

    def _on_app_changed(self, index):
        app_data = self.app_combo.currentData()
        
        if app_data:
            self.current_app_id = app_data.get('id')
            # Switch to App-Specific Database
            self.db = get_lm_db(app_data['name'])
            if self.options_window:
                self.options_window.db = self.db # Update sub-window reference
            self.cat_scanner_worker.set_db(self.db)  # Phase 18.13/19.x
            self.pkg_scanner_worker.set_db(self.db)
            
            if getattr(self, 'presets_panel', None):
                self.presets_panel.set_db(self.db)  # Must be called before set_app
                self.presets_panel.set_app(self.current_app_id)
            
            if getattr(self, 'library_panel', None):
                self.library_panel.set_app(self.current_app_id, self.db)

            # Refresh notes and presets
            self._update_notes_path()
            if self.sidebar_tabs.currentIndex() == 1 and self.drawer_widget.isVisible() and self.notes_panel:
                self.notes_panel.refresh()

            self._refresh_tag_visuals()

            # Sync Target Buttons
            self.btn_target_a.setChecked(self.current_target_key == "target_root")
            self.btn_target_b.setChecked(self.current_target_key == "target_root_2")
            self.btn_target_c.setChecked(self.current_target_key == "target_root_3")
            
            # Update target name label
            target_path = app_data.get(self.current_target_key, "")
            self.target_name_lbl.setText(os.path.basename(target_path) if target_path else _("Not Set"))
            self.target_name_lbl.setToolTip(target_path)

            self._refresh_current_view()
            
            # Display cover image next to app name and in header
            cover_img = app_data.get('cover_image')
            if cover_img and os.path.exists(cover_img):
                from PyQt6.QtGui import QPixmap, QIcon
                pixmap = QPixmap(cover_img)
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(24, 24))
                    self.app_combo.setItemIcon(index, icon)
            
            # Enable/Disable Buttons
            self.edit_app_btn.setEnabled(True)
            self.btn_drawer.setEnabled(True)

            # Re-test symlink capability for the new target folder
            target_dir = app_data.get('target_root')
            self._update_deploy_mode_indicator(target_dir)

            
            root_path = app_data.get('storage_root')
            if root_path and os.path.isdir(root_path):
                self.storage_root = root_path
                # Update Explorer Scope (with app_name for DB sync - Phase 18.13)
                self.explorer_panel.set_storage_root(root_path, app_id=app_data['id'], app_name=app_data['name'])
                try:
                    self.explorer_panel.config_changed.disconnect()
                except: pass
                self.explorer_panel.config_changed.connect(lambda: self._refresh_current_view())
                
                # Defer Auto-registration (L1/L2) to background to speed up app switching (Save ~0.7s)
                QTimer.singleShot(800, lambda: self._auto_register_folders(root_path))
                
                self._load_items_for_path(root_path)

            else:
                self.logger.warning(f"Invalid storage root: {root_path}")
            
            # Phase 28: REMOVED save here - save only on close and explicit navigation
            # Saving here was overwriting the restored path before navigation completed

            
            # Load Tags
            self._load_tags_for_app()
            
            # Update Executable Links (Phase 28)
            self._update_exe_links(app_data)

            # Update Favorite Quick Switcher Button States
            for i in range(self.title_bar_center_layout.count()):
                w = self.title_bar_center_layout.itemAt(i).widget()
                if w:
                    # We need to know which app this button belongs to
                    # Let's store app_id in the button's property or name
                    # For now, we'll re-check by tooltip or just re-run update if count is small
                    # But better to just update state if we can.
                    pass
            
            # Simpler: Just refresh all buttons to ensure correct active state
            apps = self.registry.get_apps()
            favs = sorted([a for a in apps if a.get('is_favorite')], key=lambda x: x.get('score', 0), reverse=True)
            self._update_favorite_quick_switcher(favs)
            
            # AND restore the EXE links to the center layout
            self._update_exe_links(app_data)
        else:
            self.current_app_id = None
            if getattr(self, 'presets_panel', None): self.presets_panel.set_app(None)
            if getattr(self, 'library_panel', None): self.library_panel.set_app(None, None)
            if getattr(self, 'explorer_panel', None): self.explorer_panel.set_storage_root(None)
            
            self.edit_app_btn.setEnabled(False)
            self.btn_drawer.setEnabled(False)

            self.tag_bar.set_tags([])

    # --- Size Scanning (Phase 30) ---
    def _start_bulk_size_check(self):
        if not self.storage_root:
            return
            
        if self.tools_panel:
            self.tools_panel.btn_check_sizes.setEnabled(False)
            self.tools_panel.btn_check_sizes.setText("📦 走査中...")
        
        self.size_worker = SizeScannerWorker(self.db, self.storage_root)
        self.size_worker.progress.connect(self._on_size_scan_progress)
        self.size_worker.all_finished.connect(self._on_size_scan_finished)
        self.size_worker.start()

    def _on_size_scan_progress(self, current, total):
        if self.tools_panel:
            self.tools_panel.btn_check_sizes.setText(f"📦 走査中 ({current}/{total})")
    def _on_size_scan_finished(self):
        if self.tools_panel:
            self.tools_panel.btn_check_sizes.setEnabled(True)
            self.tools_panel.btn_check_sizes.setText("全容量チェックを実行")
            
            # Phase 30: Update last check time label
            import datetime
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.tools_panel.set_last_check_time(now_str)
        
        self._refresh_current_view()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "完了", "全てのパッケージ容量チェックが完了しました。")

    def _auto_register_folders(self, storage_root):
        """Auto-register folders to ensure they exist in DB, but let dynamic logic handle types."""
        try:
            self.logger.info(f"Auto-registering folders using DB: {self.db.db_path}")
            registered_count = 0
            for name in os.listdir(storage_root):
                path = os.path.join(storage_root, name)
                if not os.path.isdir(path): continue
                
                rel = name  # Level 1
                # Standardize separators for rel path
                rel = rel.replace('\\', '/')
                
                # Check if exists, if not, create entry with folder_type='category'
                # Level 1 and Level 2 are Categories, Level 3+ are Packages
                if not self.db.get_folder_config(rel):
                    self.db.update_folder_display_config(rel, folder_type='category')
                    registered_count += 1
                    self.logger.debug(f"Registered L1: {rel}")
                
                # Level 2 - also category
                try:
                    for sub in os.listdir(path):
                        sub_path = os.path.join(path, sub)
                        if not os.path.isdir(sub_path): continue
                        sub_rel = (rel + "/" + sub).replace('\\', '/')
                        if not self.db.get_folder_config(sub_rel):
                            self.db.update_folder_display_config(sub_rel, folder_type='category')
                            registered_count += 1
                            self.logger.debug(f"Registered L2: {sub_rel}")
                except: pass
            self.logger.info(f"Auto-registration complete. New entries: {registered_count}")
        except Exception as e:
            self.logger.warning(f"Auto-register failed: {e}")

    def _detect_folder_type(self, path):
        """Phase 18.11: Heuristic to detect if a folder is a CATEGORY or a PACKAGE."""
        if not os.path.exists(path) or not os.path.isdir(path):
            return 'category'

        # 1. Manifest Check
        manifests = ["manifest.json", "plugin.json", "config.yml", "__init__.py", "package.json"]
        for m in manifests:
            if os.path.exists(os.path.join(path, m)):
                return 'package'

        # 2. Naming Convention
        pkg_exts = (".pkg", ".bundle", ".plugin", ".addon")
        if path.lower().endswith(pkg_exts):
            return 'package'

        # 3. Content Density (Heuristic)
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_file():
                        # If it contains any files at the top level, it's likely a package
                        return 'package'
        except:
            pass

        return 'category'

    # Tag methods moved to LMTagsMixin


    def _open_external_note(self, path):
        """Open the given note path in the default system editor."""
        if not path or not os.path.exists(path): return
        try:
            os.startfile(path)
        except Exception as e:
            self.logger.error(f"Failed to open external note: {e}")

    def _on_request_focus_library(self, lib_name):
        """Handler for 'Jump to Library' jump from ItemCard.
        
        Switches to Library tab and tells the panel to focus the item.
        """
        if not lib_name: return
        
        # 1. Switch sidebar to Library tab (index 0)
        # _toggle_sidebar_tab handles opening drawer if closed
        self._toggle_sidebar_tab(0)
        
        # 2. Focus the library
        if hasattr(self, 'library_panel') and self.library_panel:
            self.library_panel.focus_library(lib_name)

    def _toggle_sidebar_tab(self, index):
        """Toggle the shared sidebar drawer and switch to the specified tab (0=Library, 1=Presets, 2=Notes, 3=Tools)."""
        is_already_open = self.drawer_widget.isVisible()
        current_tab = self.sidebar_tabs.currentIndex()
        
        # Lazy Loading implementation
        if index == 0 and self.library_panel is None:
            self.library_panel = LibraryPanel(self, db=self.db)
            self.library_panel.request_register_library.connect(self._register_selected_as_library)
            self.library_panel.request_deploy_library.connect(self._deploy_single_from_rel_path)
            self.library_panel.request_unlink_library.connect(self._unlink_single_from_rel_path)
            self.library_panel.request_edit_properties.connect(self._open_properties_from_rel_path)
            self.library_panel.request_view_properties.connect(self._view_properties_from_rel_path)
            # Replace placeholder
            old = self.sidebar_tabs.widget(0)
            self.sidebar_tabs.removeTab(0)
            self.sidebar_tabs.insertTab(0, self.library_panel, _("Packages"))
            if old: old.deleteLater()
            
            # Initial state setup for new panel
            app_data = self.app_combo.currentData()
            if app_data:
                self.library_panel.set_app(self.current_app_id, self.db)

        elif index == 1 and self.presets_panel is None:
            self.presets_panel = PresetsPanel(self, db=self.db)
            self.presets_panel.load_preset.connect(self._load_preset)
            self.presets_panel.preview_preset.connect(self._preview_preset)
            self.presets_panel.delete_preset.connect(self._delete_preset)
            self.presets_panel.create_preset.connect(self._create_preset)
            self.presets_panel.clear_filter.connect(self._clear_preset_filter)
            self.presets_panel.unload_request_signal.connect(self._unload_active_links)
            self.presets_panel.order_changed.connect(self._on_preset_order_changed)
            self.presets_panel.edit_preset_properties.connect(self._show_preset_properties)
            # Replace placeholder
            old = self.sidebar_tabs.widget(1)
            self.sidebar_tabs.removeTab(1)
            self.sidebar_tabs.insertTab(1, self.presets_panel, "Presets")
            if old: old.deleteLater()
            
            if self.current_app_id:
                self.presets_panel.set_app(self.current_app_id)

        elif index == 2 and self.notes_panel is None:
            self.notes_panel = NotesPanel(self)
            self.notes_panel.request_external_edit.connect(self._open_external_note)
            # Replace placeholder
            old = self.sidebar_tabs.widget(2)
            self.sidebar_tabs.removeTab(2)
            self.sidebar_tabs.insertTab(2, self.notes_panel, "Notes")
            if old: old.deleteLater()
            
            self._update_notes_path()

        elif index == 3 and self.tools_panel is None:
            from src.ui.link_master.tools_panel import ToolsPanel
            self.tools_panel = ToolsPanel(self)
            self.tools_panel.request_reset_all.connect(self._reset_all_folder_attributes)
            self.tools_panel.request_manual_rebuild.connect(self._manual_rebuild)
            self.tools_panel.pool_size_changed.connect(self._set_pool_size)
            self.tools_panel.search_cache_toggled.connect(self._set_search_cache_enabled)
            self.tools_panel.request_import.connect(self._import_portability_package)
            self.tools_panel.request_export.connect(self._export_hierarchy_current)
            self.tools_panel.request_size_check.connect(self._start_bulk_size_check)
            self.tools_panel.deploy_opacity_changed.connect(self._set_deploy_button_opacity)
            # Replace placeholder
            old = self.sidebar_tabs.widget(3)
            self.sidebar_tabs.removeTab(3)
            self.sidebar_tabs.insertTab(3, self.tools_panel, "Tools")
            if old: old.deleteLater()
            
            # Initialize Tool values
            if hasattr(self, 'registry') and self.registry:
                try:
                    saved_pool_size = self.registry.get_setting('pool_size')
                    if saved_pool_size: self.max_pool_size = int(saved_pool_size)
                except: pass
            if hasattr(self, 'max_pool_size'):
                self.tools_panel.spin_pool_size.setValue(self.max_pool_size)
            if hasattr(self, 'search_cache_enabled'):
                self.tools_panel.chk_search_cache.setChecked(self.search_cache_enabled)
            if hasattr(self, 'deploy_button_opacity'):
                 self.tools_panel.slider_deploy_opacity.setValue(int(self.deploy_button_opacity * 100))

        if is_already_open and current_tab == index:
            # Cache splitter sizes before closing
            if hasattr(self, 'sidebar_splitter'):
                self._last_splitter_sizes = self.sidebar_splitter.sizes()
            # Close it
            self.drawer_widget.hide()
            self.btn_libraries.setChecked(False)
            self.btn_presets.setChecked(False)
            self.btn_notes.setChecked(False)
            self.btn_tools.setChecked(False)
        else:
            # Open it / Switch to it
            self.sidebar_tabs.setCurrentIndex(index)
            self.drawer_widget.show()
            
            # Restore saved splitter sizes if available
            if hasattr(self, '_pending_splitter_sizes') and self._pending_splitter_sizes:
                self.sidebar_splitter.setSizes(self._pending_splitter_sizes)
                self._pending_splitter_sizes = None  # Clear after first use
            
            self.btn_libraries.setChecked(index == 0)
            self.btn_presets.setChecked(index == 1)
            self.btn_notes.setChecked(index == 2)
            self.btn_tools.setChecked(index == 3)
            
            # Refresh content
            if index == 0:
                self.library_panel.refresh()
            elif index == 1:
                self.presets_panel.refresh()
            elif index == 2:
                self._update_notes_path()
                self.notes_panel.refresh()
            # index 2 (Tools) is static content, no refresh needed

    def _register_selected_as_library(self):
        """Registers all currently selected items as libraries (requires metadata)."""
        if not self.selected_paths:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Library", "Please select one or more items to register.")
            return
        
        # Create registration dialog with existing library dropdown
        from src.ui.link_master.dialogs_legacy import LibraryRegistrationDialog
        dialog = LibraryRegistrationDialog(self, self.db)
        if not dialog.exec():
            return
        
        name = dialog.get_library_name()
        version = dialog.get_version()
        
        if not name:
            return
        
        count = 0
        for path in self.selected_paths:
            try:
                rel_path = os.path.relpath(path, self.storage_root).replace('\\', '/')
                if rel_path == ".": rel_path = ""
                self.db.update_folder_display_config(rel_path, is_library=1, lib_name=name, lib_version=version)
                count += 1
            except: pass
            
        if self.library_panel:
            self.library_panel.refresh()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Library", f"Registered {count} item(s) to library: {name}")


    def _update_notes_path(self):
        """Set the storage path for the notes panel based on the current app."""
        if not self.current_app_id: return
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        # Determine app folder name
        app_name = app_data.get('name', 'Unknown')
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # Notes are in the root resource/app/ dir
        notes_path = os.path.join(project_root, "resource", "app", app_name, "notes")
        if self.notes_panel:
            self.notes_panel.set_app(self.current_app_id, notes_path)




    def _toggle_presets_drawer(self, checked):
        """Toggle the Presets side drawer."""
        if checked:
            self.presets_drawer.show()
        else:
            self.presets_drawer.hide()
    

    def _update_drawer_geometry(self,):
        """Update absolute position of the floating explorer panel."""
        if not hasattr(self, 'explorer_panel') or not hasattr(self, 'content_wrapper'):
            return
        # Position at the left edge of content_wrapper, below the header
        pos = self.content_wrapper.mapTo(self, self.content_wrapper.rect().topLeft())
        height = self.content_wrapper.height()
        # Use saved width or default to 280
        width = getattr(self, '_explorer_panel_width', 280)
        self.explorer_panel.setGeometry(pos.x() + 20, pos.y(), width, height)
        self.explorer_panel.raise_()
    
    def _on_explorer_panel_width_changed(self, new_width: int):
        """Cache explorer panel width for persistence."""
        self._explorer_panel_width = new_width
        self.logger.info(f"[ExplorerPanel] Width changed to: {new_width}")
    
    def _toggle_explorer(self, checked):
        """Toggle the floating Explorer panel."""
        if checked:
            self.explorer_panel.show()
            self._update_drawer_geometry()
        else:
            self.explorer_panel.hide()



    def _on_explorer_path_selected(self, rel_path):
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        storage_root = app_data.get('storage_root')
        full_path = os.path.join(storage_root, rel_path.replace('/', os.sep))
        
        self._load_items_for_path(full_path)

    def _refresh_current_view(self, force=True):
        """Reloads the currently visible folder items (Maintains state).
        
        Phase 28 Architecture: Avoids widget destruction during refresh.
        - force=False: Visual-only updates (size, mode)
        - force=True: Re-check link status and hidden state on existing cards
                      + Update visual attributes from DB (Display Name, Icon, etc.)
        
        For data changes (new items added/removed), use _load_items_for_path directly.
        """
        # print(f"[Profiling] LinkMasterWindow._refresh_current_view (force={force}): view={getattr(self, 'current_view_path', 'None')}, sel={getattr(self, 'current_path', 'None')}")
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        app_deploy_default = app_data.get('deployment_type', 'folder')
        app_conflict_default = app_data.get('conflict_policy', 'backup')
        app_name = app_data.get('name')

        # Phase 18.15 & 24: Immediate visual feedback for display mode/size changes
        # Always refresh existing widgets for immediate feedback even if not forcing a data re-scan.
        for prefix, layout in [('cat', self.cat_layout), ('pkg', self.pkg_layout)]:
            if not hasattr(self, f'{prefix}_layout'): continue
            override = getattr(self, f'{prefix}_display_override', None)
            
            # Use stored persistent mode if no override, to avoid jumps
            stored_mode = getattr(self, f'current_{prefix}_display_mode', 'mini_image')
            active_mode = override if override is not None else stored_mode
            
            # Fetch scale/params
            scale = getattr(self, f'{prefix}_{active_mode}_scale', 1.0)
            base_w = getattr(self, f'{prefix}_{active_mode}_card_w', 160)
            base_h = getattr(self, f'{prefix}_{active_mode}_card_h', 220)
            base_img_w = getattr(self, f'{prefix}_{active_mode}_img_w', 140)
            base_img_h = getattr(self, f'{prefix}_{active_mode}_img_h', 140)

            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if isinstance(widget, ItemCard):
                    # Only change display mode if there's an explicit override
                    if override is not None:
                        widget.set_display_mode(override)
                    # Always update size params for consistency
                    widget.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)

        # Phase 24 Optimization: If not forcing, we are done with visual-only updates
        if not force:
            return

        # If we are in a search/filter view, re-run search/scan (this does need rebuild)
        has_search = bool(self.search_bar.text().strip() or self.tag_bar.get_selected_tags())
        has_link_filter = bool(getattr(self, 'link_filter_mode', None))
        
        if has_search:
             # print("[Profiling] Triggering Search Refresh")
             self._perform_search()
             return
             
        # Trigger rebuild if link filter is active OR if we just turned it off
        # (Since we don't track'prev_filter_state', always rebuild if force=True
        # and current view path is set, as it's the safest way to restore all cards)
        if hasattr(self, 'current_view_path') and self.current_view_path:
             # print(f"[Profiling] Triggering Full Rebuild (force=True) for {self.current_view_path}")
             self._load_items_for_path(self.current_view_path, force=True)
             return

        # Phase 28: Lightweight refresh - update attributes on existing cards, NO rebuild
        # This updates link status (green/orange borders) and hidden state
        # --- ENHANCED: Also update Display Name/Icon from DB ---
        # print("[Profiling] Phase 28: Lightweight refresh (no rebuild) with metadata sync")
        
        # Fetch latest DB configs for merging
        all_configs = self.db.get_all_folder_configs()
        folder_configs = {k.replace('\\', '/'): v for k, v in all_configs.items()}

        for prefix, layout in [('cat', self.cat_layout), ('pkg', self.pkg_layout)]:
            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if isinstance(widget, ItemCard) and hasattr(widget, 'path'):
                    try:
                        rel_path = os.path.relpath(widget.path, storage_root).replace('\\', '/')
                        cfg = folder_configs.get(rel_path, {})
                        
                        # Map image path (Priority: DB > Auto-scan thumb)
                        img_path = None
                        cfg_img = cfg.get('image_path')
                        if cfg_img:
                            if os.path.isabs(cfg_img):
                                img_path = cfg_img
                            else:
                                img_path = os.path.join(storage_root, cfg_img)
                        else:
                            # Phase 28: Fallback to automatic thumbnail detection if not in DB
                            auto_thumb = self.scanner.detect_thumbnail(widget.path)
                            if auto_thumb:
                                img_path = os.path.join(widget.path, auto_thumb)
                        
                        # Phase 28: Proper empty string handling for display_name
                        raw_name = cfg.get('display_name')
                        final_name = raw_name if raw_name else os.path.basename(widget.path)
                        
                        widget.update_data(
                            name=final_name,
                            image_path=img_path,
                            is_registered=(rel_path in folder_configs),
                            target_override=cfg.get('target_override'),
                            deployment_rules=cfg.get('deployment_rules'),
                            manual_preview_path=cfg.get('manual_preview_path'),
                            is_hidden=(cfg.get('is_visible', 1) == 0),
                            deploy_type=cfg.get('deploy_type') or app_deploy_default,
                            conflict_policy=cfg.get('conflict_policy') or app_conflict_default,
                            storage_root=storage_root,
                            db=self.db,
                            app_name=app_name,
                            thumbnail_manager=self.thumbnail_manager
                        )
                    except Exception as e:
                        # print(f"[Profiling] Metadata sync failed for {getattr(widget, 'path', '???')}: {e}")
                        pass

        self._refresh_category_cards()  # Updates category borders + package borders
    
    def _rebuild_current_view(self):
        """Force full widget reconstruction. Use only when items are added/removed/moved.
        
        Phase 28: This is the ONLY method that triggers widget destruction.
        Use _refresh_current_view for attribute updates (link status, visibility, etc.)
        """
        # print("[Profiling] _rebuild_current_view: Full reconstruction required")
        
        # If we are in a search/filter view, re-run search
        if self.search_bar.text().strip() or self.tag_bar.get_selected_tags():
             self._perform_search()
             return

        # Full reload with widget destruction
        if hasattr(self, 'current_view_path') and self.current_view_path:
             self._load_items_for_path(self.current_view_path, force=True)

        if hasattr(self, 'current_path') and self.current_path:
             self._load_package_contents(self.current_path)

    def keyPressEvent(self, event):
        """Phase 19.5: Support Space key deployment for selected items."""
        if event.key() == Qt.Key.Key_Space:
            if self.selected_paths:
                self.logger.info(f"Space key pressed: Toggling deployment for {len(self.selected_paths)} items")
                # Find corresponding cards and toggle
                found_any = False
                for layout_obj in [self.cat_layout, self.pkg_layout]:
                    for i in range(layout_obj.count()):
                        w = layout_obj.itemAt(i).widget()
                        if isinstance(w, ItemCard) and w.path in self.selected_paths:
                            if hasattr(w, 'toggle_deployment'):
                                w.toggle_deployment()
                                found_any = True
                if found_any:
                    # Final refresh after all toggles
                    self._refresh_current_view()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Phase 28: Navigation History (Mouse Side Buttons)"""
        # Mouse Button 4 (XButton1) is Back
        if event.button() == Qt.MouseButton.XButton1:
            self._navigate_back()
            return
        # Mouse Button 5 (XButton2) is Forward
        elif event.button() == Qt.MouseButton.XButton2:
            self._navigate_forward()
            return

        super().mousePressEvent(event)

    def _load_items_for_path(self, path, force=False):
        # Phase 19.x Optimization: Skip redundant scans if already at the path (e.g., clicking Home/Breadcrumb)
        # unless force=True (used by _refresh_current_view)
        # Phase 28: Normalize paths for reliable comparison
        current_normalized = os.path.normpath(getattr(self, 'current_view_path', '') or '').replace('\\', '/')
        path_normalized = os.path.normpath(path or '').replace('\\', '/')
        is_same_path = current_normalized == path_normalized
        
        # Prevent duplicate async scans from rapid clicks (applies to ALL paths, not just same path)
        # Phase 33 FIX: Do NOT block scan requests. Cancelling previous is better, or just letting it complete and be ignored.
        # if getattr(self, '_scan_in_progress', False):
        #    self.logger.info(f"Ignoring scan request for: {path} (scan already in progress)")
        #    return
        
        # Only skip if same path AND not forced - but still update breadcrumbs
        if not force and is_same_path:
            self.logger.info(f"Skipping redundant scan for: {path}")
            # Just refresh breadcrumbs, don't clear or do a scan
            self._update_breadcrumbs(path)
            return

        # Normal navigation or forced refresh
        if not is_same_path:
            self.current_path = None  
            if hasattr(self, 'selected_paths'):
                self.selected_paths.clear()
            
            # Phase 28: Navigation History Recording
            # Avoid recording if we are navigating history itself
            if not getattr(self, '_is_navigating_history', False):
                if self.nav_index < len(self.nav_history) - 1:
                    # Branching: If we were back in time and navigated to a NEW place, 
                    # prune all forward history.
                    self.nav_history = self.nav_history[:self.nav_index + 1]
                
                # Append only if it's a new unique step
                if not self.nav_history or self.nav_history[-1] != path:
                    self.nav_history.append(path)
                
                self.nav_index = len(self.nav_history) - 1
                self._update_nav_buttons()
        
        self._nav_start_t = time.time()
        
        self.current_view_path = path
        # Phase 28: REMOVED automatic override reset on navigation
        # Overrides now persist until user explicitly changes them via buttons
        # Old behavior: reset on every navigation (is_same_path=False)
        
        # Phase 28: Save last state on every navigation for startup restoration
        self._save_last_state()
        
        self._update_breadcrumbs(path)
        
        # Phase 28: Use pooling instead of destruction
        self._release_all_active_cards("all")
        
        # Trigger Asynchronous Scan
        self._show_search_indicator()
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data['storage_root']
        target_root = app_data.get(self.current_target_key)
        
        self.cat_scanner_worker.set_params(path, target_root, storage_root, context="view", 
                                           app_data=app_data, target_key=self.current_target_key, app_id=app_data.get('id'))
        self._scan_in_progress = True  # Prevent duplicate scans from rapid clicks
        from PyQt6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self.cat_scanner_worker, "run", Qt.ConnectionType.QueuedConnection)

    def _on_category_selected(self, path, force=False):
        """Called when a category card is clicked. Loads its contents into the bottom area asynchronously."""
        # Phase 28: Skip if already showing this category's contents (unless forced)
        if not force and getattr(self, 'current_path', None) == path:
            print(f"[Debug] Skipping redundant category selection: {path}")
            return
            
        self._nav_start_t = time.time()
            
        # Update Breadcrumbs to show the selected package as a leaf
        if hasattr(self, 'current_view_path'):
             self._update_breadcrumbs(self.current_view_path, active_selection=path)
        
        # Load contents into bottom area (Async)
        self._load_package_contents(path)
        for i in range(self.cat_layout.count()):
            widget = self.cat_layout.itemAt(i).widget()
            if isinstance(widget, ItemCard):
                widget.set_selected(widget.path == path)
        
        # Phase 19: Unified Focus tree on selected folder
        app_data = self.app_combo.currentData()
        if app_data:
            storage_root = app_data.get('storage_root')
            try:
                rel_path = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel_path == ".": rel_path = ""
                self.explorer_panel.focus_on_path(rel_path)
            except:
                pass


    # --- Target Switching ---
    
    def _switch_target(self, target_idx):
        """Switch current target root (0=A, 1=B, 2=C)."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        keys = ["target_root", "target_root_2", "target_root_3"]
        self.current_target_key = keys[target_idx]
        
        # Update Button States
        self.btn_target_a.setChecked(target_idx == 0)
        self.btn_target_b.setChecked(target_idx == 1)
        self.btn_target_c.setChecked(target_idx == 2)
        
        # Update target name label
        target_path = app_data.get(self.current_target_key, "")
        self.target_name_lbl.setText(os.path.basename(target_path) if target_path else _("Not Set"))
        self.target_name_lbl.setToolTip(target_path)
        
        # Re-test symlink capability for the new target
        self._update_deploy_mode_indicator(target_path)
        
        # Record last target in DB
        self.db.update_app(app_data['id'], {'last_target': self.current_target_key})
        app_data['last_target'] = self.current_target_key # Update cache
        
        self.logger.info(f"Switched to Target {chr(65+target_idx)}: {target_path}")
        
        # Refresh visuals
        self._refresh_current_view()
        self._refresh_tag_visuals()

    def _load_package_contents(self, path):
        self.current_path = path
        # Phase 28: Save last state on every category selection for startup restoration
        self._save_last_state()
        # Phase 28: Use pooling instead of destruction
        self._release_all_active_cards("contents")
        
        # Phase 19.x: Also update breadcrumbs leaf highlight
        if hasattr(self, 'current_view_path'):
            self._update_breadcrumbs(self.current_view_path, active_selection=path)

        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data['storage_root']
        target_root = app_data.get(self.current_target_key)
        
        # Async Scan for packages only
        self.pkg_scanner_worker.set_params(path, target_root, storage_root, context="contents",
                                           app_data=app_data, target_key=self.current_target_key)
        from PyQt6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self.pkg_scanner_worker, "run", Qt.ConnectionType.QueuedConnection)

    def _is_package_auto(self, abs_path):
        """Heuristic: Check if folder contains package-like config files."""
        if not abs_path or not os.path.isdir(abs_path):
            return False
            
        package_indicators = {'.json', '.ini', '.yaml', '.toml', '.yml'}
        try:
            with os.scandir(abs_path) as it:
                for entry in it:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in package_indicators:
                            return True
        except:
            pass
        return False

    def _handle_tree_navigation(self, rel_path, is_double_click=False):
        """Unified TreeView navigation handler.
        Supports Auto-Package detection and Contextual Backtracking for categories.
        """
        if not self.storage_root:
            return
            
        # 1. Root handling
        if not rel_path:
            if is_double_click: 
                self._load_items_for_path(self.storage_root)
            else:
                self.current_path = None
                self._load_items_for_path(self.storage_root)
            return

        # 2. Folder Type Detection (Priority: DB > Auto-Heuristic)
        abs_path = os.path.join(self.storage_root, rel_path)
        config = self.db.get_folder_config(rel_path) or {}
        
        # Determine Folder Type
        config_type = config.get('folder_type', 'auto')
        if config_type == 'auto':
            folder_type = 'package' if self._is_package_auto(abs_path) else 'category'
        else:
            folder_type = config_type
        
        if folder_type == 'package':
            # Multi-level focus: View Grandparent, Select Parent, Highlight self
            parent_abs = os.path.dirname(abs_path)
            grandparent_abs = os.path.dirname(parent_abs)
            
            # 1. Top context (View Root)
            if getattr(self, 'current_view_path', None) != grandparent_abs:
                self._load_items_for_path(grandparent_abs)
            
            # 2. Mid context (Selected Category)
            if getattr(self, 'current_path', None) != parent_abs:
                self._on_category_selected(parent_abs)
            
            # 3. Bottom context (Highlighted Package)
            self.selected_paths = {abs_path}
            self._update_selection_visuals()
            
        else:
            # Category behavior
            if is_double_click:
                self._load_items_for_path(abs_path)
            else:
                # Requirement: Use Contextual Backtracking like Breadcrumbs
                # If we are ALREADY in the folder, or deep inside, click in tree should trace back
                parent_abs = os.path.dirname(abs_path)
                
                # 1. Top view (Navigator) to parent level
                self._load_items_for_path(parent_abs)
                
                # 2. Select the clicked segment in that view
                self._on_category_selected(abs_path)


    # Scan result methods moved to LMScanHandlerMixin

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    # --- Selection & Batch Methods moved to: lm_selection.py, lm_batch_ops.py ---



    def _delete_preset(self, preset_id):
        try:
            self.db.delete_preset(preset_id)
            if self.presets_panel:
                self.presets_panel.refresh()
            # Clear highlights if the deleted preset was active
            self._clear_item_highlights()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_preset_order_changed(self, order_list):
        """Persist new preset order to DB."""
        if not self.db: return
        try:
            self.db.update_preset_order(order_list)
        except Exception as e:
            self.logger.error(f"Failed to update preset order: {e}")

    def _show_preset_properties(self, preset_id):
        """Show dialog to edit preset name and description."""
        presets = self.db.get_presets()
        preset = next((p for p in presets if p['id'] == preset_id), None)
        if not preset: return
        
        from src.ui.link_master.dialogs import PresetPropertiesDialog
        dialog = PresetPropertiesDialog(self, name=preset['name'], description=preset.get('description', ''))
        if dialog.exec():
            data = dialog.get_data()
            try:
                self.db.update_preset(preset_id, **data)
                if self.presets_panel:
                    self.presets_panel.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _open_register_dialog(self):
        from src.ui.link_master.dialogs import AppRegistrationDialog
        dialog = AppRegistrationDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['name'] or not data['storage_root']:
                QMessageBox.warning(self, "Error", "Name and Storage Root are required.")
                return
            
            try:
                # Add to Registry
                new_id = self.registry.add_app(data)
                self._load_apps()
                
                # Auto-select
                for i in range(self.app_combo.count()):
                    item = self.app_combo.itemData(i)
                    if item and item.get('id') == new_id:
                        self.app_combo.setCurrentIndex(i)
                        break
                
                QMessageBox.information(self, "Success", f"Registered {data['name']}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def toggle_pin_click(self):
        """Toggle always-on-top using flicker-free Win32 implementation and persist state."""
        try:
            is_pinned = self.pin_btn.toggle()
            self._always_on_top = is_pinned
            self.set_always_on_top(is_pinned) # Win32 flicker-free call
            if hasattr(self, 'options_window') and self.options_window:
                self.options_window.update_state_from_parent(is_pinned)
            self.save_options("link_master")
            self.logger.info(f"Pin Toggled: {is_pinned}")
        except Exception as e:
            self.logger.error(f"Pin Error: {e}")
            
    def set_pin_state(self, is_pinned: bool):
        """External entry point to set pin state (e.g. from OptionsWindow)."""
        if self.pin_btn.toggled_state != is_pinned:
            self.pin_btn.toggle()
        self._always_on_top = is_pinned
        self.set_always_on_top(is_pinned)
        if hasattr(self, 'options_window') and self.options_window:
            self.options_window.update_state_from_parent(is_pinned)
        self.save_options("link_master")
        
    def toggle_options(self):
        try:
            # Lazy Initialization
            if self.options_window is None:
                import time
                t_opt = time.perf_counter()
                from src.components.sub_windows import OptionsWindow
                self.options_window = OptionsWindow(None, self.db)
                self.logger.info(f"[Profile] OptionsWindow (Lazy) init took {time.perf_counter()-t_opt:.3f}s")
                # Removed setParent to prevent darkening artifacts (Double Transparency)
                # self.options_window.setParent(self, self.options_window.windowFlags())
                self.options_window.closed.connect(self._on_options_window_closed)
                
                # Ensure it has the correct current DB if it changed since start
                if hasattr(self, 'db'):
                    self.options_window.db = self.db
                
                # Sync other states if necessary
                if hasattr(self, '_always_on_top'):
                    self.options_window.update_state_from_parent(self._always_on_top)

            self.logger.info("Toggle Options Clicked")
            is_open = self.opt_btn.toggle()
            if is_open:
                self.options_window.move(self.x() + 10, self.y() + 40)
                self.options_window.show()
                self.options_window.activateWindow()
                self.options_window.raise_()
                
                self.options_window.activateWindow()
                self.options_window.raise_()
                
                self.logger.info(f"Options Window Geometry: {self.options_window.geometry()}, Visible: {self.options_window.isVisible()}")
            else:
                self.options_window.hide()
        except Exception as e:
            self.logger.error(f"Options Error: {e}")
            QMessageBox.critical(self, "Error", f"Options Window Error: {e}")
            
    
    # --- Phase 25: Settings Handlers ---
    def _on_display_lock_toggled(self, checked):
        """Handler for 'Lock Display Mode' checkbox.
        
        Only sets a flag - does NOT change any display behavior.
        The flag is used on close to decide whether to save current overrides.
        """
        self.display_mode_locked = checked
        # No view refresh - this just sets the flag

    def _on_options_window_closed(self):
        """Reset options toggle button when window is closed via X."""
        if self.opt_btn.toggled_state:
            self.opt_btn.toggle()  # Reset toggle state
    
    def _on_help_window_closed(self):
        """Reset help toggle button when window is closed via X."""
        if self.help_btn.toggled_state:
            self.help_btn.toggle()  # Reset toggle state


    def _show_app_preview(self):
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        img_path = app_data.get('cover_image')
        if not img_path or not os.path.exists(img_path):
            QMessageBox.information(self, "App Preview", f"No cover image set for {app_data['name']}")
            return
            
        # Show Dialog
        d = QDialog(self)
        d.setWindowTitle(_("Preview: {name}").format(name=app_data['name']))
        d.setModal(True)
        layout = QVBoxLayout(d)
        
        lbl = QLabel()
        pix = QPixmap(img_path)
        if not pix.isNull():
            # Scale if too big?
            if pix.width() > 800 or pix.height() > 600:
                pix = pix.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pix)
            
        layout.addWidget(lbl)
        d.exec()

    def _open_preferred_url(self):
        """Open the preferred URL of the currently selected app in the browser."""
        app_data = self.app_combo.currentData()
        if not app_data:
            return
            
        url_list_json = app_data.get('url_list', '[]') or '[]'
        
        from src.utils.url_utils import open_first_working_url, URL_OPEN_MANAGER, URL_NO_URLS
        result = open_first_working_url(url_list_json, parent=self)
        
        # If user chose to open manager, or no URLs exist, open the dialog
        if result in (URL_OPEN_MANAGER, URL_NO_URLS):
            self._open_app_url_manager()
    
    def _open_app_url_manager(self):
        """Open URL management dialog for the current app."""
        app_data = self.app_combo.currentData()
        if not app_data:
            return
            
        from src.ui.link_master.dialogs_legacy import URLListDialog
        current_json = app_data.get('url_list', '[]') or '[]'
        
        dialog = URLListDialog(self, url_list_json=current_json)
        if dialog.exec():
            new_json = dialog.get_data()
            
            # Save to registry
            app_id = app_data['id']
            self.registry.update_app(app_id, {'url_list': new_json})
            
            # Refresh app_combo data
            self._load_apps()
            
            # Re-select the same app
            for i in range(self.app_combo.count()):
                item = self.app_combo.itemData(i)
                if item and item.get('id') == app_id:
                    self.app_combo.setCurrentIndex(i)
                    break

    def _open_edit_dialog(self):
        from PyQt6.QtWidgets import QMessageBox
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        # Pass existing data to dialog
        from src.ui.link_master.dialogs import AppRegistrationDialog
        dialog = AppRegistrationDialog(self, app_data=app_data)
        if dialog.exec():
            data = dialog.get_data()
            
            # Phase 32: Handle Unregister/Delete Request
            if data.get('is_unregister'):
                reply = QMessageBox.warning(self, _("Final Confirmation"),
                                          _("This will permanently delete the database for '{name}'.\n"
                                            "Are you absolutely sure?").format(name=app_data['name']),
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    # 1. Remove from Registry
                    self.registry.delete_app(self.current_app_id)
                    
                    # 2. Delete app-specific DB directory/file
                    try:
                        import os
                        import shutil
                        # Logic from database.py: resource/app/<app_name>/dyonis.db
                        # We are at src/apps/link_master_window.py, need to find project root.
                        # src/core/file_handler already has some path logic, but let's be robust.
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        app_dir = os.path.join(project_root, "resource", "app", app_data['name'])
                        
                        if os.path.exists(app_dir):
                            # Ensure current self.db is closed if it matches (prevent lock)
                            if hasattr(self, 'db') and self.db and getattr(self.db, 'app_name', None) == app_data['name']:
                                self.logger.info("Closing current DB before deletion.")
                                # self.db doesn't have a close(), it uses 'with get_connection()'
                                # But we should set it to None to avoid further use.
                                self.db = None

                            shutil.rmtree(app_dir)
                            self.logger.info(f"Deleted app directory: {app_dir}")
                    except Exception as e:
                        self.logger.error(f"Failed to delete app directory: {e}")

                    # 3. Reload Apps and reset
                    self._load_apps()
                    self.current_app_id = None
                    if self.app_combo.count() > 0:
                        self.app_combo.setCurrentIndex(0)
                    else:
                        self._refresh_current_view() # Empty view
                    return
                else:
                    return # Cancelled deletion

            if not data['name'] or not data['storage_root']:
                QMessageBox.warning(self, "Error", "Name and Storage Root are required.")
                return
            
            try:
                import os  # Ensure os is available in this block
                # Handle Image Processing (Resize & Save to App Folder)
                img_path = data.get('cover_image')
                storage_root = data.get('storage_root')
                
                if img_path and os.path.exists(img_path) and storage_root and os.path.exists(storage_root):
                    # Check if it's already the processed one to avoid re-processing if not changed?
                    # But simpler to just process if it's not the destination file.
                    dest_path = os.path.join(storage_root, "app_icon.png")
                    
                    if os.path.normpath(img_path) != os.path.normpath(dest_path):
                        try:
                            from PIL import Image
                            with Image.open(img_path) as img:
                                img = img.resize((80, 80), Image.Resampling.LANCZOS)
                                img.save(dest_path, "PNG")
                            data['cover_image'] = dest_path
                        except ImportError:
                            # Fallback if PIL not available - just copy the file
                            import shutil
                            shutil.copy2(img_path, dest_path)
                            data['cover_image'] = dest_path
                        except Exception as e:
                            self.logger.error(f"Failed to process app icon: {e}")
                            # Keep original path if fail
                
                # Update DB
                self.registry.update_app(app_data['id'], data)
                
                # Phase 32: Reset Root Folder Config to ensure App Settings take precedence
                try:
                    if self.db:
                        # Clear root display overrides
                        # We utilize update_folder_config with explicit None/empty to remove overrides if the DB supports it,
                        # or simply set them to match the new app defaults.
                        # Best approach: If we could delete keys. But update_folder_config merges.
                        # Let's check how update_folder_config handles None.
                        # Assuming basic implementation, we might need to rely on the display logic prioritizing app settings if root config matches default?
                        # No, user wants FORCE precedence.
                        # Let's try to clear them by setting them to None explicitly if the DB logic supports unsetting.
                        # If not, setting them to empty string might work if the getter handles empty string as "not set".
                        self.db.update_folder_config("", {
                            'display_style': None,
                            'display_style_package': None
                        })
                        self.logger.info("Cleared root folder display config to enforce App Settings.")
                except Exception as e:
                    self.logger.warning(f"Failed to reset root folder config: {e}")
                
                # Reload Apps but keep selection
                current_id = app_data['id']
                self._load_apps()
                
                # Re-select
                for i in range(self.app_combo.count()):
                    if self.app_combo.itemData(i) and self.app_combo.itemData(i)['id'] == current_id:
                        self.app_combo.setCurrentIndex(i)
                        break
                        
                QMessageBox.information(self, "Success", f"Updated {data['name']}")
                self._manual_rebuild()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _icon_mouse_press(self, event):
        # Handle Alt+Click for Debug
        if event.button() == Qt.MouseButton.LeftButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self._open_debug_window()
        else:
            # Pass to parent (Drag moves window)
            event.ignore() 

    def _open_debug_window(self):
        from src.ui.link_master.debug_window import LinkMasterDebugWindow
        
        # Get Current App Data
        app_data = self.app_combo.currentData()
        
        self.debug_window = LinkMasterDebugWindow(parent=self, app_data=app_data)
        self.debug_window.move(self.x() + 50, self.y() + 50)
        self.debug_window.show()
    
    # --- Trash Methods moved to: lm_trash.py ---
    # Tag methods moved to LMTagsMixin

    def _create_item_context_menu(self, rel_path):
        """Centralized factory to create a context menu. Delegated to factory module."""
        return create_item_context_menu(self, rel_path)

    def _open_path_in_explorer(self, path):
        import subprocess
        import sys
        import os  # Ensure os is available locally
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', path.replace('/', os.sep)])

    def _update_folder_visibility(self, rel_path, hide):
        """Helper to toggle visibility for a single folder.
        
        Uses _set_visibility_single for partial update (no full rebuild).
        """
        # Use batch ops method which does partial update (no full rebuild)
        self._set_visibility_single(rel_path, visible=(not hide), update_ui=True)

    def _show_full_preview_for_path(self, video_path, folder_path=None, folder_config=None):
        """Phase 16.5: Open preview window for a folder's preview files."""
        if not video_path: return
        
        from src.ui.link_master.preview_window import PreviewWindow
        
        # Convert single path to list if needed
        if isinstance(video_path, str):
            paths = [video_path]
        elif isinstance(video_path, list):
            paths = video_path
        else:
            paths = list(video_path) if video_path else []
        
        # Filter to existing files
        paths = [p for p in paths if p and os.path.exists(p)]
        if not paths:
            QMessageBox.warning(self, "Preview", "No valid preview files found.")
            return
        
        # Get storage root
        app_data = self.app_combo.currentData()
        storage_root = app_data.get('storage_root') if app_data else None
        
        # We need to maintain a reference to avoid GC
        if not hasattr(self, '_preview_windows'):
             self._preview_windows = []
        
        # Cleanup closed windows
        self._preview_windows = [w for w in self._preview_windows if w.isVisible()]
        
        preview_win = PreviewWindow(
            paths, self,
            folder_path=folder_path,
            folder_config=folder_config or {},
            db=self.db,
            storage_root=storage_root,
            deployer=self.deployer,
            target_dir=app_data.get(self.current_target_key) if app_data else None
        )
        if hasattr(preview_win, 'property_changed'):
            preview_win.property_changed.connect(self._on_pinpoint_property_changed)

        self._preview_windows.append(preview_win)
        preview_win.show()
    
    def _show_property_view_for_card(self, folder_path):
        """Phase 28: Open property view for a card (package or category)."""
        if not folder_path or not os.path.exists(folder_path):
            return
        
        app_data = self.app_combo.currentData()
        if not app_data:
            return
        
        storage_root = app_data.get('storage_root')
        if not storage_root:
            return
        
        # Get folder config
        rel_path = os.path.relpath(folder_path, storage_root).replace('\\', '/')
        if rel_path == '.':
            rel_path = ''
        
        folder_config = self.db.get_folder_config(rel_path) if self.db else {}
        
        # Get preview paths - check for manual_preview_path in config
        preview_paths = []
        if folder_config:
            manual_preview = folder_config.get('manual_preview_path')
            if manual_preview:
                if isinstance(manual_preview, str):
                    # Phase 28 FIX: Split by semicolon for multi-previews
                    raw_paths = [p.strip() for p in manual_preview.split(';') if p.strip()]
                    preview_paths = [p for p in raw_paths if os.path.exists(p)]
                elif isinstance(manual_preview, list):
                    preview_paths = [p for p in manual_preview if p and os.path.exists(p)]
        
        # Import and create property view
        from src.ui.link_master.preview_window import PreviewWindow
        
        if not hasattr(self, '_preview_windows'):
            self._preview_windows = []
        
        # Cleanup closed windows
        self._preview_windows = [w for w in self._preview_windows if w.isVisible()]
        
        preview_win = PreviewWindow(
            preview_paths, self,
            folder_path=folder_path,
            folder_config=folder_config or {},
            db=self.db,
            storage_root=storage_root,
            deployer=self.deployer,
            target_dir=app_data.get(self.current_target_key) if app_data else None
        )
        if hasattr(preview_win, 'property_changed'):
            preview_win.property_changed.connect(self._on_pinpoint_property_changed)

        self._preview_windows.append(preview_win)
        preview_win.show()

    def _get_active_card_by_path(self, abs_path):
        """Find the active ItemCard widget for the given absolute path."""
        if not abs_path: return None
        # Use normalized paths for comparison
        try:
            norm_path = os.path.normpath(abs_path).replace('\\', '/').lower()  # Case-insensitive
        except: return None
        
        # Check both layouts
        layouts = []
        if hasattr(self, 'cat_layout'): layouts.append(self.cat_layout)
        if hasattr(self, 'pkg_layout'): layouts.append(self.pkg_layout)
            
        from src.ui.link_master.item_card import ItemCard
        
        card_count = 0
        for layout in layouts:
            if not layout: continue
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if not item: continue
                widget = item.widget()
                try:
                    if isinstance(widget, ItemCard):
                        card_count += 1
                        w_path = os.path.normpath(widget.path).replace('\\', '/').lower()  # Case-insensitive
                        if w_path == norm_path:
                            return widget
                except: pass
        
        # Debug log if not found
        print(f"PROFILE: _get_active_card_by_path: NOT FOUND. SearchPath={norm_path}, TotalCards={card_count}")
        return None

    def _on_pinpoint_property_changed(self, update_kwargs):
        """Phase 28: Update a single card immediately when properties change."""
        # Note: PreviewWindow usually provides relateve path info or we have to use folder_path
        # The sender (PreviewWindow) knows the absolute path.
        sender = self.sender()
        if not sender or not hasattr(sender, 'folder_path'):
            return
            
        path = sender.folder_path
        card = self._get_active_card_by_path(path)
        if card:
            # Update the widget data directly
            card.update_data(**update_kwargs)
            # Force style update for conflicts etc.
            if hasattr(card, '_update_style'):
                card._update_style()
                
            # Phase 28: If tag or scope changed, re-run visual conflict detection 
            # as it might affect other visible cards (or resolve them)
            if 'conflict_tag' in update_kwargs or 'conflict_scope' in update_kwargs:
                if hasattr(self, '_refresh_tag_conflicts_visual'):
                    self._refresh_tag_conflicts_visual()

    def _handle_explorer_properties_edit(self, abs_paths):
        """Handle property edit requests from ExplorerPanel by syncing selection first."""
        if not abs_paths: return
        self.selected_paths = set(abs_paths)
        self._last_selected_path = abs_paths[0]
        # Trigger the consolidated pinpoint update method
        if hasattr(self, '_batch_edit_properties_selected'):
            self._batch_edit_properties_selected()

    def _get_app_menu_style(self):
        return """
            QMenu { background-color: #2b2b2b; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; color: #ddd; }
            QMenu::item:selected { background-color: #3498db; color: white; }
            QMenu::item:disabled { color: #555; }
        """

    def _menu_style(self):
        return """
            QMenu { background-color: #2b2b2b; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; color: #ddd; }
            QMenu::item:selected { background-color: #3498db; color: white; }
            QMenu::item:disabled { color: #555; }
        """

    def _handle_deploy_single(self, rel_path):
        """Deploy a single item from context menu."""
        if not self._deploy_single(rel_path, update_ui=True):
            QMessageBox.warning(self, "Deploy Error", f"Failed to deploy {rel_path}")

    def _handle_unlink_single(self, rel_path):
        """Unlink a single item from context menu."""
        self._unlink_single(rel_path, update_ui=True)

    def _handle_conflict_swap(self, rel_path, target_link):
        """Force deploy by removing conflict."""
        reply = QMessageBox.warning(self, "Conflict Swap", 
                                    f"Overwrite target?\n{target_link}\n\nThis will DELETE the existing file.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.islink(target_link) or os.path.isfile(target_link):
                    os.remove(target_link)
                elif os.path.isdir(target_link):
                    import shutil
                    shutil.rmtree(target_link)
                
                # Now deploy
                self._deploy_items([rel_path])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Swap failed: {e}")

    # --- Search Methods moved to: lm_search.py ---
    
    # --- Preset Filter Methods moved to: lm_presets.py ---

    def _reset_all_folder_attributes(self):
        """Reset all folder configuration for the current app."""
        if not self.current_app_id: return
        self.logger.info("Resetting all folder attributes for current app.")
        self.db.reset_app_folder_configs()
        self._refresh_current_view()
        QMessageBox.information(self, "Success", "All folder attributes have been reset.")

    def _export_hierarchy_current(self):
        """Export properties starting from the current view level."""
        if not self.storage_root or not self.current_view_path: return
        try:
            rel_path = os.path.relpath(self.current_view_path, self.storage_root).replace('\\', '/')
            if rel_path == ".": rel_path = ""
            self._export_hierarchy(rel_path)
        except:
            self._export_hierarchy("")

    def _manual_rebuild(self):
        """Forces a full re-scan and cache refresh."""
        if not self.storage_root: return
        self.logger.info("Triggering manual rebuild (Full Re-scan).")
        
        # Phase 22: Clear any internal cache in workers/scanner
        # Both workers rely on the same scanner instance, we just force a scan.
        self._load_items_for_path(self.storage_root, force=True)
        
        # If a category is selected, refresh its contents too
        if hasattr(self, 'current_path') and self.current_path:
             self._load_package_contents(self.current_path)
             
        QMessageBox.information(self, "Manual Rebuild", "再構築が完了しました。")


    def _update_exe_links(self, app_data: dict):
        """Update executable link buttons in title bar center based on app settings."""
        import json
        import subprocess
        
        # Clear existing buttons from title bar center
        while self.title_bar_center_layout.count():
            item = self.title_bar_center_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not app_data:
            return
        
        exe_json = app_data.get('executables', '[]')
        try:
            executables = json.loads(exe_json) if exe_json else []
        except:
            executables = []
        
        for exe in executables:
            name = exe.get('name', 'Unknown')
            path = exe.get('path', '')
            args = exe.get('args', '')
            
            btn = QPushButton(f"▶ {name}")
            # Phase 1.1.105: Create visible tooltip label instead of native tooltip
            tooltip_text = path.split('\\')[-1] if path else ""  # Just filename
            
            # Phase 28: Apply custom styling with tighter padding
            bg_color = exe.get('btn_color', '#3498db')
            tx_color = exe.get('text_color', '#ffffff')
            
            # Helper for hover/pressed effects (simplified)
            from PyQt6.QtGui import QColor
            base_q = QColor(bg_color)
            hover_q = base_q.lighter(120).name()
            press_q = base_q.darker(120).name()
            
            btn.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: {bg_color}; 
                    color: {tx_color}; 
                    border: 1px solid rgba(255, 255, 255, 0.1); 
                    padding: 2px 6px; 
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ 
                    background-color: {hover_q}; 
                    border: 1px solid rgba(255, 255, 255, 0.3);
                }}
                QPushButton:pressed {{ 
                    background-color: {press_q}; 
                    padding-top: 3px;
                    padding-left: 5px;
                }}
            """)
            
            # Capture path/args for lambda
            def make_launcher(p, a):
                def launch():
                    try:
                        if not p: return
                        if a:
                            subprocess.Popen([p] + a.split())
                        else:
                            subprocess.Popen([p])
                    except Exception as e:
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "Error", f"Failed to launch: {e}")
                return launch
            
            btn.clicked.connect(make_launcher(path, args))
            
            # Phase 1.1.110: Apply TooltipStyles and set native tooltip
            from src.ui.styles import TooltipStyles
            btn.setToolTip(f"Launch: {path}\nArgs: {args}" if args else f"Launch: {path}")
            current_style = btn.styleSheet()
            btn.setStyleSheet(current_style + TooltipStyles.DARK)
            
            self.title_bar_center_layout.addWidget(btn)

    def _open_executables_editor(self):
        """Open dialog to edit executables for the current app."""
        import json
        from src.ui.link_master.dialogs_legacy import ExecutablesManagerDialog
        
        app_data = self.app_combo.currentData()
        if not app_data:
            QMessageBox.warning(self, "Error", "アプリを選択してください。")
            return
        
        exe_json = app_data.get('executables', '[]')
        try:
            executables = json.loads(exe_json) if exe_json else []
        except:
            executables = []
        
        dialog = ExecutablesManagerDialog(self, executables)
        if dialog.exec():
            new_executables = dialog.get_executables()
            
            # Save to DB
            self.registry.update_app(app_data['id'], {'executables': json.dumps(new_executables)})
            
            # Update local data and refresh title bar
            app_data['executables'] = json.dumps(new_executables)
            self._update_exe_links(app_data)

    def _register_sticky_help(self):
        """Register key UI elements for the Sticky Help system."""
        self.help_manager.register_sticky("target_app", self.app_combo)
        self.help_manager.register_sticky("tag_bar", self.tag_bar)
        self.help_manager.register_sticky("search_bar", self.search_bar)
        self.help_manager.register_sticky("explorer_btn", self.btn_drawer)
        self.help_manager.register_sticky("sidebar_strip", self.sidebar_tabs)
        self.help_manager.register_sticky("presets_btn", self.btn_presets)
        self.help_manager.register_sticky("notes_btn", self.btn_notes)
        self.help_manager.register_sticky("tools_btn", self.btn_tools)
        self.help_manager.register_sticky("search_logic", self.search_logic)
        
        # Load any existing sticky data (including free ones)
        self.help_manager.load_all()

    def _show_help_button_menu(self, pos):
        """Show context menu for the Help button (Only in active Edit Mode)."""
        if not self.help_manager.is_help_visible or not self.help_manager.is_edit_mode:
            return

        menu = QMenu(self)
        add_sticky_action = menu.addAction(_("Add New Help Note"))
        bring_to_screen_action = menu.addAction(_("⭐ Bring Off-Screen to View"))
        
        # Import all help data from other language
        from src.core.lang_manager import get_lang_manager
        lang_manager = get_lang_manager()
        import_menu = menu.addMenu(_("Import All from Language..."))
        import_actions = {}
        for lang_code, lang_name in lang_manager.get_available_languages():
            if lang_code != lang_manager.current_language:
                action = import_menu.addAction(f"{lang_name} ({lang_code})")
                import_actions[action] = lang_code
        
        menu.addSeparator()
        cancel_edit_action = menu.addAction(_("Cancel (Exit Edit Mode)"))
        
        # Calculate global position for context menu
        global_pos = self.help_btn.mapToGlobal(pos)
        action = menu.exec(global_pos)
        
        if action == add_sticky_action:
            self.help_manager.add_free_sticky()
            self.help_btn._force_state(True)
        elif action == bring_to_screen_action:
            self.help_manager.bring_all_to_screen()
        elif action == cancel_edit_action:
            # 変更を破棄してEdit Modeを抜ける
            self.help_manager.cancel_all_edits()
            self.help_btn._force_state(self.help_manager.is_help_visible)
        elif action in import_actions:
            # Bulk import all help data from selected language
            source_lang = import_actions[action]
            self._import_all_help_from_language(source_lang)
    
    def _import_all_help_from_language(self, source_lang_code):
        """Import all help data from another language."""
        from src.core.lang_manager import get_lang_manager
        lang_manager = get_lang_manager()
        
        # Load all help data from source language
        source_help = lang_manager._load_help_yaml(source_lang_code)
        source_notes = source_help.get("help_notes", {})
        
        if not source_notes:
            QMessageBox.information(self, "Import", f"No help data found in {source_lang_code}.")
            return
        
        # Apply to all registered stickies
        if not self.help_manager:
            QMessageBox.information(self, "Import", "Help system not initialized. Open Help once before importing.")
            return

        imported_count = 0
        for eid, sticky in self.help_manager.stickies.items():
            if eid in source_notes:
                note_data = lang_manager._to_regular_dict(source_notes[eid])
                sticky.from_dict(note_data)
                imported_count += 1
        
        # Save imported data to current language
        self.help_manager.save_all()
        
        QMessageBox.information(self, "Import Complete", 
            f"Imported {imported_count} help notes from {source_lang_code}.")

    def toggle_help(self):
        """Toggle Sticky Help. Alt+Click triggers Edit Mode."""
        # Lazy Initialization
        if self.help_manager is None:
            from src.core.link_master.help_manager import StickyHelpManager
            self.help_manager = StickyHelpManager(self)
            self._register_sticky_help()

        modifiers = QApplication.keyboardModifiers()
        is_alt = bool(modifiers & Qt.KeyboardModifier.AltModifier)
        
        # self.logger.info(f"[HelpProfile] UI toggle_help: is_alt={is_alt}")
        self.help_manager.toggle_help(edit_mode=is_alt)
        
        # Sync title bar button state
        self.help_btn._force_state(self.help_manager.is_help_visible)

    def _on_help_window_closed(self):
        # Legacy cleanup or internal sync
        if hasattr(self, 'help_btn'):
            self.help_btn._force_state(False)
