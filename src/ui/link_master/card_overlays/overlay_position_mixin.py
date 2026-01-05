from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QEvent


class OverlayPositionMixin:
    """Mixin to hold position settings for overlays.
    
    The actual positioning is now handled common parent logic (item_card_overlays.py)
    to avoid the overhead of hundreds of event filters.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._position_mode = 'top_right'  # top_left, top_right, bottom_left, bottom_right
        self._margin = 6
    
    def setPositionMode(self, mode: str, margin: int = 6):
        """Set the position mode and margin."""
        self._position_mode = mode
        self._margin = margin
    
    def update_position_manually(self, pw: int, ph: int):
        """Update position based on card size. Called by parent."""
        w, h = self.width(), self.height()
        m = self._margin
        
        if self._position_mode == 'top_left':
            x, y = m, m
        elif self._position_mode == 'top_right':
            x, y = pw - w - m, m
        elif self._position_mode == 'bottom_left':
            x, y = m, ph - h - m
        elif self._position_mode == 'bottom_right':
            x, y = pw - w - m, ph - h - m
        else:
            x, y = m, m
        
        self.move(x, y)
