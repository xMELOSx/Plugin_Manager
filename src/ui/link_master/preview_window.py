"""
マルチプレビューウィンドウ + フォルダプロパティパネル
複数の画像/動画を順番に表示し、フォルダプロパティの編集機能も提供する。
"""
import os
import subprocess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QMenu, QSizePolicy, QMessageBox,
                             QSplitter, QFrame, QLineEdit, QTextEdit, 
                             QCheckBox, QScrollArea, QGroupBox, QMainWindow,
                             QFileDialog, QFormLayout, QStackedWidget, QSlider,
                             QProgressBar, QGridLayout, QStyle, QStyleOptionSlider,
                             QSpinBox)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QMouseEvent, QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from src.ui.flow_layout import FlowLayout
from src.ui.link_master.compact_dial import CompactDial
from src.core.lang_manager import _
import shutil


class JumpSlider(QSlider):
    """Clickable slider that jumps to the clicked position."""
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Fix: Rect.contains() accepts QPoint directly.
            click_pos = event.pos()
            
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            sr = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self)
            
            if not sr.contains(click_pos):
                new_val = self.minimum() + ((self.maximum() - self.minimum()) * click_pos.x()) / self.width()
                self.setValue(int(new_val))
                self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)


class PreviewWindow(QWidget):
    """複数プレビューファイルを表示するウィンドウ + プロパティパネル。"""
    
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.webm', '.mov'}
    
    # Signal for property changes
    property_changed = pyqtSignal(dict)
    
    def __init__(self, paths: list, parent=None, folder_path: str = None, 
                 folder_config: dict = None, db=None, storage_root: str = None,
                 deployer=None, target_dir: str = None):
        super().__init__(parent)
        
        # Ensure paths is a list and filter existing files
        if paths is None:
            self.paths = []
        elif isinstance(paths, str):
            self.paths = [paths] if os.path.exists(paths) else []
        else:
            self.paths = [p for p in paths if p and os.path.exists(p)]
        
        self.current_index = 0
        self.folder_path = folder_path
        self.folder_config = folder_config or {}
        self.db = db
        self.storage_root = storage_root
        self.deployer = deployer
        self.target_dir = target_dir
        
        self.setWindowTitle("Preview")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setMinimumSize(600, 400)
        
        # Set window title with folder name
        folder_name = os.path.basename(folder_path) if folder_path else "Properties"
        self.setWindowTitle(f"Properties - {folder_name}")
        
        self._init_ui()
        self._apply_style()
        self._load_folder_properties()
        self._restore_window_size()
        
        # Show first item after UI is ready, or show no-preview message
        if self.paths:
            QTimer.singleShot(50, self._show_current)
        else:
            QTimer.singleShot(50, self._show_no_preview)
    
    def _show_no_preview(self):
        """プレビューがない場合のメッセージを表示。"""
        self.image_label.setText("プレビューが設定されていません")
        self.index_label.setText("0/0")
        self.filename_label.setText("")
    
    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for preview and properties
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left: Preview Area
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        
        # Navigation Bar
        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(10, 5, 10, 5)
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedWidth(40)
        self.prev_btn.clicked.connect(self._prev)
        
        self.index_label = QLabel("0/0")
        self.index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.index_label.setFixedWidth(50)
        
        self.filename_label = QLabel("")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedWidth(40)
        self.next_btn.clicked.connect(self._next)
        
        self.edit_previews_btn = QPushButton(_("📑 Edit Full Previews"))
        self.edit_previews_btn.setFixedWidth(140)
        self.edit_previews_btn.clicked.connect(self._open_preview_editor)
        
        nav_bar.addWidget(self.prev_btn)
        nav_bar.addWidget(self.index_label)
        nav_bar.addWidget(self.filename_label)
        nav_bar.addWidget(self.next_btn)
        nav_bar.addWidget(self.edit_previews_btn)
        
        nav_widget = QWidget()
        nav_widget.setLayout(nav_bar)
        nav_widget.setObjectName("navBar")
        preview_layout.addWidget(nav_widget)
        
        # Preview Area - Use QStackedWidget to stabilize layout
        self.preview_stack = QStackedWidget()
        
        # Page 0: Image
        self.image_label = QLabel("No preview")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setScaledContents(False)
        self.image_label.setMinimumSize(100, 100)
        self.preview_stack.addWidget(self.image_label)
        
        # Page 1: Video
        self.video_container = QWidget()
        video_v_layout = QVBoxLayout(self.video_container)
        video_v_layout.setContentsMargins(0, 0, 0, 0)
        video_v_layout.setSpacing(0)
        
        self.video_widget = QVideoWidget()
        video_v_layout.addWidget(self.video_widget)
        
        # Video Controls
        self.video_controls = QWidget()
        self.video_controls.setFixedHeight(40)
        self.video_controls.setObjectName("videoControls")
        controls_layout = QHBoxLayout(self.video_controls)
        controls_layout.setContentsMargins(5, 0, 5, 0) # Reduced margins
        controls_layout.setSpacing(8)
        
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; border: none; outline: none; 
                color: white; font-size: 20px; font-weight: bold; 
            }
            QPushButton:hover { background: rgba(255,255,255, 0.1); border-radius: 16px; }
        """)
        self.play_btn.clicked.connect(self._toggle_playback)
        
        # Seekbar with buffering
        self.seekbar_container = QWidget()
        self.seekbar_container.setFixedHeight(24)
        self.seekbar_container.setMinimumWidth(200) # Added safety width
        self.seekbar_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Grid layout for triple-layering
        seekbar_grid = QGridLayout(self.seekbar_container)
        seekbar_grid.setContentsMargins(0, 0, 0, 0)
        seekbar_grid.setSpacing(0)
        seekbar_grid.setColumnStretch(0, 1) # Force total expansion
        
        # Layer 1: Buffer Progress (Bottom) - Dark Gray/Medium Gray
        self.buffer_bar = QProgressBar()
        self.buffer_bar.setRange(0, 100)
        self.buffer_bar.setValue(0)
        self.buffer_bar.setTextVisible(False)
        self.buffer_bar.setFixedHeight(6)
        self.buffer_bar.setStyleSheet("""
            QProgressBar { background-color: #222; border: none; border-radius: 3px; padding: 0; margin: 0; }
            QProgressBar::chunk { background-color: #555; border-radius: 3px; }
        """)
        self.buffer_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Layer 2: Played Progress (Middle) - Light Gray
        self.played_bar = QProgressBar()
        self.played_bar.setRange(0, 100)
        self.played_bar.setValue(0)
        self.played_bar.setTextVisible(False)
        self.played_bar.setFixedHeight(6)
        self.played_bar.setStyleSheet("""
            QProgressBar { background-color: transparent; border: none; border-radius: 3px; padding: 0; margin: 0; }
            QProgressBar::chunk { background-color: #aaa; border-radius: 3px; }
        """)
        self.played_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Layer 3: Interaction Slider (Top) - Orange Handle
        self.seek_slider = JumpSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.seek_slider.sliderMoved.connect(self._on_seek)
        self.seek_slider.setStyleSheet("""
            QSlider { background: transparent; padding: 0; margin: 0; }
            QSlider::groove:horizontal { height: 6px; background: transparent; border-radius: 3px; margin: 0; }
            QSlider::handle:horizontal {
                background: #e67e22; border: 1px solid #d35400;
                width: 14px; height: 14px; margin: -4px 0; border-radius: 7px;
            }
        """)
        self.seek_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Absolute layering without alignment flags to ensure full stretch
        seekbar_grid.addWidget(self.buffer_bar, 0, 0)
        seekbar_grid.addWidget(self.played_bar, 0, 0)
        seekbar_grid.addWidget(self.seek_slider, 0, 0)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #ddd; font-family: 'Consolas', monospace; font-size: 13px;")
        
        self.volume_btn = QPushButton("🔊")
        self.volume_btn.setFixedSize(32, 32)
        self.volume_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume_btn.clicked.connect(self._toggle_mute)
        self.volume_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; border: none; outline: none; 
                font-size: 16px; color: white; padding: 0; margin: 0;
            }
            QPushButton:hover { background: #444; border-radius: 4px; }
        """)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.seekbar_container, 20) # High stretch factor for absolute priority
        controls_layout.addWidget(self.time_label)
        controls_layout.addSpacing(5)
        controls_layout.addWidget(self.volume_btn)
        controls_layout.addWidget(self.volume_slider)
        
        self.video_controls.setFixedHeight(50) 
        
        video_v_layout.addWidget(self.video_controls)
        self.preview_stack.addWidget(self.video_container)
        
        preview_layout.addWidget(self.preview_stack)
        
        self.splitter.addWidget(preview_container)
        
        # Right: Properties Panel
        self._create_properties_panel()
        
        # Set splitter sizes (preview takes more space)
        self.splitter.setSizes([700, 300])
        
        # Media Player
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.bufferProgressChanged.connect(self._on_buffer_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        
        # Auto-play timer
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self._next)
        
        # Mouse events
        self.image_label.mousePressEvent = self._on_image_click
        self.image_label.mouseDoubleClickEvent = self._on_image_double_click
        self.video_widget.mousePressEvent = self._on_image_click
        self.video_widget.mouseDoubleClickEvent = self._on_image_double_click
        
        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _create_properties_panel(self):
        """プロパティパネルを作成。"""
        prop_scroll = QScrollArea()
        prop_scroll.setWidgetResizable(True)
        prop_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        prop_scroll.setMinimumWidth(100)
        # Remove maximum width to allow full resizing of the preview area
        
        prop_container = QWidget()
        prop_container.setObjectName("propContainer")
        prop_layout = QVBoxLayout(prop_container)
        prop_layout.setContentsMargins(10, 10, 10, 10)
        prop_layout.setSpacing(10)
        
        # Checkboxes (horizontal layout)
        checkbox_layout = QHBoxLayout()
        
        self.deploy_check = QCheckBox(_("Link Enabled"))
        # Actual deploy/unlink will happen on save, not immediately
        checkbox_layout.addWidget(self.deploy_check)
        
        self.visible_check = QCheckBox(_("Visibility"))
        # Actual visibility change will happen on save, not immediately
        checkbox_layout.addWidget(self.visible_check)
        
        # Favorite & Score (Moved to top right of visibility)
        checkbox_layout.addSpacing(10)
        # Favorite button
        is_fav = bool(self.folder_config.get('is_favorite', False))
        self.favorite_btn = QPushButton(_("★Favorite") if is_fav else _("☆Favorite"), self)
        self.favorite_btn.setCheckable(True)
        self.favorite_btn.setChecked(is_fav)
        self.favorite_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.favorite_btn.setStyleSheet("""
            QPushButton { 
                background-color: transparent; color: #ccc; border: none; outline: none;
                text-align: left; padding: 2px 5px; min-width: 100px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QPushButton:checked { 
                background-color: transparent; color: #f1c40f; font-weight: bold; border: none; outline: none;
            }
        """)
        # Only update UI text on toggle, actual save happens on save button
        self.favorite_btn.toggled.connect(self._on_favorite_ui_update)
        checkbox_layout.addWidget(self.favorite_btn)
        
        checkbox_layout.addSpacing(15)
        
        # Score label and CompactDial
        score_label = QLabel(_("Score:"), self)
        score_label.setStyleSheet("color: #ccc; font-size: 11px;")
        checkbox_layout.addWidget(score_label)
        
        self.score_dial = CompactDial(self, digits=3, show_arrows=True)
        self.score_dial.valueChanged.connect(self._on_score_changed)
        checkbox_layout.addWidget(self.score_dial)
        
        checkbox_layout.addStretch()
        prop_layout.addLayout(checkbox_layout)
        
        # Folder Name (read-only) with folder open button
        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(5)
        
        folder_label = QLabel(_("Folder Name:"))
        folder_row.addWidget(folder_label)
        
        self.folder_open_btn = QPushButton()
        self.folder_open_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.folder_open_btn.setFixedSize(24, 24)
        self.folder_open_btn.setToolTip(_("Open actual folder"))
        self.folder_open_btn.clicked.connect(self._open_actual_folder)
        folder_row.addWidget(self.folder_open_btn)
        folder_row.addStretch()
        
        prop_layout.addLayout(folder_row)
        
        self.folder_name_label = QLabel("-")
        self.folder_name_label.setObjectName("readOnlyField")
        self.folder_name_label.setWordWrap(True)
        prop_layout.addWidget(self.folder_name_label)
        
        # Display Name
        prop_layout.addWidget(QLabel(_("Display Name:")))
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText(_("Enter display name..."))
        prop_layout.addWidget(self.display_name_edit)
        
        # Description
        prop_layout.addWidget(QLabel(_("Description:")))
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(_("Enter description..."))
        self.description_edit.setMaximumHeight(80)
        prop_layout.addWidget(self.description_edit)

        # Author
        prop_layout.addWidget(QLabel(_("Author:")))
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText(_("Author name..."))
        prop_layout.addWidget(self.author_edit)

        # URL List Management
        prop_layout.addWidget(QLabel(_("URL:")))
        url_manage_layout = QHBoxLayout()
        self.url_btn = QPushButton(_("🌐 Manage URLs..."))
        self.url_btn.clicked.connect(self._open_url_manager)
        self.url_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; min-height: 28px;")
        url_manage_layout.addWidget(self.url_btn)
        
        self.url_count_label = QLabel("(0)")
        self.url_count_label.setStyleSheet("color: #888;")
        url_manage_layout.addWidget(self.url_count_label)
        url_manage_layout.addStretch()
        prop_layout.addLayout(url_manage_layout)
        
        # Hidden field for JSON storage
        self.url_list_json = "[]"
        self.marked_url = None
        self.auto_mark = True
        
        # Quick Tags
        tag_group = QGroupBox(_("Quick Tags"))
        tag_v_layout = QVBoxLayout(tag_group)
        
        self.tag_panel = QWidget()
        self.tag_panel_layout = FlowLayout(self.tag_panel)
        self.tag_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_panel_layout.setSpacing(5)
        
        self.tag_buttons = {} # name -> QPushButton
        self._init_tag_buttons()
        
        tag_v_layout.addWidget(self.tag_panel)
        
        tag_v_layout.addWidget(QLabel(_("Additional Tags:")))
        self.tags_edit = QLineEdit()
        self.tags_edit.setMaxLength(100) # Phase 28: Add character limit
        self.tags_edit.setPlaceholderText(_("Enter tags separated by comma..."))
        tag_v_layout.addWidget(self.tags_edit)
        
        prop_layout.addWidget(tag_group)
        
        # Button Row: 詳細編集 + 保存
        btn_row = QHBoxLayout()
        
        # Detail Edit Button (Opens full FolderPropertiesDialog)
        self.detail_btn = QPushButton(_("📝 Detail Edit"))
        self.detail_btn.clicked.connect(self._open_detail_edit)
        self.detail_btn.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 8px;")
        self.detail_btn.setToolTip(_("Close this and open full property editor"))
        btn_row.addWidget(self.detail_btn)
        
        # Save Button (Minimal - No advanced features here)
        self.save_btn = QPushButton(_("💾 Save"))
        self.save_btn.clicked.connect(self._save_properties)
        self.save_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        btn_row.addWidget(self.save_btn)
        
        # Shortcut for Alt+Enter Save
        from PyQt6.QtGui import QKeySequence, QShortcut
        self.save_shortcut = QShortcut(QKeySequence("Alt+Return"), self)
        self.save_shortcut.activated.connect(self._save_properties)
        self.save_shortcut_win = QShortcut(QKeySequence("Alt+Enter"), self)
        self.save_shortcut_win.activated.connect(self._save_properties)
        
        prop_layout.addLayout(btn_row)
        
        prop_layout.addStretch()
        
        prop_scroll.setWidget(prop_container)
        self.splitter.addWidget(prop_scroll)
    
    def keyPressEvent(self, event):
        """Handle global shortcuts like Alt+Enter to save properties."""
        from PyQt6.QtCore import Qt
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self._save_properties()
                return
        super().keyPressEvent(event)

    def _init_tag_buttons(self):
        """頻繁に使用するタグのボタンを初期化。"""
        try:
            # 親ウィンドウから頻繁なタグを取得
            window = self.parent()
            # Traverse up the parent chain to find the main window that has _load_frequent_tags
            while window:
                if hasattr(window, '_load_frequent_tags'):
                    break
                window = window.parent()

            if window and hasattr(window, '_load_frequent_tags'):
                frequent_tags = window._load_frequent_tags()
                for t in frequent_tags:
                    if t.get('is_sep'): continue
                    name = t.get('name')
                    mode = t.get('display_mode', 'text')
                    emoji = t.get('emoji', '')
                    
                    # Respect display_mode as in FolderPropertiesDialog
                    btn_text = ""
                    if mode == 'symbol' and emoji:
                        btn_text = emoji
                    elif mode == 'text_symbol' and emoji:
                        btn_text = f"{emoji} {name}"
                    elif mode == 'image':
                        btn_text = "" # Text hidden for image-only
                    elif mode == 'image_text':
                        btn_text = name # Icon + Text
                    else: # 'text' or fallback
                        btn_text = name
                    
                    btn = QPushButton(btn_text)
                    btn.setCheckable(True)
                    
                    # Add Icon if mode allows
                    show_icon = (mode in ['image', 'image_text', 'text'])
                    if show_icon and t.get('icon') and os.path.exists(t.get('icon')):
                         btn.setIcon(QIcon(t.get('icon')))
                    elif mode not in ['symbol', 'text_symbol'] and t.get('icon') and os.path.exists(t.get('icon')):
                         # Fallback for complex modes
                         btn.setIcon(QIcon(t.get('icon')))

                    btn.setStyleSheet("background-color: #444; color: #ccc; border: 1px solid #555; padding: 4px 8px;")
                    
                    # トグルイベント
                    btn.toggled.connect(lambda checked, n=name: self._on_tag_btn_toggled(n, checked))
                    self.tag_panel_layout.addWidget(btn)
                    self.tag_buttons[name.lower()] = btn
        except Exception as e:
            print(f"Error initializing tag buttons in PreviewWindow: {e}")

    def _on_tag_btn_toggled(self, name, checked):
        btn = self.tag_buttons.get(name.lower())
        if btn:
            if checked:
                btn.setStyleSheet("background-color: #2980b9; color: white; border: 1px solid #3498db; padding: 4px 8px;")
            else:
                btn.setStyleSheet("background-color: #444; color: #ccc; border: 1px solid #555; padding: 4px 8px;")

    def _apply_style(self):
        self.setStyleSheet("""
            PreviewWindow {
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QWidget#navBar, QWidget#videoControls {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
            }
            QWidget#propContainer {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
                background-color: transparent;
            }
            QLabel#readOnlyField {
                background-color: #2d2d2d;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QLineEdit, QTextEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                padding: 5px;
                border-radius: 3px;
            }
            QCheckBox {
                color: #e0e0e0;
                background-color: transparent;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #252525;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                color: #e0e0e0;
            }
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background-color: #3d3d3d;
                border-radius: 5px;
            }
        """)

    def _load_folder_properties(self):
        """フォルダプロパティをUIにロード。"""
        if not self.folder_path:
            return
        
        # Folder name - disabled/grayed out appearance
        self.folder_name_label.setText(os.path.basename(self.folder_path))
        self.folder_name_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                color: #888888;
                padding: 8px;
                border-radius: 3px;
                border: 1px solid #3d3d3d;
            }
        """)
        
        # Load from config - use correct DB column names
        cfg = self.folder_config or {}
        
        # is_visible controls Visibility checkbox (block signals to prevent unwanted side-effects)
        is_visible = cfg.get('is_visible')
        if is_visible is None:
            is_visible = True
        self.visible_check.blockSignals(True)
        self.visible_check.setChecked(is_visible == 1 or is_visible is True)
        self.visible_check.blockSignals(False)
        
        # Link Enabled (Check actual filesystem status) - block signals for initial load
        is_actually_linked = False
        if self.deployer and self.folder_path:
            # Re-use logic from ItemCard border
            target_link = os.path.join(self.target_dir, os.path.basename(self.folder_path)) if self.target_dir else None
            if target_link:
                status = self.deployer.get_link_status(target_link, expected_source=self.folder_path)
                if status.get('status') in ['linked', 'conflict']: # 'conflict' counts as 'linked' for the checkbox usually
                    is_actually_linked = True
        self.deploy_check.blockSignals(True)
        self.deploy_check.setChecked(is_actually_linked)
        self.deploy_check.blockSignals(False)
        
        # Display name + Char limit
        self.display_name_edit.setMaxLength(100)
        self.display_name_edit.setText(cfg.get('display_name', '') or '')
        
        # Description
        self.description_edit.setText(cfg.get('description', '') or '')
        
        # Author
        self.author_edit.setText(cfg.get('author', '') or '')
        
        # URL List Handling
        self.url_list_json = cfg.get('url_list', '[]') or '[]'
        old_url = cfg.get('url', '')
        if old_url and self.url_list_json == '[]':
            import json
            self.url_list_json = json.dumps([{"url": old_url, "active": True}])
            
        self._update_url_count_preview()
        
        # Favorite & Score
        self.favorite_btn.blockSignals(True)
        is_fav = bool(cfg.get('is_favorite'))
        self.favorite_btn.setChecked(is_fav)
        self.favorite_btn.setText(_("★Favorite") if is_fav else _("☆Favorite"))
        self.favorite_btn.blockSignals(False)
        
        self.score_dial.blockSignals(True)
        self.score_dial.setValue(int(cfg.get('score', 0) or 0))
        self.score_dial.blockSignals(False)
        
        # Tags
        tags_str = cfg.get('tags', '') or ''
        current_tags = [t.strip().lower() for t in tags_str.split(',') if t.strip()]
        
        # Update tag buttons
        quick_tag_names = set(self.tag_buttons.keys())
        for name, btn in self.tag_buttons.items():
            btn.blockSignals(True)
            if name in current_tags:
                btn.setChecked(True)
                btn.setStyleSheet("background-color: #2980b9; color: white; border: 1px solid #3498db; padding: 4px 8px;")
            else:
                btn.setChecked(False)
                btn.setStyleSheet("background-color: #444; color: #ccc; border: 1px solid #555; padding: 4px 8px;")
            btn.blockSignals(False)
            
        # Update additional tags (filter out quick tags)
        manual_only = [t.strip() for t in tags_str.split(',') if t.strip() and t.strip().lower() not in quick_tag_names]
        self.tags_edit.setText(", ".join(manual_only))
    
    def _on_deploy_changed(self, state):
        """リンク有効の即時更新（デプロイ/アンリンクを実行）。"""
        if not self.folder_path or not self.storage_root:
            return
        try:
            rel_path = os.path.relpath(self.folder_path, self.storage_root).replace('\\', '/')
            is_linked = (state == Qt.CheckState.Checked.value)
            
            # Call parent's deploy/unlink methods
            parent = self.parent()
            if parent:
                if is_linked and hasattr(parent, '_deploy_single'):
                    parent._deploy_single(rel_path, update_ui=True)
                elif not is_linked and hasattr(parent, '_unlink_single'):
                    parent._unlink_single(rel_path, update_ui=True)
            
            self.property_changed.emit({'is_linked': is_linked})
        except Exception as e:
            print(f"[Error] _on_deploy_changed: {e}")
    
    def _on_visible_changed(self, state):
        """表示状態の即時更新（親のメソッドを使用）。"""
        if not self.folder_path or not self.storage_root:
            return
        try:
            rel_path = os.path.relpath(self.folder_path, self.storage_root).replace('\\', '/')
            is_visible = (state == Qt.CheckState.Checked.value)
            
            # Call parent's visibility toggle method if available
            parent = self.parent()
            if parent and hasattr(parent, '_set_visibility_single'):
                parent._set_visibility_single(rel_path, visible=is_visible, update_ui=True)
            elif self.db:
                self.db.update_folder_display_config(rel_path, is_visible=is_visible)
            
            self.property_changed.emit({'is_visible': is_visible})
        except Exception as e:
            print(f"[Error] _on_visible_changed: {e}")
    
    def _on_display_name_changed(self):
        pass  # Will save on button click
    
    def _on_favorite_ui_update(self, checked):
        """Update favorite button text only (actual save on save button)."""
        self.favorite_btn.setText(_("★Favorite") if checked else _("☆Favorite"))

    def _on_score_changed(self, value):
        """スコア値変更時の処理。"""
        self.property_changed.emit({'score': value})
        # Score saving is also handled via focus out in CompactDial or save button
    
    def _on_quick_tag_changed(self, state):
        pass  # Will save on button click
    
    def _on_tags_changed(self):
        pass  # Will save on button click

    def _update_url_count_preview(self):
        """Update the count label and button state."""
        import json
        try:
            data = json.loads(self.url_list_json)
            urls = []
            if isinstance(data, dict):
                urls = data.get('urls', [])
            elif isinstance(data, list):
                urls = data
            
            count = len(urls)
            self.url_count_label.setText(f"({count})")
        except:
            self.url_count_label.setText("(0)")

    def _open_url_manager(self):
        """Open the URL List management dialog."""
        from src.ui.link_master.dialogs_legacy import URLListDialog
        import json
        
        dialog = URLListDialog(self, url_list_json=self.url_list_json)
        if dialog.exec():
            # Update state
            new_data = dialog.get_data()
            self.url_list_json = new_data
            self._update_url_count_preview()
            
            # Auto-save immediately for URL changes? 
            # Let's emit property changed so it's tracked
            self.property_changed.emit({'url_list': self.url_list_json})
    
    def _save_properties(self):
        """プロパティを保存。"""
        if not self.db or not self.folder_path or not self.storage_root:
            QMessageBox.warning(self, "Error", "Cannot save: no database connection")
            return
        
        try:
            rel_path = os.path.relpath(self.folder_path, self.storage_root).replace('\\', '/')
            if rel_path == '.':
                rel_path = ''
            
            # Collect tags from buttons and text edit
            quick_tags = [name for name, btn in self.tag_buttons.items() if btn.isChecked()]
            manual_tags = [t.strip() for t in self.tags_edit.text().split(',') if t.strip()]
            all_tags = sorted(list(set(quick_tags + manual_tags)))
            tags_str = ", ".join(all_tags) if all_tags else None
            
            # Build update kwargs using correct DB column names (Minimal - no advanced features)
            update_kwargs = {
                'is_visible': self.visible_check.isChecked(),
                'display_name': self.display_name_edit.text().strip() or None,
                'description': self.description_edit.toPlainText().strip() or None,
                'author': self.author_edit.text().strip() or None,
                'url_list': self.url_list_json,
                'tags': tags_str,
                'is_favorite': 1 if self.favorite_btn.isChecked() else 0,
                'score': self.score_dial.value(),
                'manual_preview_path': "; ".join(self.paths) if self.paths else None
            }
            
            # Save using correct method
            self.db.update_folder_display_config(rel_path, **update_kwargs)
            
            # Handle deploy/unlink based on checkbox state
            is_linked_requested = self.deploy_check.isChecked()
            parent = self.parent()
            if parent:
                # Check current status
                current_status = 'unlinked'
                if self.deployer and self.target_dir:
                    target_link = os.path.join(self.target_dir, os.path.basename(self.folder_path))
                    status_info = self.deployer.get_link_status(target_link, expected_source=self.folder_path)
                    current_status = status_info.get('status', 'unlinked')
                
                currently_linked = current_status in ['linked', 'conflict']
                
                if is_linked_requested and not currently_linked:
                    if hasattr(parent, '_deploy_single'):
                        parent._deploy_single(rel_path, update_ui=True)
                elif not is_linked_requested and currently_linked:
                    if hasattr(parent, '_unlink_single'):
                        parent._unlink_single(rel_path, update_ui=True)
            
            # Emit signal
            self.property_changed.emit(update_kwargs)
            
            # Close without dialog (as requested)
            self.close()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to save: {e}")
    
    def _open_actual_folder(self):
        """Open the folder in Explorer."""
        if self.folder_path and os.path.isdir(self.folder_path):
            os.startfile(os.path.normpath(self.folder_path))
    
    def _open_detail_edit(self):
        """Close this window and open the full FolderPropertiesDialog."""
        from src.ui.link_master.dialogs import FolderPropertiesDialog
        
        if not self.folder_path or not self.storage_root:
            return
        
        try:
            rel_path = os.path.relpath(self.folder_path, self.storage_root).replace('\\', '/')
            current_config = self.db.get_folder_config(rel_path) if self.db else {}
            
            # Find app name from parent chain
            app_name = getattr(self, 'app_name', None)
            window = self.parent()
            while window and not app_name:
                if hasattr(window, 'app_name'):
                    app_name = window.app_name
                    break
                window = window.parent() if hasattr(window, 'parent') else None
            
            # Close this window first
            self.close()
            
            # Open the full dialog - use topmost parent as owner
            top_parent = self.parent()
            while top_parent and top_parent.parent():
                top_parent = top_parent.parent()
            
            dialog = FolderPropertiesDialog(
                parent=top_parent,
                folder_path=self.folder_path,
                current_config=current_config,
                app_name=app_name,
                storage_root=self.storage_root,
                thumbnail_manager=getattr(self, 'thumbnail_manager', None)
            )
            if dialog.exec():
                # Refresh parent if possible
                if self.parent() and hasattr(self.parent(), 'refresh') and callable(self.parent().refresh):
                    self.parent().refresh()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to open editor: {e}")

    def _open_preview_editor(self):
        """フルプレビュー編集ダイアログを開く。"""
        from src.ui.link_master.dialogs import PreviewTableDialog
        
        dlg = PreviewTableDialog(self, paths=self.paths)
        if dlg.exec():
            new_paths = dlg.get_paths()
            self.paths = [p for p in new_paths if os.path.exists(p)]
            
            # Reset index if current is invalid
            if self.current_index >= len(self.paths):
                self.current_index = 0
            
            if self.paths:
                self._show_current()
            else:
                self._show_no_preview()
            
            # Notify that properties need saving (or just save now?)
            # The user usually expects "Save" button to handle persistence.
            # But the paths list is now updated in memory.
            self.filename_label.setStyleSheet("color: #e67e22; font-weight: bold;") # Hint changed

    def _on_image_click(self, event):
        """Click on image area."""
        pass

    def _on_image_double_click(self, event):
        """Double click to open preview table editor."""
        self._open_preview_editor()
    
    def _show_current(self):
        """現在のインデックスのファイルを表示。"""
        if not self.paths:
            self.index_label.setText("0/0")
            self.filename_label.setText("No files")
            return
        
        # Ensure index is valid
        if self.current_index >= len(self.paths):
            self.current_index = 0
        
        path = self.paths[self.current_index]
        ext = os.path.splitext(path)[1].lower()
        
        # Update labels
        self.index_label.setText(f"{self.current_index + 1}/{len(self.paths)}")
        self.filename_label.setText(os.path.basename(path))
        self.setWindowTitle(f"Preview - {os.path.basename(path)}")
        
        # Stop any playing video
        self.media_player.stop()
        
        if ext in self.IMAGE_EXTENSIONS:
            self._show_image(path)
        elif ext in self.VIDEO_EXTENSIONS:
            self._show_video(path)
        else:
            self._show_unsupported(path)
    
    def _show_image(self, path):
        """画像を表示。"""
        self.preview_stack.setCurrentIndex(0)
        
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Failed to load image")
    
    def _show_video(self, path):
        """動画を表示。"""
        self.preview_stack.setCurrentIndex(1)
        self.buffer_bar.setValue(0) # Reset buffer for new media
        self.media_player.setSource(QUrl.fromLocalFile(path))
        self.media_player.play()
        # Reset play button text to ensure consistency
        self.play_btn.setText("||")
    
    def _show_unsupported(self, path):
        """サポートされていないファイル。"""
        self.preview_stack.setCurrentIndex(0)
        self.image_label.setText(f"Unsupported: {os.path.basename(path)}")
    
    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Phase 28: Auto-loop behavior
            self.media_player.setPosition(0)
            self.media_player.play()
    
    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            # Use ASCII pipe characters to avoid Windows blue-framed emojis
            self.play_btn.setText("||") 
        else:
            self.play_btn.setText("▶")
            
    def _toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
            
    def _on_position_changed(self, position):
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(position)
        self.seek_slider.blockSignals(False)
        self.played_bar.setValue(position) # Update played progress layer
        self._update_time_label()
        
    def _on_duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)
        self.played_bar.setRange(0, duration) # Sync visual progress bar
        self.buffer_bar.setRange(0, duration) # Sync buffer progress bar (using ms instead of 0-100)
        self._update_time_label()
        
    def _on_seek(self, position):
        self.media_player.setPosition(position)
        
    def _on_volume_changed(self, volume):
        self.audio_output.setVolume(volume / 100.0)
        if volume > 0:
            self.volume_btn.setText("🔊")
        else:
            self.volume_btn.setText("🔇")
            
    def _toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.volume_btn.setText("🔇" if not is_muted else "🔊")
        if not is_muted:
            self.volume_slider.blockSignals(True)
            self._prev_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
            self.volume_slider.blockSignals(False)
        else:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(getattr(self, '_prev_volume', 100))
            self.volume_slider.blockSignals(False)
        
    def _update_time_label(self):
        curr = self.media_player.position()
        total = self.media_player.duration()
        
        def format_time(ms):
            s = ms // 1000
            m, s = divmod(s, 60)
            return f"{m:02}:{s:02}"
            
        self.time_label.setText(f"{format_time(curr)} / {format_time(total)}")
        
    def _on_buffer_changed(self, progress):
        """Update buffering progress bar layer with persistence logic."""
        duration = self.media_player.duration()
        if duration <= 0:
            return 
            
        if progress <= 1.0:
            val = int(progress * duration)
        else:
            val = int((progress / 100.0) * duration)
            
        # Persistence: If player reports 0 during seeking, ignore it
        # unless we are at the very start of the media.
        if val <= 0 and self.buffer_bar.value() > (duration * 0.05):
            if self.media_player.position() > 500:
                return # Keep old buffer value

        self.buffer_bar.setValue(val)
    
    def _prev(self):
        if self.paths:
            self.current_index = (self.current_index - 1) % len(self.paths)
            self._show_current()
    
    def _next(self):
        if self.paths:
            self.current_index = (self.current_index + 1) % len(self.paths)
            self._show_current()
    
    def _on_image_click(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            widget = self.image_label if self.image_label.isVisible() else self.video_widget
            if event.position().x() < widget.width() / 2:
                self._prev()
            else:
                self._next()
    
    def _on_image_double_click(self, event):
        """ダブルクリックで独立した再生ウィンドウを開く。"""
        if not self.paths:
            return
        
        from src.ui.link_master.media_playback_window import MediaPlaybackWindow
        path = self.paths[self.current_index]
        
        # Stop current playback if it's a video
        self.media_player.pause()
        
        self.playback_win = MediaPlaybackWindow(path, self)
        self.playback_win.show()
    
    def _show_context_menu(self, pos):
        """コンテキストメニューの表示。"""
        if not self.paths:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d; }
            QMenu::item:selected { background-color: #5d5d5d; }
        """)
        
        open_playback_act = menu.addAction("🎬 専用ウィンドウで再生")
        open_playback_act.triggered.connect(self._on_image_double_click) # Connect to the new _on_image_double_click logic
        
        menu.addSeparator()
        
        open_folder_act = menu.addAction("📁 フォルダを開く")
        open_folder_act.triggered.connect(self._open_in_explorer) # Assuming _open_folder should map to _open_in_explorer
        
        menu.addAction("🚀 外部アプリで開く").triggered.connect(self._open_external)
        menu.addAction("📂 エクスプローラーで開く").triggered.connect(self._open_in_explorer)
        menu.addSeparator()
        menu.addAction("❌ リストから削除").triggered.connect(self._remove_current)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _open_external(self):
        if not self.paths:
            return
        try:
            os.startfile(self.paths[self.current_index])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open: {e}")
    
    def _open_in_explorer(self):
        if not self.paths:
            return
        try:
            subprocess.run(['explorer', '/select,', os.path.normpath(self.paths[self.current_index])])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed: {e}")
    
    def _remove_current(self):
        if not self.paths:
            return
        
        self.paths.pop(self.current_index)
        
        if not self.paths:
            self.close()
            return
        
        if self.current_index >= len(self.paths):
            self.current_index = len(self.paths) - 1
        
        self._show_current()
    
    def get_paths(self):
        return self.paths.copy()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update image scaling on resize if currently showing an image
        if self.paths and self.preview_stack.currentIndex() == 0:
            self._show_image(self.paths[self.current_index])
    
    def _restore_window_size(self):
        """保存されたウィンドウサイズを復元。"""
        try:
            parent = self.parent()
            if parent and hasattr(parent, 'registry'):
                # Restore window size
                width = int(parent.registry.get_global('preview_window_width', 1000))
                height = int(parent.registry.get_global('preview_window_height', 600))
                self.resize(width, height)
                
                # Restore splitter sizes
                left = int(parent.registry.get_global('preview_splitter_left', 700))
                right = int(parent.registry.get_global('preview_splitter_right', 300))
                self.splitter.setSizes([left, right])
            else:
                self.resize(1000, 600)
        except Exception as e:
            print(f"[Warning] _restore_window_size: {e}")
            self.resize(1000, 600)
    
    def _save_window_size(self):
        """ウィンドウサイズを保存。"""
        try:
            parent = self.parent()
            if parent and hasattr(parent, 'registry'):
                parent.registry.set_global('preview_window_width', str(self.width()))
                parent.registry.set_global('preview_window_height', str(self.height()))
                sizes = self.splitter.sizes()
                if len(sizes) >= 2:
                    parent.registry.set_global('preview_splitter_left', str(sizes[0]))
                    parent.registry.set_global('preview_splitter_right', str(sizes[1]))
        except Exception as e:
            print(f"[Warning] _save_window_size: {e}")
    
    def closeEvent(self, event):
        self._save_window_size()
        self.media_player.stop()
        self.auto_timer.stop()
        super().closeEvent(event)


    def keyPressEvent(self, event):
        """Keyboard logic: Enter to Save."""
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            # Trigger Save instead of opening preview manager
            self._save_properties()
            # Accept event to prevent it from reaching FullPreviewManager triggers or other buttons
            event.accept()
            return
            
        super().keyPressEvent(event)

# Alias for backwards compatibility
VideoPreviewWindow = PreviewWindow
