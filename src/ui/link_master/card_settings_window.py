"""
Link Master: Independent Card Settings Window
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QTabWidget, QSpinBox, 
                             QSlider, QMessageBox, QScrollArea)
from src.ui.common_widgets import StyledSpinBox
from src.ui.frameless_window import FramelessDialog
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from src.core.lang_manager import _

class CardSettingsWindow(FramelessDialog):
    # Signals to communicate back to the main window
    # type_, mode, param, value
    paramChanged = pyqtSignal(str, str, str, object)
    # type_, mode, scale
    scaleChanged = pyqtSignal(str, str, float)
    # type_, mode, param, value (bool)
    checkChanged = pyqtSignal(str, str, str, bool)
    
    lockToggled = pyqtSignal(bool)
    saveRequested = pyqtSignal()
    cancelRequested = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, current_settings, display_mode_locked, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Card Settings"))
        self.set_default_icon()
        self.resize(400, 850)
        self.settings = current_settings
        self.locked = display_mode_locked
        
        # Explicit Title Bar Styling
        self.title_bar.setStyleSheet("background-color: #2b2b2b; border-bottom: 1px solid #3d3d3d;")
        self.title_label.setStyleSheet("color: #ffffff; background-color: transparent; font-weight: bold; padding-left: 5px;")
        
        # Apply dark theme style
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #ddd; }
            QTabWidget::pane { border: 1px solid #555; background: #333; }
            QTabBar::tab { background: #3a3a3a; color: #ddd; padding: 6px 12px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 1px; }
            QTabBar::tab:selected { background: #555; border-bottom: 2px solid #3498db; }
            QTabBar::tab:hover { background: #444; }
            
            QPushButton { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 4px; }
            QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
            QPushButton:pressed { background-color: #222; }
            
            QSlider::groove:horizontal { height: 6px; background: #444; border-radius: 3px; }
            QSlider::handle:horizontal { background: #3498db; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
            QSlider::handle:horizontal:hover { background: #5dade2; border: 1px solid #fff; }
            
            QSpinBox { background-color: #222; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 2px; }
            QSpinBox:focus { border: 1px solid #27ae60; }
        """)
        
        self._setup_ui()
        # Ensure 'closed' is emitted even on simple hide/reject
        self.finished.connect(lambda _: self.closed.emit())

    def _setup_ui(self):
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(10)

        # --- Header (Save/Reset Buttons) - Clean style ---
        header = QHBoxLayout()
        header.addStretch()
        
        save_btn = QPushButton(_("Save"))
        save_btn.setFixedWidth(70)
        save_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border-radius: 4px; padding: 6px; font-weight: bold; } QPushButton:hover { background-color: #2ecc71; }")
        save_btn.clicked.connect(self.saveRequested.emit)
        header.addWidget(save_btn)
        
        cancel_btn = QPushButton(_("Reset"))
        cancel_btn.setFixedWidth(70)
        cancel_btn.setStyleSheet("QPushButton { background-color: #3b3b3b; color: white; border-radius: 4px; padding: 6px; border: 1px solid #555; } QPushButton:hover { background-color: #4a4a4a; }")
        cancel_btn.clicked.connect(self.cancelRequested.emit)
        header.addWidget(cancel_btn)
        
        main_layout.addLayout(header)

        # --- Lock Toggle ---
        from src.ui.slide_button import SlideButton
        lock_layout = QHBoxLayout()
        lock_layout.setSpacing(10)
        
        self._lock_check = SlideButton()
        self._lock_check.setChecked(self.locked)
        self._lock_check.clicked.connect(lambda: self.lockToggled.emit(self._lock_check.isChecked()))
        lock_layout.addWidget(self._lock_check)
        
        lock_lbl = QLabel(_("Lock Display Mode (Persist)"))
        lock_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        lock_layout.addWidget(lock_lbl)
        lock_layout.addStretch()
        main_layout.addLayout(lock_layout)
        
        # --- Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(self.tabs.sizePolicy().horizontalPolicy(), self.tabs.sizePolicy().verticalPolicy())
        
        # 1. Text Mode
        self.tabs.addTab(self._create_mode_tab("text_list"), _("T Text"))
        # 2. Image Mode
        self.tabs.addTab(self._create_mode_tab("mini_image"), _("🖼 Image"))
        # 3. Combined Mode
        self.tabs.addTab(self._create_mode_tab("image_text"), _("🖼T Both"))
        
        main_layout.addWidget(self.tabs)
        
        # --- General Settings (Opacity) - No Frame ---
        # Deploy Button Opacity
        row = QHBoxLayout()
        from src.ui.custom_slider import CustomSlider
        
        op_lbl = QLabel(_("Btn Opacity"))
        op_lbl.setFixedWidth(80)
        row.addWidget(op_lbl)
        
        # Value 0.1 - 1.0 -> 10 - 100
        current_op = int(self.settings.get('deploy_button_opacity', 0.8) * 100)
        
        op_slider = CustomSlider(Qt.Orientation.Horizontal)
        op_slider.setRange(10, 100)
        op_slider.setValue(current_op)
        row.addWidget(op_slider)
        
        op_spin = StyledSpinBox()
        op_spin.setRange(10, 100)
        op_spin.setValue(current_op)
        op_spin.setSuffix("%")
        op_spin.setFixedWidth(60)
        op_spin.setStyleSheet("background: #222; color: #fff; border: 1px solid #555;")
        op_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        row.addWidget(op_spin)
        
        def update_opacity(v):
            op_slider.blockSignals(True)
            op_spin.blockSignals(True)
            op_slider.setValue(v)
            op_spin.setValue(v)
            op_slider.blockSignals(False)
            op_spin.blockSignals(False)
            # Send as generic param change but handled specially by main window probably? 
            # Or use 'category'/'package' type with NONE?
            # Im treating it as a global setting, but mixin treats it as attribute.
            # We will emit for both or handle in main.
            self.paramChanged.emit('global', 'all', 'deploy_button_opacity', v / 100.0)
            
        op_slider.valueChanged.connect(update_opacity)
        op_spin.valueChanged.connect(update_opacity)
        
        main_layout.addLayout(row)
        
        # Set content area
        self.set_content_widget(content_widget)

    def _create_mode_tab(self, mode):
        """Create a tab page for a specific display mode."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # We need settings for both Category and Package for this mode
        # Scroll Area if needed
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(20)
        c_layout.setContentsMargins(5, 5, 5, 5)
        
        # --- Category Section ---
        c_layout.addWidget(QLabel(_("<b>📁 Categories</b>")))
        c_cat = QFrame()
        c_cat.setStyleSheet("background: #383838; border-radius: 6px; padding: 5px;")
        l_cat = QVBoxLayout(c_cat)
        
        self._add_controls(l_cat, 'category', mode)
        c_layout.addWidget(c_cat)
        
        # --- Package Section ---
        c_layout.addWidget(QLabel(_("<b>📦 Packages</b>")))
        c_pkg = QFrame()
        c_pkg.setStyleSheet("background: #383838; border-radius: 6px; padding: 5px;")
        l_pkg = QVBoxLayout(c_pkg)
        
        self._add_controls(l_pkg, 'package', mode)
        c_layout.addWidget(c_pkg)
        
        c_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return page

    def _add_controls(self, layout, type_, mode):
        """Add sliders and checks for a specific type and mode."""
        prefix = 'cat' if type_ == 'category' else 'pkg'
        
        # 1. Scale
        layout.addLayout(self._create_scale_row(_("Scale"), prefix, type_, mode))
        
        # 2. Dimensions (Width/Height)
        # Only meaningful if not text list? Text list has fixed height usually but maybe width matters.
        if mode != 'text_list':
             layout.addLayout(self._create_slider_row(_("Width"), f'{prefix}_{mode}_card_w', type_, mode, 'card_w', 100, 400))
             layout.addLayout(self._create_slider_row(_("Height"), f'{prefix}_{mode}_card_h', type_, mode, 'card_h', 50, 400))
             layout.addLayout(self._create_slider_row(_("Img W"), f'{prefix}_{mode}_img_w', type_, mode, 'img_w', 50, 300))
             layout.addLayout(self._create_slider_row(_("Img H"), f'{prefix}_{mode}_img_h', type_, mode, 'img_h', 50, 300))
        
        # 3. Toggles
        layout.addLayout(self._create_check_row(_("Show Link Icon"), f'{prefix}_{mode}_show_link', type_, mode, 'show_link'))
        layout.addLayout(self._create_check_row(_("Show Deploy Button"), f'{prefix}_{mode}_show_deploy', type_, mode, 'show_deploy'))

    def _create_slider_row(self, label, attr, type_, mode, param, min_v, max_v):
        row = QHBoxLayout()
        row.setContentsMargins(0,0,0,0)
        
        lbl = QLabel(label)
        lbl.setFixedWidth(70)
        row.addWidget(lbl)
        
        val = int(self.settings.get(attr, 100)) # Default fallback
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(val)
        row.addWidget(slider)
        
        spin = StyledSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(val)
        spin.setFixedWidth(50)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spin.setStyleSheet("background: #222; border: 1px solid #555;")
        row.addWidget(spin)
        
        def update(v):
            slider.blockSignals(True)
            spin.blockSignals(True)
            slider.setValue(v)
            spin.setValue(v)
            slider.blockSignals(False)
            spin.blockSignals(False)
            self.paramChanged.emit(type_, mode, param, v)
            
        slider.valueChanged.connect(update)
        spin.valueChanged.connect(update)
        
        return row

    def _create_scale_row(self, label, prefix, type_, mode):
        attr = f'{prefix}_{mode}_scale'
        row = QHBoxLayout()
        row.setContentsMargins(0,0,0,0)
        
        lbl = QLabel(label)
        lbl.setFixedWidth(70)
        row.addWidget(lbl)
        
        val = int(self.settings.get(attr, 1.0) * 100)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(50, 200) # 50% to 200%
        slider.setValue(val)
        row.addWidget(slider)
        
        spin = StyledSpinBox()
        spin.setRange(50, 200)
        spin.setValue(val)
        spin.setSuffix("%")
        spin.setFixedWidth(50)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spin.setStyleSheet("background: #222; border: 1px solid #555;")
        row.addWidget(spin)
        
        def update(v):
            slider.blockSignals(True)
            spin.blockSignals(True)
            slider.setValue(v)
            spin.setValue(v)
            slider.blockSignals(False)
            spin.blockSignals(False)
            self.scaleChanged.emit(type_, mode, v / 100.0)

        slider.valueChanged.connect(update)
        spin.valueChanged.connect(update)
        
        return row

    def _create_check_row(self, label, attr, type_, mode, param):
        from src.ui.slide_button import SlideButton
        row = QHBoxLayout()
        
        check = SlideButton()
        val = bool(self.settings.get(attr, True))
        check.setChecked(val)
        
        lbl = QLabel(label)
        
        check.clicked.connect(lambda: self.checkChanged.emit(type_, mode, param, check.isChecked()))
        
        row.addWidget(check)
        row.addWidget(lbl)
        row.addStretch()
        return row

    def closeEvent(self, event):
        """Emit closed signal when window is closed."""
        self.closed.emit()
        super().closeEvent(event)
