from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QPushButton, QLabel, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QBrush, QPen, QPixmap, QImage

from src.ui.frameless_window import FramelessDialog
from src.ui.common_widgets import StyledSpinBox, ProtectedLineEdit
from src.core.lang_manager import _

class ColorMapWidget(QWidget):
    """
    A 2D color selection widget (Sat/Val or similar).
    For simplicity, we'll use a standard Hue-Saturation/Value style:
    - Main Area: Saturation (x) vs Value (y) using current Hue.
    - Side Bar: Hue Slider.
    """
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(256, 256)
        self.hue = 0.0 # 0-1.0
        self.sat = 0.0 # 0-1.0
        self.val = 1.0 # 0-1.0
        self.dragging = False
        self._cache_pixmap = None

    def set_color(self, h, s, v):
        self.hue = h
        self.sat = s
        self.val = v
        self._update_pixmap()
        self.update()

    def set_hue(self, h):
        self.hue = h
        self._update_pixmap()
        self.update()

    def _update_pixmap(self):
        # Generate Sat/Val gradient for current hue
        img = QImage(256, 256, QImage.Format.Format_RGB32)
        
        # This pixel manipulation might be slow in Python if not optimized,
        # but for 256x256 it's acceptable for a dialog. 
        # Actually, using QLinearGradient is faster.
        self._cache_pixmap = QPixmap(256, 256)
        self._cache_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(self._cache_pixmap)
        
        # 1. Base Hue Color
        base_color = QColor.fromHsvF(self.hue, 1.0, 1.0)
        
        # 2. Horizontal Saturation Gradient (White -> Color)
        g_sat = QLinearGradient(0, 0, 256, 0)
        g_sat.setColorAt(0, QColor(255, 255, 255))
        g_sat.setColorAt(1, base_color)
        painter.fillRect(0, 0, 256, 256, g_sat)
        
        # 3. Vertical Value Gradient (Transparent -> Black)
        g_val = QLinearGradient(0, 0, 0, 256)
        g_val.setColorAt(0, QColor(0, 0, 0, 0)) # Transparent
        g_val.setColorAt(1, QColor(0, 0, 0, 255)) # Black
        painter.fillRect(0, 0, 256, 256, g_val)
        
        painter.end()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._cache_pixmap:
            painter.drawPixmap(0, 0, self._cache_pixmap)
        
        # Draw reticle
        x = int(self.sat * 256)
        y = int((1.0 - self.val) * 256)
        
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawEllipse(QPoint(x, y), 5, 5)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(QPoint(x, y), 4, 4)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self._handle_mouse(event.pos())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._handle_mouse(event.pos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def _handle_mouse(self, pos):
        x = max(0, min(256, pos.x()))
        y = max(0, min(256, pos.y()))
        
        self.sat = x / 256.0
        self.val = 1.0 - (y / 256.0)
        
        new_color = QColor.fromHsvF(self.hue, self.sat, self.val)
        self.colorChanged.emit(new_color)
        self.update()

class HueSlider(QWidget):
    colorChanged = pyqtSignal(float) # Emits hue 0-1.0
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 256)
        self.hue = 0.0
        self.dragging = False
        
        # Generate Hue Gradient
        self.bg_pixmap = QPixmap(24, 256)
        painter = QPainter(self.bg_pixmap)
        gradient = QLinearGradient(0, 0, 0, 256)
        for i in range(7):
            gradient.setColorAt(i/6.0, QColor.fromHsvF(i/6.0 if i<6 else 0.999, 1.0, 1.0))
        painter.fillRect(0, 0, 24, 256, gradient)
        painter.end()

    def set_hue(self, h):
        self.hue = h
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.bg_pixmap)
        
        # Draw handle
        y = int(self.hue * 256)
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawRect(0, y-2, 24, 4)

    def mousePressEvent(self, event):
        self.dragging = True
        self._handle_mouse(event.pos())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._handle_mouse(event.pos())
            
    def mouseReleaseEvent(self, event):
        self.dragging = False

    def _handle_mouse(self, pos):
        y = max(0, min(256, pos.y()))
        self.hue = y / 256.0
        self.colorChanged.emit(self.hue)
        self.update()

