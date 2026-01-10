"""
Toast Notification Widget - Reusable floating notification component.

Usage:
    from src.ui.toast import Toast
    
    # Create once
    self._toast = Toast(parent=self)
    
    # Show with default style
    self._toast.show_message("Saved!")
    
    # Show with custom style
    self._toast.show_message("Error!", color="#e74c3c", duration=3000)
"""

from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QAbstractAnimation


class Toast(QLabel):
    """Floating notification label with configurable style and position."""
    
    # Preset colors for common toast types
    COLORS = {
        'info': '#5dade2',     # Blue
        'success': '#2ecc71', # Green
        'warning': '#f39c12', # Orange
        'error': '#e74c3c',   # Red
    }
    
    def __init__(self, parent, text="", duration=2000, y_offset=60):
        super().__init__(text, parent)
        self._duration = duration
        self._y_offset = y_offset  # Vertical position from parent top
        self._color = self.COLORS['info']
        
        # Initialize opacity effect once
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # Initialize animation once
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        
        # Timer for auto-hide
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.fade_out)
        
        self._apply_style()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adjustSize()
        self.hide()

    @staticmethod
    def show_toast(parent, message, preset="info", duration=2000, y_offset=None):
        """Helper to show a toast on a parent without needing an instance.
        Automatically finds the main window to prevent clipping in small dialogs.
        """
        import logging
        logging.debug(f"[Toast] show_toast called with parent={parent}, message={message}, preset={preset}")
        if not parent: 
            logging.debug("[Toast] show_toast failed: No parent provided")
            return
        
        # Redirect to Main Window if possible
        from PyQt6.QtWidgets import QMainWindow
        target = parent
        curr = parent
        while curr:
            if isinstance(curr, QMainWindow):
                target = curr
                break
            curr = curr.parentWidget()
            
        # Try to find existing toast instance on target
        toast = getattr(target, "_toast_instance", None)
        if not toast or toast.parent() != target:
            # Create if missing or target changed
            toast = Toast(target, y_offset=(y_offset if y_offset is not None else 60))
            # Set to target as the standard instance
            try:
                setattr(target, "_toast_instance", toast)
            except: pass
            
        if y_offset is not None:
            toast.set_y_offset(y_offset)
            
        logging.debug(f"[Toast] show_message being called on instance {toast} for target {target}")
        toast.show_message(message, preset=preset, duration=duration)
        return toast

    def _apply_style(self, color=None):
        """Apply or update the toast styling."""
        c = color or self._color
        self.setStyleSheet(f"""
            background: rgba(40, 40, 40, 230);
            color: {c};
            border: 1px solid {c};
            border-radius: 15px;
            padding: 8px 20px;
            font-weight: bold;
            font-size: 11pt;
        """)

    def set_y_offset(self, offset):
        """Set the vertical position offset from parent top."""
        self._y_offset = offset

    def show_message(self, text=None, color=None, duration=None, preset=None):
        """
        Display the toast notification.
        """
        # Stop everything first
        self._hide_timer.stop()
        if self.anim.state() == QAbstractAnimation.State.Running:
            self.anim.stop()
            
        # Ensure 'finished' signal is disconnected to prevent hide() call
        try:
            self.anim.finished.disconnect(self.hide)
        except TypeError:
            pass 

        if text:
            self.setText(text)
        
        # Apply color
        actual_preset = preset or "info"
        if actual_preset and actual_preset in self.COLORS:
            self._color = self.COLORS[actual_preset]
        elif color:
            self._color = color
        
        self._apply_style(self._color)
        self.adjustSize()
        
        # Override duration if specified
        show_duration = duration or self._duration
        
        # Position at top center with y_offset
        parent = self.parentWidget()
        import logging
        logging.debug(f"[Toast] show_message start: text='{text}', parent_w={parent.width() if parent else 'None'}")

        if parent:
            x = (parent.width() - self.width()) // 2
            y = self._y_offset
            self.move(x, y)
        
        self.show()
        self.raise_()
        logging.debug(f"[Toast] show_message visible: pos=({self.x()}, {self.y()}), parent={parent}")
        
        # Start Fade In
        self.opacity_effect.setOpacity(0.0)
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        
        # Start hide timer
        self._hide_timer.start(show_duration)

    def fade_out(self):
        """Animate fade out and hide."""
        # Stop any running animation (e.g., fade in)
        if self.anim.state() == QAbstractAnimation.State.Running:
            self.anim.stop()
            
        try:
            self.anim.finished.disconnect(self.hide)
        except TypeError:
            pass

        self.anim.setDuration(500)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.hide)
        self.anim.start()
