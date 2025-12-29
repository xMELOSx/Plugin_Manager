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


        layout.addStretch()
        
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)  # Use close() to emit closed signal
        layout.addWidget(close_btn)
        
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
        self._save_settings()  # Auto-save on change

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
        self._save_settings()

    def _on_remember_geo_toggled(self, checked):
        self._save_settings()

    def update_state_from_parent(self, is_pinned: bool):
        """Called when parent changes state to sync checkbox."""
        block = self.always_top_cb.blockSignals(True)
        self.always_top_cb.setChecked(is_pinned)
        self.always_top_cb.blockSignals(block)
    
    def closeEvent(self, event):
        """Override to emit closed signal when X button is clicked."""
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
