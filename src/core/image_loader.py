""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage
from collections import OrderedDict
import os
import time
import logging

class ImageLoadWorker(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(QPixmap, str)  # pixmap, original_path for validation
        
    def __init__(self, path: str, size: QSize):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = self.Signals()
        self._cancelled = False

    def cancel(self):
        """Mark this worker as cancelled to prevent callback execution."""
        self._cancelled = True

    def run(self):
        if self._cancelled:
            return
        try:
            image = QImage(self.path)
            if self._cancelled:
                return
            if not image.isNull():
                # Scale smoothly
                scaled = image.scaled(self.size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                pixmap = QPixmap.fromImage(scaled)
                if not self._cancelled:
                    self.signals.finished.emit(pixmap, self.path)
            else:
                if not self._cancelled:
                    self.signals.finished.emit(QPixmap(), self.path) # Empty on fail
        except Exception:
            if not self._cancelled:
                self.signals.finished.emit(QPixmap(), self.path)

class ImageLoader(QObject):
    # Class-level memory cache (LRU-style using OrderedDict)
    _cache = OrderedDict()
    _cache_max_size = 300  # Keep up to 300 images in memory
    
    # Phase 33: Batch counter for staggering cache hit callbacks
    _batch_delay_counter = 0
    _BATCH_SIZE = 5  # Process 5 images per event loop cycle
    
    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(8)  # Increased from 4 to 8 for faster loading
        self._pending_workers = {}  # {path: worker} for cancellation

    def load_image(self, path: str, target_size: QSize, callback, request_validator=None):
        """
        Asynchronously loads an image and calls callback(QPixmap) when done.
        
        Args:
            path: Image path to load
            target_size: Target size for scaling
            callback: Function to call with the loaded QPixmap
            request_validator: Optional function that returns True if the request is still valid.
                              Used to prevent image mismatch when cards are reused from pool.
        """
        if not path or not os.path.exists(path):
            return

        # Cache hit - use cached image, but defer callback to allow UI updates
        if path in ImageLoader._cache:
            # Move to end (most recently used)
            ImageLoader._cache.move_to_end(path)
            logging.getLogger("ImageLoader").info(f"[CacheHit] {os.path.basename(path)}")
            
            # Phase 33: Stagger callbacks across multiple event loop cycles
            # Every BATCH_SIZE images, add 1ms delay to allow UI breathing room
            from PyQt6.QtCore import QTimer
            cached_pixmap = ImageLoader._cache[path]
            basename = os.path.basename(path)
            
            # Calculate delay: 0ms for first batch, 1ms for second, etc.
            delay = ImageLoader._batch_delay_counter // ImageLoader._BATCH_SIZE
            ImageLoader._batch_delay_counter += 1
            
            # Reset counter periodically to avoid unbounded growth
            if ImageLoader._batch_delay_counter > 1000:
                ImageLoader._batch_delay_counter = 0
            
            def deferred_callback():
                t_start = time.perf_counter()
                callback(cached_pixmap)
                t_end = time.perf_counter()
                if (t_end - t_start) > 0.01:  # Log if > 10ms
                    logging.getLogger("ImageLoader").warning(f"[SlowCacheCallback] {basename}: {(t_end-t_start)*1000:.1f}ms")
            
            QTimer.singleShot(delay, deferred_callback)
            return

        logging.getLogger("ImageLoader").debug(f"[CacheMiss] Loading: {os.path.basename(path)}")
        # Cache miss - load asynchronously
        worker = ImageLoadWorker(path, target_size)
        
        def on_finished(pixmap, loaded_path):
            t_cb_start = time.perf_counter()
            # Remove from pending
            self._pending_workers.pop(loaded_path, None)
            
            # Validate request is still valid (card hasn't been reused for different item)
            if request_validator and not request_validator():
                logging.getLogger("ImageLoader").debug(f"[Stale] Ignoring: {os.path.basename(loaded_path)}")
                return  # Request is stale, don't set image
            
            # Add to cache
            if not pixmap.isNull():
                # Evict oldest if cache is full
                while len(ImageLoader._cache) >= ImageLoader._cache_max_size:
                    ImageLoader._cache.popitem(last=False)
                ImageLoader._cache[loaded_path] = pixmap
            
            callback(pixmap)
            t_cb_end = time.perf_counter()
            if (t_cb_end - t_cb_start) > 0.01:  # Log if callback takes > 10ms
                logging.getLogger("ImageLoader").warning(f"[SlowCallback] {os.path.basename(loaded_path)}: {(t_cb_end-t_cb_start)*1000:.1f}ms")
        
        worker.signals.finished.connect(on_finished)
        self._pending_workers[path] = worker
        self.thread_pool.start(worker)

    def cancel_pending(self):
        """Cancel all pending image load requests (call when navigating to new folder)."""
        for path, worker in list(self._pending_workers.items()):
            worker.cancel()
        self._pending_workers.clear()

    @classmethod
    def clear_cache(cls):
        """Clear the image cache (e.g., when app switches)."""
        cls._cache.clear()

