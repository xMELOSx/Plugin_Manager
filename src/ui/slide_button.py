from PyQt6.QtWidgets import QAbstractButton
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, pyqtProperty, pyqtSignal, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

class SlideButton(QAbstractButton):
    """
    Moderate, animated slide toggle button (Toggle Switch).
    """
    def __init__(self, parent=None, active_color="#2ecc71", bg_color="#555"):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(40, 20)
        
        self._active_color = QColor(active_color)
        self._bg_color = QColor(bg_color)
        self._circle_color = QColor("#ffffff")
        
        self._circle_position = 3 if not self.isChecked() else 23
        self._animation = QPropertyAnimation(self, b"circle_position", self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    @pyqtProperty(int)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def setChecked(self, checked):
        super().setChecked(checked)
        self._circle_position = 23 if checked else 3
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Background
        p.setPen(Qt.PenStyle.NoPen)
        # Ensure position matches state if not animating
        if self._animation.state() == QPropertyAnimation.State.Stopped:
            self._circle_position = 23 if self.isChecked() else 3

        if not self.isChecked():
            p.setBrush(QBrush(self._bg_color))
        else:
            p.setBrush(QBrush(self._active_color))
            
        p.drawRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        
        # Draw Circle
        p.setBrush(QBrush(self._circle_color))
        p.drawEllipse(self._circle_position, 3, 14, 14)
        p.end()

    def nextCheckState(self):
        super().nextCheckState()
        start = self._circle_position
        end = 23 if self.isChecked() else 3
        
        self._animation.stop()
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()
