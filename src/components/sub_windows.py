""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QCheckBox, QSlider, QSpinBox, QApplication
from PyQt6.QtCore import Qt, pyqtSignal
from src.ui.frameless_window import FramelessWindow

class OptionsWindow(FramelessWindow):
    closed = pyqtSignal()  # Signal emitted when window is closed via X button
    
    def __init__(self, parent_debug_window=None, db=None):
        super().__init__()
        self.setWindowTitle("Options")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)
        self.resize(300, 240)

        self.parent_debug_window = parent_debug_window
        self.db = db  # Database for settings persistence
        self.set_resizable(False) 
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        
        from src.core.lang_manager import _
        header_lbl = QLabel(_("<b>Settings</b>"))
        layout.addWidget(header_lbl)
        
        # Always on Top
        self.always_top_cb = QCheckBox(_("Always on Top"))
        self.always_top_cb.toggled.connect(self._on_always_top_toggled)
        layout.addWidget(self.always_top_cb)

        # Remember Geometry
        self.remember_geo_cb = QCheckBox(_("Remember Position/Size"))
        self.remember_geo_cb.toggled.connect(self._on_remember_geo_toggled)
        layout.addWidget(self.remember_geo_cb)
        
        # Background Opacity Control
        opacity_layout = QVBoxLayout()
        opacity_layout.setSpacing(5)
        
        # Row 1: Background
        bg_opacity_layout = QHBoxLayout()
        bg_opacity_lbl = QLabel(_("Background Opacity:"))
        bg_opacity_layout.addWidget(bg_opacity_lbl)
        
        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(20, 100)
        self.bg_opacity_slider.setValue(90)
        
        self.bg_opacity_spin = QSpinBox()
        self.bg_opacity_spin.setRange(20, 100)
        self.bg_opacity_spin.setValue(90)
        self.bg_opacity_spin.setSuffix("%")
        self.bg_opacity_spin.setFixedWidth(75)
        
        bg_opacity_layout.addWidget(self.bg_opacity_slider)
        bg_opacity_layout.addWidget(self.bg_opacity_spin)
        
        # Row 2: Text/Content
        text_opacity_layout = QHBoxLayout()
        text_opacity_lbl = QLabel(_("Text Opacity:"))
        text_opacity_layout.addWidget(text_opacity_lbl)
        
        self.text_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.text_opacity_slider.setRange(20, 100)
        self.text_opacity_slider.setValue(100)
        
        self.text_opacity_spin = QSpinBox()
        self.text_opacity_spin.setRange(20, 100)
        self.text_opacity_spin.setValue(100)
        self.text_opacity_spin.setSuffix("%")
        self.text_opacity_spin.setFixedWidth(75) 
        
        text_opacity_layout.addWidget(self.text_opacity_slider)
        text_opacity_layout.addWidget(self.text_opacity_spin)

        opacity_layout.addLayout(bg_opacity_layout)
        opacity_layout.addLayout(text_opacity_layout)
        layout.addLayout(opacity_layout)

        # Window Size
        size_layout = QVBoxLayout()
        size_header_lbl = QLabel(_("<b>Window Size</b>"))
        size_layout.addWidget(size_header_lbl)
        
        # Width
        width_row = QHBoxLayout()
        width_lbl = QLabel(_("Width:"))
        width_row.addWidget(width_lbl)
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(400, 2560)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(400, 2560)
        self.width_spin.setFixedWidth(75)
        width_row.addWidget(self.width_slider)
        width_row.addWidget(self.width_spin)
        size_layout.addLayout(width_row)
        
        # Height
        height_row = QHBoxLayout()
        height_lbl = QLabel(_("Height:"))
        height_row.addWidget(height_lbl)
        self.height_slider = QSlider(Qt.Orientation.Horizontal)
        self.height_slider.setRange(400, 1440)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(400, 1440)
        self.height_spin.setFixedWidth(75)
        height_row.addWidget(self.height_slider)
        height_row.addWidget(self.height_spin)
        size_layout.addLayout(height_row)
        
        layout.addLayout(size_layout)

        # Connections
        self.bg_opacity_slider.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.bg_opacity_slider, self.bg_opacity_spin, self._apply_bg_opacity))
        self.bg_opacity_spin.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.bg_opacity_slider, self.bg_opacity_spin, self._apply_bg_opacity))
        
        self.text_opacity_slider.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.text_opacity_slider, self.text_opacity_spin, self._apply_text_opacity))
        self.text_opacity_spin.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.text_opacity_slider, self.text_opacity_spin, self._apply_text_opacity))

        self.width_slider.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.width_slider, self.width_spin, self._apply_window_width))
        self.width_spin.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.width_slider, self.width_spin, self._apply_window_width))
        
        self.height_slider.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.height_slider, self.height_spin, self._apply_window_height))
        self.height_spin.valueChanged.connect(lambda v: self._sync_slider_spin(v, self.height_slider, self.height_spin, self._apply_window_height))

        # --- Language Selection ---
        from PyQt6.QtWidgets import QComboBox
        lang_layout = QHBoxLayout()
        lang_lbl = QLabel(_("Language:"))
        lang_layout.addWidget(lang_lbl)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(_("System Default"), "system")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("日本語", "ja")
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self.lang_combo)
        layout.addLayout(lang_layout)
        self.lang_lbl = lang_lbl  # Store for retranslate

        layout.addStretch()
        
        # --- Action Buttons ---
        btn_layout = QHBoxLayout()
        
        about_btn = QPushButton(_("About"))
        about_btn.clicked.connect(self._show_about)
        btn_layout.addWidget(about_btn)
        self.about_btn = about_btn
        
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)  # Use close() to emit closed signal
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        self.set_content_widget(content)

        # Store labels to retranslate
        self.header_lbl = header_lbl
        self.bg_opacity_lbl = bg_opacity_lbl
        self.text_opacity_lbl = text_opacity_lbl
        self.size_header_lbl = size_header_lbl
        self.width_lbl = width_lbl
        self.height_lbl = height_lbl
        self.close_btn = close_btn

        from src.core.lang_manager import get_lang_manager
        get_lang_manager().language_changed.connect(self.retranslate_ui)

    def retranslate_ui(self):
        """Update all UI strings logic."""
        from src.core.lang_manager import _
        self.setWindowTitle(_("Options"))
        self.header_lbl.setText(_("<b>Settings</b>"))
        self.always_top_cb.setText(_("Always on Top"))
        self.remember_geo_cb.setText(_("Remember Position/Size"))
        self.bg_opacity_lbl.setText(_("Background Opacity:"))
        self.text_opacity_lbl.setText(_("Text Opacity:"))
        self.size_header_lbl.setText(_("<b>Window Size</b>"))
        self.width_lbl.setText(_("Width:"))
        self.height_lbl.setText(_("Height:"))
        self.close_btn.setText(_("Close"))
        self.lang_lbl.setText(_("Language:"))
        self.about_btn.setText(_("About"))
        # Update language combo first item (System Default)
        self.lang_combo.setItemText(0, _("System Default"))
    
    def _get_config_path(self):
        """Get path to config/window.json."""
        from src.core.file_handler import FileHandler
        import os
        project_root = FileHandler().project_root
        return os.path.join(project_root, "config", "window.json")

    def _load_settings(self):
        """Load settings from config/window.json."""
        try:
            import json
            import os
            from src.core.file_handler import FileHandler
            
            path = self._get_config_path()
            if not os.path.exists(path):
                return
                
            content = FileHandler().read_text_file(path)
            all_config = json.loads(content)
            settings = all_config.get('options_window', {})
            
            if settings:
                self.always_top_cb.blockSignals(True)
                self.remember_geo_cb.blockSignals(True)
                self.bg_opacity_slider.blockSignals(True)
                self.text_opacity_slider.blockSignals(True)
                
                self.always_top_cb.setChecked(settings.get('always_top', False))
                self.remember_geo_cb.setChecked(settings.get('remember_geo', True))
                self.bg_opacity_slider.setValue(settings.get('bg_opacity', 90))
                self.bg_opacity_spin.setValue(settings.get('bg_opacity', 90))
                self.text_opacity_slider.setValue(settings.get('text_opacity', 100))
                self.text_opacity_spin.setValue(settings.get('text_opacity', 100))

                self.always_top_cb.blockSignals(False)
                self.remember_geo_cb.blockSignals(False)
                self.bg_opacity_slider.blockSignals(False)
                self.text_opacity_slider.blockSignals(False)
                
                # Apply loaded values
                if self.parent_debug_window:
                    self.parent_debug_window.set_background_opacity(settings.get('bg_opacity', 90) / 100.0)
                    self.parent_debug_window.set_content_opacity(settings.get('text_opacity', 100) / 100.0)
                    if settings.get('always_top', False):
                        self.parent_debug_window.set_pin_state(True)
            
            # Load language setting
            saved_lang = all_config.get('language', 'system')
            self.lang_combo.blockSignals(True)
            for i in range(self.lang_combo.count()):
                if self.lang_combo.itemData(i) == saved_lang:
                    self.lang_combo.setCurrentIndex(i)
                    break
            self.lang_combo.blockSignals(False)
        except Exception as e:
            print(f"Failed to load OptionsWindow settings: {e}")
    
    def _save_settings(self):
        """Save settings to config/window.json."""
        try:
            import json
            import os
            from src.core.file_handler import FileHandler
            
            path = self._get_config_path()
            
            # Read existing config
            all_config = {}
            if os.path.exists(path):
                try:
                    content = FileHandler().read_text_file(path)
                    all_config = json.loads(content)
                except:
                    pass
            
            # Update options_window section
            all_config['options_window'] = {
                'always_top': self.always_top_cb.isChecked(),
                'remember_geo': self.remember_geo_cb.isChecked(),
                'bg_opacity': self.bg_opacity_slider.value(),
                'text_opacity': self.text_opacity_slider.value()
            }
            
            FileHandler().write_text_file(path, json.dumps(all_config, indent=4))
        except Exception as e:
            print(f"Failed to save OptionsWindow settings: {e}")
    
    def get_remember_geo(self) -> bool:
        """Return whether geometry should be saved."""
        return self.remember_geo_cb.isChecked()

    def _sync_slider_spin(self, value, slider, spin, apply_func):
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            value = round(value / 5) * 5
        
        slider.blockSignals(True)
        spin.blockSignals(True)
        
        slider.setValue(value)
        spin.setValue(value)
        
        slider.blockSignals(False)
        spin.blockSignals(False)
        
        apply_func(value)
        # Removed: auto-save on change - now saved on close only

    def _apply_bg_opacity(self, value):
        if self.parent_debug_window:
            self.parent_debug_window.set_background_opacity(value / 100.0)

    def _apply_text_opacity(self, value):
        if self.parent_debug_window:
            self.parent_debug_window.set_content_opacity(value / 100.0)

    def _apply_window_width(self, value):
        if self.parent_debug_window:
            curr_h = self.parent_debug_window.height()
            self.parent_debug_window.resize(value, curr_h)

    def _apply_window_height(self, value):
        if self.parent_debug_window:
            curr_w = self.parent_debug_window.width()
            self.parent_debug_window.resize(curr_w, value)

    def _on_language_changed(self, index):
        """Handle language selection change."""
        from src.core.lang_manager import get_lang_manager
        from PyQt6.QtCore import QLocale
        
        lang_code = self.lang_combo.currentData()
        if lang_code == "system":
            # Use system language via QLocale (more reliable in Qt)
            sys_lang = QLocale.system().name()  # e.g., "ja_JP" or "en_US"
            if sys_lang.startswith("ja"):
                lang_code = "ja"
            else:
                lang_code = "en"
        
        lm = get_lang_manager()
        lm.set_language(lang_code)
        
        # Save language preference (as 'system' if that was selected)
        self._save_language_setting(self.lang_combo.currentData())

    def _save_language_setting(self, lang_code):
        """Save language preference to config."""
        try:
            import json
            from src.core.file_handler import FileHandler
            
            path = self._get_config_path()
            all_config = {}
            try:
                content = FileHandler().read_text_file(path)
                all_config = json.loads(content)
            except:
                pass
            
            all_config['language'] = lang_code
            FileHandler().write_text_file(path, json.dumps(all_config, indent=4))
        except Exception as e:
            print(f"Failed to save language setting: {e}")

    def _show_about(self):
        """Show About window (transparent overlay with icon and close button)."""
        from src.core.version import APP_NAME, VERSION, AUTHOR, YEAR, SOURCE_URL
        from src.core.lang_manager import _
        
        # Create or show existing about window
        if not hasattr(self, '_about_window') or self._about_window is None:
            self._about_window = AboutWindow(APP_NAME, VERSION, AUTHOR, YEAR, SOURCE_URL)
        
        self._about_window.show()
        self._about_window.raise_()
        self._about_window.activateWindow()


    def showEvent(self, event):
        """Update sliders to current parent window dimensions when shown."""
        self._sync_size_from_parent()
        super().showEvent(event)
    
    def _sync_size_from_parent(self):
        """Sync width/height sliders with parent window dimensions."""
        if self.parent_debug_window:
            self.width_slider.blockSignals(True)
            self.width_spin.blockSignals(True)
            self.height_slider.blockSignals(True)
            self.height_spin.blockSignals(True)
            
            w = self.parent_debug_window.width()
            h = self.parent_debug_window.height()
            
            self.width_slider.setValue(w)
            self.width_spin.setValue(w)
            self.height_slider.setValue(h)
            self.height_spin.setValue(h)
            
            self.width_slider.blockSignals(False)
            self.width_spin.blockSignals(False)
            self.height_slider.blockSignals(False)
            self.height_spin.blockSignals(False)

    def update_size_from_parent(self):
        """Public method for parent to notify of size changes."""
        if self.isVisible():
            self._sync_size_from_parent()

    def _on_always_top_toggled(self, checked):
        if self.parent_debug_window:
            self.parent_debug_window.set_pin_state(checked)
        # Removed: _save_settings() - now saved on close only

    def _on_remember_geo_toggled(self, checked):
        # Removed: _save_settings() - now saved on close only
        pass

    def update_state_from_parent(self, is_pinned: bool):
        """Called when parent changes state to sync checkbox."""
        block = self.always_top_cb.blockSignals(True)
        self.always_top_cb.setChecked(is_pinned)
        self.always_top_cb.blockSignals(block)
    
    def closeEvent(self, event):
        """Override to emit closed signal and save settings when closed."""
        self._save_settings()  # Save settings only on close
        self.closed.emit()
        super().closeEvent(event)


