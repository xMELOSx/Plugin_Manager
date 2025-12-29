""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage
import os

class ImageLoadWorker(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(QPixmap)
        
    def __init__(self, path: str, size: QSize):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = self.Signals()

    def run(self):
        try:
            image = QImage(self.path)
            if not image.isNull():
                # Scale smoothly
                scaled = image.scaled(self.size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                pixmap = QPixmap.fromImage(scaled)
                self.signals.finished.emit(pixmap)
            else:
                self.signals.finished.emit(QPixmap()) # Empty on fail
        except Exception:
            self.signals.finished.emit(QPixmap())

class ImageLoader(QObject):
    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4) # Limit threads

    def load_image(self, path: str, target_size: QSize, callback):
        """
        Asynchronously loads an image and calls callback(QPixmap) when done.
        """
        if not path or not os.path.exists(path):
            return

        worker = ImageLoadWorker(path, target_size)
        # Connect signal. Note: direct connection might be thread-unsafe if not careful, 
        # but pyqtSignal usually handles thread boundary to Main Thread slot automatically.
        worker.signals.finished.connect(callback)
        self.thread_pool.start(worker)
