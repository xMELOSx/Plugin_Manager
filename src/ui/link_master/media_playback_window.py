"""
Dedicated Media Playback Window
Provides a clean, player-focused view for images and videos.
"""
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QSlider, QSizePolicy, QStackedWidget,
                             QProgressBar, QGridLayout)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon, QKeyEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

class MediaPlaybackWindow(QWidget):
    """A standalone window for media playback."""
    
    def __init__(self, path: str, parent=None):
        super().__init__(None) # Standalone
        self.path = path
        self.setWindowTitle(f"Playback - {os.path.basename(path)}")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background-color: #000; color: #fff;")
        
        self._init_ui()
        self._load_content()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.stack = QStackedWidget()
        
        # Image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.image_label)
        
        # Video
        self.video_container = QWidget()
        v_layout = QVBoxLayout(self.video_container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        
        self.video_widget = QVideoWidget()
        v_layout.addWidget(self.video_widget)
        
        # Controls (Auto-hide could be cool, but keeping it simple for now)
        self.controls = QWidget()
        self.controls.setFixedHeight(50)
        self.controls.setStyleSheet("background-color: rgba(30,30,30, 200);")
        c_layout = QHBoxLayout(self.controls)
        
        self.play_btn = QPushButton("⏯")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.clicked.connect(self._toggle_playback)
        
        # Seekbar with buffering
        self.buffer_bar = QProgressBar()
        self.buffer_bar.setRange(0, 100)
        self.buffer_bar.setValue(0)
        self.buffer_bar.setTextVisible(False)
        self.buffer_bar.setFixedHeight(6)
        self.buffer_bar.setStyleSheet("""
            QProgressBar { background-color: #333; border: none; border-radius: 3px; }
            QProgressBar::chunk { background-color: #555; border-radius: 3px; }
        """)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.sliderMoved.connect(self._on_seek)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 6px; background: transparent; }
            QSlider::handle:horizontal { background: #e67e22; border-radius: 7px; width: 14px; height: 14px; margin: -4px 0; }
        """)
        
        seekbar_container = QWidget()
        seekbar_grid = QGridLayout(seekbar_container)
        seekbar_grid.setContentsMargins(10, 0, 10, 0)
        seekbar_grid.addWidget(self.buffer_bar, 0, 0)
        seekbar_grid.addWidget(self.slider, 0, 0)
        
        self.time_label = QLabel("00:00 / 00:00")
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        
        c_layout.addWidget(self.play_btn)
        c_layout.addWidget(seekbar_container, 1)
        c_layout.addWidget(self.time_label)
        c_layout.addSpacing(20)
        c_layout.addWidget(QLabel("🔊"))
        c_layout.addWidget(self.volume_slider)
        
        v_layout.addWidget(self.controls)
        self.stack.addWidget(self.video_container)
        
        layout.addWidget(self.stack)
        
        # Media
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.bufferProgressChanged.connect(self._on_buffer_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        
    def _load_content(self):
        ext = os.path.splitext(self.path)[1].lower()
        from src.ui.link_master.preview_window import PreviewWindow
        
        if ext in PreviewWindow.IMAGE_EXTENSIONS:
            self.stack.setCurrentIndex(0)
            self._show_image()
        elif ext in PreviewWindow.VIDEO_EXTENSIONS:
            self.stack.setCurrentIndex(1)
            self.player.setSource(QUrl.fromLocalFile(self.path))
            self.player.play()
            
    def _show_image(self):
        pix = QPixmap(self.path)
        if not pix.isNull():
            # Initial scale, won't update on resize in this simple version
            # unless we implement resizeEvent
            self.image_label.setPixmap(pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            
    def _toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()
            
    def _on_playback_state_changed(self, state):
        self.play_btn.setText("⏸" if state == QMediaPlayer.PlaybackState.PlayingState else "▶")
        
    def _on_position_changed(self, pos):
        self.slider.blockSignals(True)
        self.slider.setValue(pos)
        self.slider.blockSignals(False)
        self._update_time()
        
    def _on_duration_changed(self, dur):
        self.slider.setRange(0, dur)
        self._update_time()
        
    def _on_seek(self, pos):
        self.player.setPosition(pos)
        
    def _on_volume_changed(self, vol):
        self.audio.setVolume(vol / 100.0)
        
    def _on_buffer_changed(self, progress):
        """Update buffering progress bar. Supports 0.0-1.0 and 0-100."""
        if progress <= 1.0:
            val = int(progress * 100)
        else:
            val = int(progress)
        self.buffer_bar.setValue(val)
        
    def _update_time(self):
        def fmt(ms):
            s = ms // 1000
            m, s = divmod(s, 60)
            return f"{m:02}:{s:02}"
        self.time_label.setText(f"{fmt(self.player.position())} / {fmt(self.player.duration())}")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            self._toggle_playback()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.stack.currentIndex() == 0:
            self._show_image()
    
    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
