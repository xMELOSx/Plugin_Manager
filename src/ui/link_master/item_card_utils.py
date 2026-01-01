from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, Qt

class ScaleSignals(QObject):
    finished = pyqtSignal(object, int) # pixmap, request_id (object to avoid direct QPixmap import overhead here if needed, but usually QPixmap is fine)

class AsyncScaler(QRunnable):
    """Offloads heavy QPixmap.scaled from the main thread."""
    def __init__(self, pixmap, size, request_id):
        super().__init__()
        self.pixmap = pixmap
        self.size = size
        self.request_id = request_id
        self.signals = ScaleSignals()

    def run(self):
        if self.pixmap.isNull(): return
        # Perform high quality scaling on background thread
        scaled = self.pixmap.scaled(
            self.size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.signals.finished.emit(scaled, self.request_id)
