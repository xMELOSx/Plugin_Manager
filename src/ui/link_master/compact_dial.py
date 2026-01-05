from PyQt6.QtWidgets import QWidget, QLineEdit, QHBoxLayout, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QWheelEvent

class CompactDial(QWidget):
    """
    A compact numeric input that shows neighbors like a physical dial.
    - Vertical wheel scrolling per digit.
    - Click to type directly.
    - Designed to be reusable with configurable digits/size.
    """
    valueChanged = pyqtSignal(int)
    
    def __init__(self, parent=None, value=0, min_val=0, max_val=999, digits=3, show_arrows=True):
        super().__init__(parent)
        self._value = value
        self._min_val = min_val
        self._max_val = max_val
        self._digits = digits
        self._show_arrows = show_arrows
        
        # UI Metrics (Match PreviewWindow dial size)
        self._digit_w = 15
        self._digit_h = 22
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        
        # Main Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        
        # Up Button
        self.up_btn = QPushButton("▲", self)
        self.up_btn.setFixedSize(18, self._digit_h + 4)
        self.up_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.up_btn.setStyleSheet("QPushButton { background: #444; color: #ccc; border: 1px solid #555; font-size: 10px; padding: 0; min-width: 18px; max-width: 18px; } QPushButton:hover { background: #555; }")
        self.up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.up_btn.clicked.connect(self.stepUp)
        self.layout.addWidget(self.up_btn)
        
        # Dial Area (The drawing part)
        self.dial_widget = QWidget(self)
        self.dial_widget.setFixedSize(self._digit_w * self._digits + 4, self._digit_h + 4)
        self.dial_widget.paintEvent = self._paint_dial
        self.dial_widget.mousePressEvent = self._on_dial_pressed
        self.layout.addWidget(self.dial_widget)
        
        # Down Button
        self.down_btn = QPushButton("▼", self)
        self.down_btn.setFixedSize(18, self._digit_h + 4)
        self.down_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.down_btn.setStyleSheet("QPushButton { background: #444; color: #ccc; border: 1px solid #555; font-size: 10px; padding: 0; min-width: 18px; max-width: 18px; } QPushButton:hover { background: #555; }")
        self.down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.down_btn.clicked.connect(self.stepDown)
        self.layout.addWidget(self.down_btn)
        
        # Inline editor for direct input (overlay on dial_widget)
        self.editor = QLineEdit(self.dial_widget)
        self.editor.setFrame(False)
        self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editor.setStyleSheet("background: #3b3b3b; color: #fff; border: 1px solid #3498db;")
        self.editor.hide()
        self.editor.editingFinished.connect(self._on_editor_finished)
        
        self.toggleArrows(show_arrows)
        self._update_editor_geometry()
        
    def _update_editor_geometry(self):
        self.editor.setGeometry(0, 0, self.dial_widget.width(), self.dial_widget.height())

    def toggleArrows(self, show):
        self._show_arrows = show
        self.up_btn.setVisible(show)
        self.down_btn.setVisible(show)
        # Adjust total width
        w = self.dial_widget.width()
        if show:
            w += self.up_btn.width() + self.down_btn.width() + 4
        h = self._digit_h + 4
        self.setFixedSize(w, h)
        self.setMinimumSize(w, h)  # Prevent layout compression

    def value(self):
        return self._value

    def setValue(self, val):
        val = max(self._min_val, min(self._max_val, val))
        if self._value != val:
            self._value = val
            self.valueChanged.emit(val)
            self.update()

    def stepUp(self):
        self.setValue(self._value + 1)

    def stepDown(self):
        self.setValue(self._value - 1)

    def _on_editor_finished(self):
        try:
            val = int(self.editor.text())
            self.setValue(val)
        except:
            pass
        self.editor.hide()
        self.setFocus()

    def _on_dial_pressed(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.editor.setText(str(self._value))
            self.editor.show()
            self.editor.setFocus()
            self.editor.selectAll()

    def wheelEvent(self, event: QWheelEvent):
        # Determine which digit we are over
        # Calculate local X relative to dial_widget
        local_pos = self.dial_widget.mapFrom(self, event.position().toPoint())
        x = local_pos.x()
        
        if 0 <= x <= self.dial_widget.width():
            digit_idx = int((self.dial_widget.width() - x) / self._digit_w)
            if digit_idx < 0: digit_idx = 0
            if digit_idx >= self._digits: digit_idx = self._digits - 1
            
            delta = 1 if event.angleDelta().y() > 0 else -1
            step = 10**digit_idx
            self.setValue(self._value + (delta * step))
            event.accept()
        else:
            super().wheelEvent(event)

    def _paint_dial(self, event):
        painter = QPainter(self.dial_widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.dial_widget.rect()
        painter.fillRect(rect, QColor("#3b3b3b"))
        
        if self.editor.isVisible():
            return
            
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        
        val_str = str(self._value).zfill(self._digits)
        if len(val_str) > self._digits:
            val_str = val_str[-self._digits:]
            
        for i in range(self._digits):
            x = (self._digits - 1 - i) * self._digit_w + 2
            digit = int(val_str[-(i+1)])
            
            # Draw Center (Neighbors removed for clarity)
            painter.setPen(QColor("#fff"))
            painter.drawText(QRect(int(x), 0, int(self._digit_w), int(self._digit_h)), 
                             Qt.AlignmentFlag.AlignCenter, str(digit))
            
        # Subtle border
        painter.setPen(QPen(QColor("#555"), 1))
        painter.drawRect(rect.adjusted(0,0,-1,-1))

    def paintEvent(self, event):
        # Container doesn't need custom painting
        pass

    def resizeEvent(self, event):
        self._update_editor_geometry()
        super().resizeEvent(event)