class CustomColorDialog(FramelessDialog):
    def __init__(self, initial_color=QColor("#ffffff"), parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Select Color"))
        self.set_default_icon()
        self.resize(550, 400)
        self.set_resizable(False)
        
        self.current_color = QColor(initial_color)
        if not self.current_color.isValid():
            self.current_color = QColor("#ffffff")
            
        self._init_ui()
        self._update_ui_from_color(self.current_color)

    def _init_ui(self):
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Left: Color Map + Hue Slider
        map_layout = QHBoxLayout()
        self.color_map = ColorMapWidget()
        self.color_map.colorChanged.connect(self._on_map_changed)
        
        self.hue_slider = HueSlider()
        self.hue_slider.colorChanged.connect(self._on_hue_changed)
        
        map_layout.addWidget(self.color_map)
        map_layout.addWidget(self.hue_slider)
        
        left_container = QVBoxLayout()
        left_container.addLayout(map_layout)
        
        # Palette (Simple grid of buttons below map)
        palette_grid = QGridLayout()
        palette_grid.setSpacing(5)
        colors = [
            "#ffffff", "#c0c0c0", "#808080", "#000000",
            "#ff0000", "#800000", "#ffff00", "#808000",
            "#00ff00", "#008000", "#00ffff", "#008080",
            "#0000ff", "#000080", "#ff00ff", "#800080"
        ]
        for i, c in enumerate(colors):
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(f"background-color: {c}; border: 1px solid #555;")
            btn.clicked.connect(lambda _, col=c: self._set_color_hex(col))
            palette_grid.addWidget(btn, i // 8, i % 8)
            
        left_container.addLayout(palette_grid)
        layout.addLayout(left_container)
        
        # Right: Inputs and Preview
        right_layout = QVBoxLayout()
        
        # Preview
        self.preview_box = QLabel()
        self.preview_box.setFixedSize(120, 80)
        self.preview_box.setStyleSheet("border: 1px solid #888; background-color: white;")
        right_layout.addWidget(self.preview_box)
        
        right_layout.addSpacing(20)
        
        # RGB Inputs
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        
        grid.addWidget(QLabel("R:"), 0, 0)
        self.spin_r = StyledSpinBox()
        self.spin_r.setRange(0, 255)
        self.spin_r.valueChanged.connect(self._on_rgb_changed)
        grid.addWidget(self.spin_r, 0, 1)
        
        grid.addWidget(QLabel("G:"), 1, 0)
        self.spin_g = StyledSpinBox()
        self.spin_g.setRange(0, 255)
        self.spin_g.valueChanged.connect(self._on_rgb_changed)
        grid.addWidget(self.spin_g, 1, 1)
        
        grid.addWidget(QLabel("B:"), 2, 0)
        self.spin_b = StyledSpinBox()
        self.spin_b.setRange(0, 255)
        self.spin_b.valueChanged.connect(self._on_rgb_changed)
        grid.addWidget(self.spin_b, 2, 1)
        
        # Hex Input
        grid.addWidget(QLabel("Hex:"), 3, 0)
        self.hex_input = ProtectedLineEdit()
        self.hex_input.textChanged.connect(self._on_hex_changed)
        grid.addWidget(self.hex_input, 3, 1)
        
        right_layout.addLayout(grid)
        right_layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 6px 20px; font-weight: bold;")
        
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        
        right_layout.addLayout(btn_layout)
        
        layout.addLayout(right_layout)
        
        self.set_content_widget(root)

    def _update_ui_from_color(self, color):
        # Prevent loops
        self.spin_r.blockSignals(True)
        self.spin_g.blockSignals(True)
        self.spin_b.blockSignals(True)
        self.hex_input.blockSignals(True)
        self.color_map.blockSignals(True)
        self.hue_slider.blockSignals(True)
        
        # Inputs
        self.spin_r.setValue(color.red())
        self.spin_g.setValue(color.green())
        self.spin_b.setValue(color.blue())
        self.hex_input.setText(color.name())
        
        # Map/Slider
        h, s, v, _ = color.getHsvF()
        if s == 0: h = self.color_map.hue # Preserve hue if desaturated
        self.color_map.set_color(h, s, v)
        self.hue_slider.set_hue(h)
        
        # Preview
        # Use simple style since it's a label
        self.preview_box.setStyleSheet(f"border: 1px solid #888; background-color: {color.name()};")
        
        self.spin_r.blockSignals(False)
        self.spin_g.blockSignals(False)
        self.spin_b.blockSignals(False)
        self.hex_input.blockSignals(False)
        self.color_map.blockSignals(False)
        self.hue_slider.blockSignals(False)
        
        self.current_color = color

    def _on_rgb_changed(self):
        r = self.spin_r.value()
        g = self.spin_g.value()
        b = self.spin_b.value()
        self._update_ui_from_color(QColor(r, g, b))

    def _on_hex_changed(self, text):
        if len(text) >= 4 and QColor.isValidColor(text):
            self._update_ui_from_color(QColor(text))

    def _on_map_changed(self, color):
        self._update_ui_from_color(color)

    def _on_hue_changed(self, hue):
        # Update map's hue while keeping saturation/value
        h, s, v, _ = self.current_color.getHsvF()
        # Note: getHsvF returns h=-1 for grayscale, handle that
        if h < 0: h = self.color_map.hue
        
        new_color = QColor.fromHsvF(hue, s, v)
        self._update_ui_from_color(new_color)

    def _set_color_hex(self, hex_code):
        self._update_ui_from_color(QColor(hex_code))

    def currentColor(self):
        return self.current_color

