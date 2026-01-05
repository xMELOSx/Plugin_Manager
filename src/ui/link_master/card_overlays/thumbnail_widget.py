from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QSize, QThreadPool
from PyQt6.QtGui import QPixmap
from src.core.lang_manager import _
from ..item_card_utils import AsyncScaler


class ThumbnailWidget(QLabel):
    """Self-contained thumbnail component with async loading and resize handling."""
    
    _pool = QThreadPool.globalInstance()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)
        self.setText(_("No Image"))
        self.setStyleSheet("color: #777;")
        
        self._original_pixmap = None
        self._current_request_id = 0
        self._target_size = QSize(140, 120)
        self._last_scaled_size = QSize(0, 0)
    
    def setTargetSize(self, size: QSize):
        """Set the target display size for the thumbnail."""
        if self._target_size == size:
            return
        self._target_size = size
        if self._original_pixmap:
            self._requestScale()
    
    def setImage(self, pixmap: QPixmap):
        """Set the source image and trigger async scaling."""
        if pixmap and not pixmap.isNull():
            # Optimization: If the same pixmap and size, skip scaling
            if self._original_pixmap is pixmap and self._last_scaled_size == self._target_size:
                return
            self._original_pixmap = pixmap
            # Reset cached size to force re-scale when image changes
            self._last_scaled_size = QSize(0, 0)
            self._requestScale()
        else:
            self._original_pixmap = None
            self._last_scaled_size = QSize(0, 0)
            self.setPixmap(QPixmap())
            self.setText(_("No Image"))
    
    def loadFromPath(self, path: str, loader=None, size: QSize = None):
        """Load image from path using provided loader."""
        if size:
            self._target_size = size
        if path and loader:
            self.setText(_("Loading..."))
            loader.load_image(path, QSize(256, 256), self._onImageLoaded)
        else:
            self.setText(_("No Image"))
    
    def _onImageLoaded(self, pixmap: QPixmap):
        """Callback when image is loaded by external loader."""
        self.setImage(pixmap)
    
    def _requestScale(self):
        """Request async scaling of the current pixmap."""
        if not self._original_pixmap or self._original_pixmap.isNull():
            return
            
        # Optimization: Skip if already scaled to the requested size
        if self._last_scaled_size == self._target_size:
            return
        
        self._current_request_id += 1
        scaler = AsyncScaler(self._original_pixmap, self._target_size, self._current_request_id)
        scaler.signals.finished.connect(self._onScaleFinished)
        ThumbnailWidget._pool.start(scaler)
    
    def _onScaleFinished(self, pixmap: QPixmap, request_id: int):
        """Handle completion of async scaling."""
        if request_id != self._current_request_id:
            return  # Stale request
        
        if pixmap and not pixmap.isNull():
            self.setPixmap(pixmap)
            self._last_scaled_size = self._target_size
            self.setText("")
            # Force UI repaint - needed when cards are reused from pool
            self.update()
            if self.parent():
                self.parent().update()
        else:
            self.setText(_("No Image"))
    
    def clear(self):
        """Clear the thumbnail."""
        self._original_pixmap = None
        self.setPixmap(QPixmap())
        self.setText(_("No Image"))
