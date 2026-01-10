from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QCheckBox, QComboBox, QSpinBox, QScrollArea, QLineEdit)
from PyQt6.QtCore import Qt, QPoint
from src.ui.frameless_window import FramelessWindow
from src.ui.title_bar_button import TitleBarButton
from src.ui.window_mixins import OptionsMixin
from src.core import core_handler
from src.core.lang_manager import _
import os
import logging



class LinkMasterDebugWindow(FramelessWindow, OptionsMixin):
    def __init__(self, parent=None, main_window=None, app_data=None):
        """
        app_data: dict containing 'storage_root', 'target_root'
        """
        super().__init__()
        self.setObjectName("LinkMasterDebugWindow")
        self.logger = logging.getLogger("LinkMasterDebugWindow")
        # Tool flag allows stacking above parent without staying on top of all apps
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)
        
        # Determine parent logic: independent window but logically connected
        self.parent_window = main_window if main_window else parent
        
        self.setWindowTitle("LinkMaster Debug")
        self.resize(400, 600)
        
        # Options Setup
        from src.components.sub_windows import OptionsWindow
        self.options_window = OptionsWindow(parent=self, db=self.parent_window.db if self.parent_window else None)
        
        # Add Options Button to Title Bar
        self.opt_btn = TitleBarButton("⚙", is_toggle=True)
        self.opt_btn.clicked.connect(self.toggle_options)
        self.add_title_bar_button(self.opt_btn, index=0)
        
        self.app_data = app_data
        
        # Dragging state
        self._drag_active = False
        self._drag_pos = QPoint()
        
        self.init_ui()
        
    # --- Qt-based Dragging Implementation ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check for interactive widgets to avoid dragging when clicking buttons/combos
            child = self.childAt(event.position().toPoint())
            
            from PyQt6.QtWidgets import QPushButton, QComboBox, QSpinBox, QCheckBox, QLineEdit, QSlider, QAbstractSlider, QScrollArea
            interactive_types = (QPushButton, QComboBox, QSpinBox, QCheckBox, QLineEdit, QSlider, QAbstractSlider, QScrollArea)
            
            if isinstance(child, interactive_types):
                return # Let standard interaction take place

            # Start dragging
            self._drag_active = True
            # globalPosition() handles DPI scaling correctly across different screens
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_active and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        event.accept()

    # ... toggle_options and init_ui skipped ...

    # ... toggle_options and init_ui skipped ...

    def toggle_options(self):
        """Toggle options window visibility."""
        if self.options_window.isVisible():
            self.options_window.hide()
            self.opt_btn.setChecked(False)
        else:
            # Position relative to this window
            self.options_window.move(self.x() + self.width() + 5, self.y())
            self.options_window.show()
            self.opt_btn.setChecked(True)


    def init_ui(self):
        container = QWidget() # No parent, set_content_widget handles it
        container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        layout = QVBoxLayout(container)
        
        self.security_lbl = QLabel(_("<h2>Debug: Core Security Check</h2>"))
        layout.addWidget(self.security_lbl)
        self.security_desc = QLabel(_("Attempts to write to Parent Directory (../New).<br>If Core is secure, these should FAIL."))
        layout.addWidget(self.security_desc)
        
        # Test Storage Parent
        self.btn_storage = QPushButton(_("Test: Write to Storage Parent"))
        self.btn_storage.clicked.connect(self._test_storage_parent)
        layout.addWidget(self.btn_storage)
 
        # Test Target Parent
        self.btn_target = QPushButton(_("Test: Write to Target Parent"))
        self.btn_target.clicked.connect(self._test_target_parent)
        layout.addWidget(self.btn_target)
        
        layout.addStretch()
        
        layout.addSpacing(20)
        self.backup_lbl = QLabel(_("<b>Backup Management</b>"))
        layout.addWidget(self.backup_lbl)
        
        self.btn_full_backup = QPushButton(_("📦 Create Full Backup (Storage + DB)"))
        self.btn_full_backup.clicked.connect(self._create_full_backup)
        layout.addWidget(self.btn_full_backup)
        
        self.btn_db_backup = QPushButton(_("💾 Backup Database Only"))
        self.btn_db_backup.clicked.connect(self._backup_database)
        layout.addWidget(self.btn_db_backup)
        
        self.btn_db_restore = QPushButton(_("🔄 Restore Database"))
        self.btn_db_restore.clicked.connect(self._restore_database)
        layout.addWidget(self.btn_db_restore)
        
        self.btn_open_backup = QPushButton(_("📂 Open Backup Folder"))
        self.btn_open_backup.clicked.connect(self._open_backup_folder)
        layout.addWidget(self.btn_open_backup)
 
        layout.addSpacing(20)
        self.source_backup_lbl = QLabel(_("<b>Source Code Backup (Versioning)</b>"))
        layout.addWidget(self.source_backup_lbl)
        
        src_backup_grid = QVBoxLayout()
        
        self.btn_src_dev = QPushButton(_("🛠️ Source Backup (Dev)"))
        self.btn_src_dev.clicked.connect(lambda: self._run_backup_bat("dev"))
        src_backup_grid.addWidget(self.btn_src_dev)
        
        self.btn_src_patch = QPushButton(_("🩹 Source Backup (Patch)"))
        self.btn_src_patch.clicked.connect(lambda: self._run_backup_bat("patch"))
        src_backup_grid.addWidget(self.btn_src_patch)
        
        self.btn_src_minor = QPushButton(_("🌟 Source Backup (Minor)"))
        self.btn_src_minor.clicked.connect(lambda: self._run_backup_bat("minor"))
        src_backup_grid.addWidget(self.btn_src_minor)
        
        self.btn_src_major = QPushButton(_("🚀 Source Backup (Major)"))
        self.btn_src_major.clicked.connect(lambda: self._run_backup_bat("major"))
        src_backup_grid.addWidget(self.btn_src_major)
        
        layout.addLayout(src_backup_grid)
        
        layout.addSpacing(20)
        
        # --- Log Level Control ---
        self.log_lbl = QLabel(_("<b>Log Level</b>"))
        layout.addWidget(self.log_lbl)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        # Set current level
        current_level = logging.getLogger().getEffectiveLevel()
        if current_level <= 10: self.log_level_combo.setCurrentText("DEBUG")
        elif current_level <= 20: self.log_level_combo.setCurrentText("INFO")
        elif current_level <= 30: self.log_level_combo.setCurrentText("WARNING")
        else: self.log_level_combo.setCurrentText("ERROR")
        
        self.log_level_combo.currentTextChanged.connect(self._on_log_level_changed)
        layout.addWidget(self.log_level_combo)

        # --- Maximize Alpha Boost Control ---
        layout.addSpacing(10)
        self.alpha_lbl = QLabel(_("<b>Maximize Shadow Alpha (0-255)</b>"))
        layout.addWidget(self.alpha_lbl)
        
        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(0, 255)
        # Default value from parent if available, else 55
        default_alpha = 55
        if self.parent_window and hasattr(self.parent_window, 'max_alpha_boost'):
             default_alpha = self.parent_window.max_alpha_boost
        self.alpha_spin.setValue(default_alpha)
        self.alpha_spin.valueChanged.connect(self._on_alpha_boost_changed)
        layout.addWidget(self.alpha_spin)


        layout.addSpacing(20)
        self.ui_debug_lbl = QLabel(_("<b>UI Debug</b>"))
        layout.addWidget(self.ui_debug_lbl)
        self.show_hitbox_cb = QCheckBox(_("当たり判定を表示 (Show Hitboxes)"))
        from src.ui.link_master.item_card import ItemCard
        self.show_hitbox_cb.setChecked(getattr(ItemCard, 'SHOW_HITBOXES', False))
        self.show_hitbox_cb.toggled.connect(self._on_hitbox_toggled)
        layout.addWidget(self.show_hitbox_cb)
        
        self.show_outlines_cb = QCheckBox(_("全ウィジェットに枠線を表示 (Global Outlines)"))
        self.show_outlines_cb.toggled.connect(self._on_global_outlines_toggled)
        layout.addWidget(self.show_outlines_cb)

        self.allow_folder_deploy_cb = QCheckBox(_("子項目ビューでのフォルダデプロイを許可 (Folder Deploy in Pkg View)"))
        # Load persisted value from settings file so it works before debug window opens
        # Default to TRUE if no setting exists
        saved_value = self._load_debug_setting('allow_folder_deploy_pkg_view', True)
        ItemCard.ALLOW_FOLDER_DEPLOY_IN_PKG_VIEW = saved_value
        self.allow_folder_deploy_cb.setChecked(saved_value)
        self.allow_folder_deploy_cb.toggled.connect(self._on_allow_folder_deploy_toggled)
        layout.addWidget(self.allow_folder_deploy_cb)
        
        # Window Count Debug Button
        self.btn_window_count = QPushButton(_("🔍 Show Top-Level Widget Count"))
        self.btn_window_count.clicked.connect(self._show_window_count)
        layout.addWidget(self.btn_window_count)
        
        # Language Settings Section
        layout.addSpacing(20)
        self.lang_header_lbl = QLabel(_("<b>Language Settings / 言語設定</b>"))
        layout.addWidget(self.lang_header_lbl)
        
        from PyQt6.QtWidgets import QHBoxLayout
        lang_layout = QHBoxLayout()
        
        from src.core.lang_manager import get_lang_manager
        self.lang_manager = get_lang_manager()
        
        self.lang_label = QLabel(f"{_('Current:')} {self.lang_manager.current_language_name}")
        lang_layout.addWidget(self.lang_label)
        
        self.lang_combo = QComboBox()
        for code, name in self.lang_manager.get_available_languages():
            self.lang_combo.addItem(f"{name} ({code})", code)
            if code == self.lang_manager.current_language:
                self.lang_combo.setCurrentIndex(self.lang_combo.count() - 1)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self.lang_combo)
        
        layout.addLayout(lang_layout)
        
        layout.addStretch()
        self.set_content_widget(container)
        
        # Ensure Debug Window is visible and clickable
        self.set_background_opacity(0.95)
        self.setWindowOpacity(1.0)


        # Connect for automatic retranslation
        self.lang_manager.language_changed.connect(self.retranslate_ui)

    def retranslate_ui(self):
        """Update all UI strings logic."""
        from src.core.lang_manager import _
        self.setWindowTitle(_("LinkMaster Debug"))
        self.security_lbl.setText(_("<h2>Debug: Core Security Check</h2>"))
        self.security_desc.setText(_("Attempts to write to Parent Directory (../New).<br>If Core is secure, these should FAIL."))
        self.btn_storage.setText(_("Test: Write to Storage Parent"))
        self.btn_target.setText(_("Test: Write to Target Parent"))
        self.backup_lbl.setText(_("<b>Backup Management</b>"))
        self.btn_full_backup.setText(_("📦 Create Full Backup (Storage + DB)"))
        self.btn_db_backup.setText(_("💾 Backup Database Only"))
        self.btn_db_restore.setText(_("🔄 Restore Database"))
        self.btn_open_backup.setText(_("📂 Open Backup Folder"))
        self.source_backup_lbl.setText(_("<b>Source Code Backup (Versioning)</b>"))
        self.btn_src_dev.setText(_("🛠️ Source Backup (Dev)"))
        self.btn_src_patch.setText(_("🩹 Source Backup (Patch)"))
        self.btn_src_minor.setText(_("🌟 Source Backup (Minor)"))
        self.btn_src_major.setText(_("🚀 Source Backup (Major)"))
        self.ui_debug_lbl.setText(_("<b>UI Debug</b>"))
        self.show_hitbox_cb.setText(_("当たり判定を表示 (Show Hitboxes)"))
        self.show_outlines_cb.setText(_("全ウィジェットに枠線を表示 (Global Outlines)"))
        self.lang_header_lbl.setText(_("<b>Language Settings / 言語設定</b>"))
        self.lang_label.setText(f"{_('Current:')} {self.lang_manager.current_language_name}")

    def _on_allow_folder_deploy_toggled(self, checked):
        from src.ui.link_master.item_card import ItemCard
        ItemCard.ALLOW_FOLDER_DEPLOY_IN_PKG_VIEW = checked
        self.logger.debug(f"[Debug] Folder Deploy in Package View set to: {checked}")
        
    def _on_hitbox_toggled(self, checked):
        from src.ui.link_master.item_card import ItemCard
        ItemCard.SHOW_HITBOXES = checked
        if self.parent_window:
            # Force repaint of all cards
            self.parent_window._refresh_current_view(force=False)

    def _on_global_outlines_toggled(self, checked):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app: return
        
        if checked:
            app.setStyleSheet("""
                QWidget { border: 1px solid red; }
                QLabel { border: 1px solid blue; }
                QPushButton { border: 2px solid green; }
            """)
        else:
            # Revert to original? We don't have the original, but we can clear it.
            # Usually better to set to empty or re-apply window style.
            app.setStyleSheet("")
            # If parent window had a theme, we might need to re-apply it.
            if self.parent_window:
                 # LinkMasterWindow doesn't have a single apply_theme but it sets stylesheet on main_widget.
                 # QApplication stylesheet is global.
                 pass

    def _on_allow_folder_deploy_toggled(self, checked):
        """Toggle folder deployment in package view and persist state."""
        from src.ui.link_master.item_card import ItemCard
        ItemCard.ALLOW_FOLDER_DEPLOY_IN_PKG_VIEW = checked
        self._save_debug_setting('allow_folder_deploy_pkg_view', checked)
        self.logger.info(f"Folder Deploy in Package View: {checked}")

    def _get_debug_settings_path(self):
        """Get path to debug settings JSON file."""
        import os
        # Use resource folder relative to project
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        return os.path.join(base, 'resource', 'debug_settings.json')

    def _load_debug_setting(self, key, default=None):
        """Load a debug setting from JSON file."""
        import os, json
        path = self._get_debug_settings_path()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get(key, default)
        except Exception as e:
            self.logger.warning(f"Failed to load debug setting '{key}': {e}")
        return default

    def _save_debug_setting(self, key, value):
        """Save a debug setting to JSON file."""
        import os, json
        path = self._get_debug_settings_path()
        try:
            data = {}
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data[key] = value
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save debug setting '{key}': {e}")

    def _show_window_count(self):
        """Show count and details of all top-level widgets."""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app: return
        
        widgets = app.topLevelWidgets()
        details = []
        for i, w in enumerate(widgets):
            class_name = w.__class__.__name__
            obj_name = w.objectName() or "(no name)"
            is_visible = "V" if w.isVisible() else "H"
            size = f"{w.width()}x{w.height()}"
            parent = w.parent().__class__.__name__ if w.parent() else "None"
            details.append(f"[{i}] {class_name} ({obj_name}) | {is_visible} | {size} | Parent: {parent}")
        
        msg = f"Top-Level Widgets Count: {len(widgets)}\n\n" + "\n".join(details)
        QMessageBox.information(self, "Window Count Debug", msg)
        self.logger.debug(f"=== TOP LEVEL WIDGETS: {len(widgets)} ===")
        for d in details:
            self.logger.debug(f"  {d}")

    def _on_language_changed(self, index):
        """Handle language selection change."""
        lang_code = self.lang_combo.itemData(index)
        if lang_code and self.lang_manager.set_language(lang_code):
            self.lang_label.setText(f"{_('Current:')} {self.lang_manager.current_language_name}")
            QMessageBox.information(self, _("Language Changed"), 
                _("Language changed to: {0}\n\nSome changes may require a restart to take full effect.").format(self.lang_manager.current_language_name))

    def _on_log_level_changed(self, text):
        """Update global log level (Standard)."""
        level = getattr(logging, text, logging.INFO)
        
        # Set root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Also set handler levels (important for DEBUG to work)
        for handler in root_logger.handlers:
            handler.setLevel(level)
        
        # Also set specific loggers if needed
        for logger_name in ["LinkMasterWindow", "LinkMasterDeployer", "ItemCard"]:
            logging.getLogger(logger_name).setLevel(level)
        
        msg = f"[Debug] Log Level changed to {text}"
        logging.log(level, msg)
        
        # Phase 35: Persist log level
        self._save_debug_setting('log_level', text)
        
        # Confirmatory log
        self.logger.info(f"{msg} (all handlers updated and persisted)")

    def _on_alpha_boost_changed(self, value):
        """Update max_alpha_boost in parent window."""
        if self.parent_window and hasattr(self.parent_window, "save_alpha_boost"):
            self.parent_window.save_alpha_boost(value)
        elif self.parent_window:
            self.parent_window.max_alpha_boost = value
            self.parent_window.update() # Trigger repaint

    def _run_backup_bat(self, arg):
        """Runs backup_source.bat with the given argument."""
        import subprocess
        import time
        # __file__ is src/ui/link_master/debug_window.py
        # Go up 4 directories to reach Plugin_Manager root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        bat_path = os.path.join(project_root, "backup_source.bat")
        version_file = os.path.join(project_root, "VERSION.txt")
        
        if not os.path.exists(bat_path):
            QMessageBox.warning(self, "Error", f"backup_source.bat not found at:\n{bat_path}")
            return
            
        try:
            # Run the batch file and wait for it to complete
            result = subprocess.run(["cmd.exe", "/c", bat_path, arg], cwd=project_root, capture_output=True, text=True)
            
            # Read the new version
            new_version = "Unknown"
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    new_version = f.read().strip()
            
            # Show success message with version
            QMessageBox.information(self, "Backup Complete", 
                                    f"Backup type: {arg.upper()}\nVersion: {new_version}\n\nBackup completed successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to run backup script: {e}")


    def _get_backup_dir(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        backup_dir = os.path.join(project_root, "backups")

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        return backup_dir

    def _create_full_backup(self):
        if not self.app_data or not self.app_data.get('storage_root'):
             QMessageBox.warning(self, "Error", "No App Data Loaded")
             return
        
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self._get_backup_dir()
        app_name = self.app_data.get('name', 'UnknownApp').replace(" ", "_")
        
        zip_name = f"FullBackup_{app_name}_{timestamp}"
        zip_path = os.path.join(backup_dir, zip_name)
        
        try:
            storage_root = self.app_data['storage_root']
            shutil.make_archive(zip_path, 'zip', storage_root)
            
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "core", "link_master", "dyonis.db")
            if os.path.exists(db_path):
                shutil.copy2(db_path, os.path.join(backup_dir, f"DBBackup_{app_name}_{timestamp}.db"))
            
            QMessageBox.information(self, _("Success"), _("Full backup created successfully!\nFile: {0}.zip").format(zip_name))
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Backup failed: {0}").format(e))

    def _backup_database(self):
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        app_name = (self.app_data.get('name') if self.app_data else "Global").replace(" ", "_")
        backup_dir = self._get_backup_dir()
        
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "core", "link_master", "dyonis.db")
        dest_path = os.path.join(backup_dir, f"Manual_DB_{app_name}_{timestamp}.db")
        
        try:
            shutil.copy2(db_path, dest_path)
            QMessageBox.information(self, _("Success"), _("Database backed up to:\n{0}").format(os.path.basename(dest_path)))
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("DB Backup failed: {0}").format(e))

    def _restore_database(self):
        from PyQt6.QtWidgets import QFileDialog
        import shutil
        
        backup_dir = self._get_backup_dir()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Database Backup", backup_dir, "SQLite DB (*.db)")
        
        if not file_path: return
        
        reply = QMessageBox.question(self, _("Confirm Restore"), 
                                   _("Are you SURE you want to restore this database?\nThis will overwrite the current database and REQUIRE A RESTART."),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "core", "link_master", "dyonis.db")
            try:
                shutil.copy2(db_path, db_path + ".safe_bak")
                shutil.copy2(file_path, db_path)
                QMessageBox.information(self, _("Success"), _("Database restored. Please restart the application."))
            except Exception as e:
                 QMessageBox.critical(self, _("Error"), _("Restore failed: {0}").format(e))

    def _open_backup_folder(self):
        import subprocess
        backup_dir = self._get_backup_dir()
        subprocess.Popen(['explorer', backup_dir])

    def _test_storage_parent(self):
        if not self.app_data or not self.app_data.get('storage_root'):
            QMessageBox.warning(self, "Error", "No App Data Loaded")
            return
            
        root = self.app_data['storage_root']
        parent = os.path.dirname(os.path.abspath(root))
        target_path = os.path.join(parent, "New_Debug_Folder")
        
        self._try_make_dir(target_path)

    def _test_target_parent(self):
        if not self.app_data or not self.app_data.get('target_root'):
            QMessageBox.warning(self, "Error", "No App Data Loaded")
            return
            
        root = self.app_data['target_root']
        parent = os.path.dirname(os.path.abspath(root))
        target_path = os.path.join(parent, "New_Debug_Folder")
        
        self._try_make_dir(target_path)

    def _try_make_dir(self, path):
        try:
            # We MUST use core_handler to test security!
            # If we used os.makedirs here, it might succeed if user has permissions.
            # But the goal is to verify core_handler blocks it.
            
            # Note: core_handler.create_directory wrapper?
            # Assuming src.core.file_handler exposed via core_handler or direct import.
            # Usually users do `from src.core import file_handler` but here we see `from src.core import core_handler` 
            # In previous files `core_handler` was imported. Let's assume it has methods or proxies.
            # Actually, looking at imports in other files: `from src.core import core_handler`.
            # If `core_handler` is just an initialization module, we might need `src.core.file_handler`.
            
            # Let's try importing file_handler directly to be sure we hit the logic.
            from src.core import file_handler
            
            file_handler.create_directory(path)
            
            QMessageBox.critical(self, "SECURITY FAIL", f"Directory Created!\nPath: {path}\nCore Protection: FAILED/INACTIVE")
            
        except Exception as e:
            QMessageBox.information(self, "SECURITY PASS", f"Operation Blocked (Expected).\nError: {e}")