class HelpWindow(FramelessWindow):
    closed = pyqtSignal()  # Signal emitted when window is closed via X button
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Help")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)
        self.resize(300, 200)
        self.set_resizable(False)
        self._init_ui()

    def _init_ui(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        
        from src.core.lang_manager import _
        self.header_lbl = QLabel(_("<b>Dionys Debug Help</b>"))
        layout.addWidget(self.header_lbl)
        self.bullet1_lbl = QLabel(_("• 📌: Toggle Always on Top"))
        layout.addWidget(self.bullet1_lbl)
        self.bullet2_lbl = QLabel(_("• Win32 Native Resizing Enabled"))
        layout.addWidget(self.bullet2_lbl)
        self.bullet3_lbl = QLabel(_("• F11: Fullscreen"))
        layout.addWidget(self.bullet3_lbl)
        layout.addStretch()
        
        self.close_btn = QPushButton(_("Close"))
        self.close_btn.clicked.connect(self.close)  # Use close() to emit closed signal
        layout.addWidget(self.close_btn)
        
        self.set_content_widget(content)

        from src.core.lang_manager import get_lang_manager
        get_lang_manager().language_changed.connect(self.retranslate_ui)

    def retranslate_ui(self):
        """Update all UI strings logic."""
        from src.core.lang_manager import _
        self.setWindowTitle(_("Help"))
        self.header_lbl.setText(_("<b>Dionys Debug Help</b>"))
        self.bullet1_lbl.setText(_("• 📌: Toggle Always on Top"))
        self.bullet2_lbl.setText(_("• Win32 Native Resizing Enabled"))
        self.bullet3_lbl.setText(_("• F11: Fullscreen"))
        self.close_btn.setText(_("Close"))
    
    def closeEvent(self, event):
        """Override to emit closed signal when X button is clicked."""
        self.closed.emit()
        super().closeEvent(event)


class AboutWindow(FramelessWindow):
    """Transparent overlay About window with icon and close button."""
    closed = pyqtSignal()
    
    def __init__(self, app_name: str, version: str, author: str, year: str, source_url: str):
        super().__init__()
        self.app_name = app_name
        self.version = version
        self.author = author
        self.year = year
        self.source_url = source_url
        
        # Title specified as 'About'
        self.setWindowTitle("About")
        
        # Ensure no maximize/minimize, just tool window behavior
        # MSWindowsFixedSizeDialogHint removes min/max buttons on Windows
        self.setWindowFlags(
            self.windowFlags() 
            | Qt.WindowType.Tool 
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self.resize(380, 320)
        self.set_resizable(False)
        self.hide_min_max_buttons()  # Hide min/max buttons for About dialog
        self._init_ui()
    
    def _init_ui(self):
        from src.core.lang_manager import _
        import os
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(10)
        
        # Icon (centered)
        icon_layout = QHBoxLayout()
        icon_layout.addStretch()
        
        icon_lbl = QLabel()
        # Use application icon from resource
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        icon_path = os.path.join(project_root, "resource", "app_icon.png")
        
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(icon_path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_lbl.setPixmap(pixmap)
        else:
            icon_lbl.setText("⚙️")
            icon_lbl.setStyleSheet("font-size: 64px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_lbl)
        icon_layout.addStretch()
        layout.addLayout(icon_layout)
        
        layout.addSpacing(10)
        
        # App Title (Dyonys Control)
        title_lbl = QLabel(f"<b>{self.app_name}</b>")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("font-size: 20px; color: #fff;")
        layout.addWidget(title_lbl)
        
        # Version
        version_lbl = QLabel(f"Ver.{self.version}")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_lbl.setStyleSheet("font-size: 13px; color: #aaa;")
        layout.addWidget(version_lbl)
        
        layout.addSpacing(5)
        
        # Description
        desc_lbl = QLabel(_("A powerful plugin and link management tool."))
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet("color: #888;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        
        layout.addStretch()
        
        # Metadata: Year & Author
        meta_lbl = QLabel(f"© {self.year} {self.author}")
        meta_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_lbl.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(meta_lbl)
        
        # Source Link
        source_lbl = QLabel(f'<a href="{self.source_url}" style="color: #3498db; text-decoration: none;">GitHub Source</a>')
        source_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        source_lbl.setOpenExternalLinks(True)
        source_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(source_lbl)
        
        layout.addSpacing(15)
        
        # Close button
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e; 
                color: #fff; 
                padding: 8px 30px; 
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
        """)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.set_content_widget(content)
        
        # Store for retranslation
        self.desc_lbl = desc_lbl
        self.close_btn = close_btn
        
        from src.core.lang_manager import get_lang_manager
        get_lang_manager().language_changed.connect(self.retranslate_ui)
    
    def retranslate_ui(self):
        from src.core.lang_manager import _
        self.desc_lbl.setText(_("A powerful plugin and link management tool."))
        self.close_btn.setText(_("Close"))
    
    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
