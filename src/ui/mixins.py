""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QScreen
from PyQt6.QtCore import QRect

class SmartPositioningMixin:
    """Mixin to provide smart positioning logic relative to a target window."""
    
    def smart_position(self, target_rect: QRect, screen: QScreen = None):
        """
        Attempts to position self around the target_rect.
        Order: Right -> Left -> Bottom -> Top
        Fallback: Offset from target.
        """
        if not screen:
            screen = QApplication.primaryScreen()
        
        screen_geo = screen.availableGeometry()
        my_geo = self.frameGeometry()
        width = my_geo.width()
        height = my_geo.height()
        gap = 10 

        # 1. Try Right
        x = target_rect.right() + gap
        y = target_rect.top()
        if x + width <= screen_geo.right():
            self.move(x, y)
            return

        # 2. Try Left
        x = target_rect.left() - width - gap
        if x >= screen_geo.left():
            self.move(x, y)
            return

        # 3. Try Bottom
        x = target_rect.left()
        y = target_rect.bottom() + gap
        if y + height <= screen_geo.bottom():
            self.move(x, y)
            return

        # 4. Try Top
        y = target_rect.top() - height - gap
        if y >= screen_geo.top():
            self.move(x, y)
            return

        # 5. Fallback: Offset
        title_bar_height = 30 # Approx
        self.move(target_rect.left(), target_rect.top() + title_bar_height + gap)
