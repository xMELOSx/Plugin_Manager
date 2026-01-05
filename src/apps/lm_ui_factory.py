""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import time
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QSplitter, QScrollArea, QTabWidget,
    QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt
from src.core.lang_manager import _
from src.ui.flow_layout import FlowLayout
from src.ui.link_master.explorer_window import ExplorerPanel
from src.ui.link_master.tag_bar import TagBar

def setup_ui(window):
    """Factory entry point to build the LinkMasterWindow UI."""
    t_start = time.perf_counter()
    main_widget = QWidget(window)
    main_widget.setStyleSheet("""
        QWidget { background-color: transparent; }
        QToolTip { background-color: #333; color: #fff; border: 1px solid #555; padding: 4px; }
        QComboBox { background-color: #3b3b3b; color: #fff; border: 1px solid #555; padding: 4px 8px; border-radius: 4px; }
        QComboBox:hover { border-color: #3498db; background-color: #444; }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView { background-color: #3b3b3b; color: #fff; selection-background-color: #2980b9; border: 1px solid #555; }
        QLineEdit { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 4px; }
        QLineEdit:hover { border-color: #3498db; background-color: #444; }
        QPushButton#header_btn { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 2px; }
        QPushButton#header_btn:hover { background-color: #3498db; border-color: #5dade2; }
        QPushButton#header_btn:pressed { background-color: #21618c; padding-top: 4px; padding-left: 4px; }
    """)
    
    main_layout = QVBoxLayout(main_widget)
    main_layout.setContentsMargins(5, 2, 5, 5)
    
    _setup_header(window, main_layout, main_widget)
    _setup_content_area(window, main_layout, main_widget)
    _setup_floating_explorer(window)
    
    # Finalize setup
    window.set_content_widget(main_widget)
    window.retranslate_ui()
    window._restore_ui_state()
    
    window.logger.info(f"[Profile] setup_ui took {time.perf_counter()-t_start:.3f}s")

def _setup_header(window, main_layout, main_widget):
    t_start = time.perf_counter()
    header_layout = QHBoxLayout()
    header_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    
    window.app_combo = QComboBox(main_widget)
    window.app_combo.setObjectName("header_app_combo")
    window.app_combo.setMinimumWidth(200)
    window.app_combo.currentIndexChanged.connect(window._on_app_changed)
    
    window.target_app_lbl = QLabel(_("Target App:"), main_widget)
    header_layout.addWidget(window.target_app_lbl)
    header_layout.addWidget(window.app_combo)
    
    window.edit_app_btn = QPushButton(_("Edit Settings"), main_widget)
    window.edit_app_btn.setObjectName("header_edit_app_btn")
    window.edit_app_btn.clicked.connect(window._open_edit_dialog)
    window.edit_app_btn.setFixedWidth(55)
    window.edit_app_btn.setStyleSheet("""
        QPushButton { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 4px; }
        QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
        QPushButton:pressed { background-color: #222; padding-top: 5px; padding-left: 5px; }
    """)
    header_layout.addWidget(window.edit_app_btn)
    
    window.web_btn = QPushButton("🌐", main_widget)
    window.web_btn.setObjectName("header_web_btn")
    window.web_btn.setFixedSize(32, 28)
    window.web_btn.setToolTip(_("Open Preferred URL in Browser"))
    window.web_btn.clicked.connect(window._open_preferred_url)
    window.web_btn.setStyleSheet("""
        QPushButton { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 2px; }
        QPushButton:hover { background-color: #3498db; border-color: #3498db; }
        QPushButton:pressed { background-color: #222; font-size: 13px; }
    """)
    header_layout.addWidget(window.web_btn)
    
    window.register_app_btn = QPushButton("➕", main_widget)
    window.register_app_btn.setObjectName("header_register_app_btn")
    window.register_app_btn.clicked.connect(window._open_register_dialog)
    window.register_app_btn.setFixedSize(32, 28)
    window.register_app_btn.setToolTip(_("Register New App"))
    window.register_app_btn.setStyleSheet("""
        QPushButton { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 2px; }
        QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
        QPushButton:pressed { background-color: #222; font-size: 13px; }
    """)
    header_layout.addWidget(window.register_app_btn)
    
    header_layout.addSpacing(20)
    
    window.tag_bar = TagBar(main_widget)
    window.tag_bar.setObjectName("main_tag_bar")
    window.tag_bar.tags_changed.connect(window._on_tags_changed)
    window.tag_bar.request_edit_tags.connect(window._open_tag_manager)
    window.tag_bar.tag_icon_updated.connect(window._on_tag_icon_updated)
    header_layout.addWidget(window.tag_bar, 1)
    
    header_layout.addSpacing(10)
    window.search_logic = QComboBox(main_widget)
    window.search_logic.setObjectName("search_logic_combo")
    window.search_logic.addItem(_("OR"), "or")
    window.search_logic.addItem(_("AND"), "and")
    window.search_logic.setFixedWidth(60)
    header_layout.addWidget(window.search_logic)
    
    window.search_bar = QLineEdit(main_widget)
    window.search_bar.setObjectName("main_search_bar")
    window.search_bar.setPlaceholderText(_("Search by name or tags..."))
    window.search_bar.setFixedWidth(300)
    window.search_bar.returnPressed.connect(window._perform_search)
    header_layout.addWidget(window.search_bar)
    
    window.search_mode = QComboBox(main_widget)
    window.search_mode.setObjectName("search_mode_combo")
    window.search_mode.addItem(_("📦 All Packages"), "all_packages")
    window.search_mode.addItem(_("📁 Categories Only"), "categories_only")
    window.search_mode.addItem(_("📁+📦 Categories with Packages"), "cats_with_packages")
    window.search_mode.setFixedWidth(150)
    header_layout.addWidget(window.search_mode)
    
    window.search_btn = QPushButton("🔍", main_widget)
    window.search_btn.setObjectName("header_search_btn")
    window.search_btn.setFixedSize(30, 28)
    window.search_btn.clicked.connect(window._perform_search)
    header_layout.addWidget(window.search_btn)
    
    window.clear_search_btn = QPushButton("✕", main_widget)
    window.clear_search_btn.setObjectName("header_clear_btn")
    window.clear_search_btn.setFixedSize(30, 28)
    window.clear_search_btn.clicked.connect(window._clear_search)
    header_layout.addWidget(window.clear_search_btn)
    
    # Preventing transparency leakage from popups (User Fix)
    for combo in [window.app_combo, window.search_logic, window.search_mode]:
        if hasattr(combo, 'view'):
            combo.view().window().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

    main_layout.addLayout(header_layout)
    window.logger.info(f"[Profile] _setup_header took {time.perf_counter()-t_start:.3f}s")

def _setup_content_area(window, main_layout, main_widget):
    window.content_wrapper = QWidget(main_widget)
    content_wrapper_layout = QHBoxLayout(window.content_wrapper)
    content_wrapper_layout.setContentsMargins(0, 0, 0, 0)
    content_wrapper_layout.setSpacing(0)
    
    _setup_sidebar(window, content_wrapper_layout)
    
    # Resizable Sidebar Splitter (Horizontal)
    window.sidebar_splitter = QSplitter(Qt.Orientation.Horizontal, window.content_wrapper)
    window.sidebar_splitter.setHandleWidth(4)
    window.sidebar_splitter.setStyleSheet("QSplitter::handle { background-color: #444; } QSplitter::handle:hover { background-color: #666; }")
    
    _setup_sidebar_drawer(window)
    
    # CARD VIEW AREA
    right_widget = QWidget(window.sidebar_splitter)
    window.sidebar_splitter.addWidget(right_widget)
    window.sidebar_splitter.setStretchFactor(1, 1)
    content_wrapper_layout.addWidget(window.sidebar_splitter, 1)
    
    right_layout = QVBoxLayout(right_widget)
    right_layout.setContentsMargins(0, 0, 0, 0)
    
    _setup_navigation_bar(window, right_layout)
    _setup_main_card_view(window, right_layout)
    
    main_layout.addWidget(window.content_wrapper, 1)

def _setup_sidebar(window, layout):
    btn_strip = QWidget(window.content_wrapper)
    btn_strip.setFixedWidth(28)
    btn_strip.setStyleSheet("background-color: #222; border-right: 1px solid #333;")
    btn_strip_layout = QVBoxLayout(btn_strip)
    btn_strip_layout.setContentsMargins(1, 82, 1, 2)
    btn_strip_layout.setSpacing(10)
    
    # Explorer Toggle
    window.btn_drawer = QPushButton("🌲", btn_strip)
    window.btn_drawer.setObjectName("sidebar_explorer_btn")
    window.btn_drawer.setFixedSize(24, 30)
    window.btn_drawer.setCheckable(True)
    window.btn_drawer.clicked.connect(window._toggle_explorer)
    window.btn_drawer.setStyleSheet("""
        QPushButton { font-size: 16px; padding: 2px; border: none; background: transparent; }
        QPushButton:hover { background: #555; border-radius: 4px; }
        QPushButton:checked { background: #27ae60; border-radius: 4px; }
    """)
    window.btn_drawer.setToolTip(_("Toggle Explorer Panel"))
    btn_strip_layout.addWidget(window.btn_drawer)
    
    # Library Toggle
    window.btn_libraries = QPushButton("📚", btn_strip)
    window.btn_libraries.setObjectName("sidebar_library_btn")
    window.btn_libraries.setFixedSize(24, 30)
    window.btn_libraries.setCheckable(True)
    window.btn_libraries.clicked.connect(lambda: window._toggle_sidebar_tab(0))
    window.btn_libraries.setStyleSheet("""
        QPushButton { font-size: 14px; padding: 2px; border: none; background: transparent; }
        QPushButton:hover { background: #555; border-radius: 4px; }
        QPushButton:checked { background: #16a085; border-radius: 4px; }
    """)
    window.btn_libraries.setToolTip(_("Library Management"))
    btn_strip_layout.addWidget(window.btn_libraries)
    
    # Presets Toggle
    window.btn_presets = QPushButton("📋", btn_strip)
    window.btn_presets.setObjectName("sidebar_presets_btn")
    window.btn_presets.setFixedSize(24, 30)
    window.btn_presets.setCheckable(True)
    window.btn_presets.clicked.connect(lambda: window._toggle_sidebar_tab(1))
    window.btn_presets.setStyleSheet("""
        QPushButton { font-size: 14px; padding: 2px; border: none; background: transparent; }
        QPushButton:hover { background: #555; border-radius: 4px; }
        QPushButton:checked { background: #2980b9; border-radius: 4px; }
    """)
    window.btn_presets.setToolTip(_("Toggle Presets"))
    btn_strip_layout.addWidget(window.btn_presets)
    
    # Notes Toggle
    window.btn_notes = QPushButton("📒", btn_strip)
    window.btn_notes.setObjectName("sidebar_notes_btn")
    window.btn_notes.setFixedSize(24, 30)
    window.btn_notes.setCheckable(True)
    window.btn_notes.clicked.connect(lambda: window._toggle_sidebar_tab(2))
    window.btn_notes.setStyleSheet("""
        QPushButton { font-size: 14px; padding: 2px; border: none; background: transparent; }
        QPushButton:hover { background: #555; border-radius: 4px; }
        QPushButton:checked { background: #8e44ad; border-radius: 4px; }
    """)
    window.btn_notes.setToolTip(_("Toggle Quick Notes"))
    btn_strip_layout.addWidget(window.btn_notes)
    
    # Tools Toggle
    window.btn_tools = QPushButton("🔧", btn_strip)
    window.btn_tools.setObjectName("sidebar_tools_btn")
    window.btn_tools.setFixedSize(24, 30)
    window.btn_tools.setCheckable(True)
    window.btn_tools.clicked.connect(lambda: window._toggle_sidebar_tab(3))
    window.btn_tools.setStyleSheet("""
        QPushButton { font-size: 14px; padding: 2px; border: none; background: transparent; }
        QPushButton:hover { background: #555; border-radius: 4px; }
        QPushButton:checked { background: #d35400; border-radius: 4px; }
    """)
    window.btn_tools.setToolTip(_("Special Actions"))
    btn_strip_layout.addWidget(window.btn_tools)
    
    btn_strip_layout.addStretch()
    layout.addWidget(btn_strip)

def _setup_sidebar_drawer(window):
    window.drawer_widget = QWidget(window.sidebar_splitter)
    window.drawer_ui_layout = QVBoxLayout(window.drawer_widget)
    window.drawer_ui_layout.setContentsMargins(0, 0, 0, 0)
    
    window.sidebar_tabs = QTabWidget(window.drawer_widget)
    window.sidebar_tabs.setTabPosition(QTabWidget.TabPosition.North)
    window.sidebar_tabs.tabBar().hide()
    window.sidebar_tabs.setStyleSheet("QTabWidget::pane { border: none; }")
    
    window.sidebar_tabs.addTab(QWidget(window.sidebar_tabs), "Libraries")
    window.sidebar_tabs.addTab(QWidget(window.sidebar_tabs), "Presets")
    window.sidebar_tabs.addTab(QWidget(window.sidebar_tabs), "Notes")
    window.sidebar_tabs.addTab(QWidget(window.sidebar_tabs), "Tools")
    
    window.drawer_ui_layout.addWidget(window.sidebar_tabs)
    window.drawer_widget.setMinimumWidth(200)
    window.drawer_widget.hide()
    
    window.sidebar_splitter.addWidget(window.drawer_widget)
    window.sidebar_splitter.setCollapsible(0, True)
    window.sidebar_splitter.splitterMoved.connect(window._on_sidebar_splitter_moved)

def _setup_navigation_bar(window, right_layout):
    nav_bar_layout = QHBoxLayout()
    nav_bar_layout.setContentsMargins(5, 5, 5, 5)
    nav_bar_layout.setSpacing(5)
    
    nav_btn_style = """
        QPushButton { background-color: #3b3b3b; color: #fff; font-size: 14px; border: 1px solid #555; border-radius: 4px; padding: 2px 6px; }
        QPushButton:hover { background-color: #4a4a4a; border-color: #999; }
        QPushButton:pressed { background-color: #222; padding-top: 4px; padding-left: 8px; }
        QPushButton:disabled { background-color: #222; color: #555; border-color: #333; }
    """
    
    window.btn_back = QPushButton("←", window.content_wrapper)
    window.btn_back.setObjectName("nav_back_btn")
    window.btn_back.setFixedSize(30, 26)
    window.btn_back.setStyleSheet(nav_btn_style)
    window.btn_back.setEnabled(False)
    window.btn_back.clicked.connect(window._navigate_back)
    nav_bar_layout.addWidget(window.btn_back)
    
    window.btn_forward = QPushButton("→", window.content_wrapper)
    window.btn_forward.setObjectName("nav_forward_btn")
    window.btn_forward.setFixedSize(30, 26)
    window.btn_forward.setStyleSheet(nav_btn_style)
    window.btn_forward.setEnabled(False)
    window.btn_forward.clicked.connect(window._navigate_forward)
    nav_bar_layout.addWidget(window.btn_forward)
    
    window.breadcrumb_layout = QHBoxLayout()
    window.breadcrumb_layout.setSpacing(5)
    nav_bar_layout.addLayout(window.breadcrumb_layout)
    
    nav_bar_layout.addStretch()
    
    # Phase 5: Target Switch Buttons (A, B, C) - HIDDEN as per user request for folder-centric design
    target_btn_style = """
        QPushButton { background-color: #3b3b3b; color: #fff; font-weight: bold; border: 1px solid #555; border-radius: 4px; padding: 2px 8px; }
        QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
        QPushButton:checked { background-color: #2980b9; border-color: #3498db; }
    """
    
    window.btn_target_a = QPushButton("A", window.content_wrapper)
    window.btn_target_a.setFixedSize(30, 26)
    window.btn_target_a.setCheckable(True)
    window.btn_target_a.setToolTip(_("Target A (Primary)"))
    window.btn_target_a.setStyleSheet(target_btn_style)
    window.btn_target_a.clicked.connect(lambda: window._switch_target(0))
    # nav_bar_layout.addWidget(window.btn_target_a) # Hidden
    
    window.btn_target_b = QPushButton("B", window.content_wrapper)
    window.btn_target_b.setFixedSize(30, 26)
    window.btn_target_b.setCheckable(True)
    window.btn_target_b.setToolTip(_("Target B (Secondary)"))
    window.btn_target_b.setStyleSheet(target_btn_style)
    window.btn_target_b.clicked.connect(lambda: window._switch_target(1))
    # nav_bar_layout.addWidget(window.btn_target_b) # Hidden
    
    window.btn_target_c = QPushButton("C", window.content_wrapper)
    window.btn_target_c.setFixedSize(30, 26)
    window.btn_target_c.setCheckable(True)
    window.btn_target_c.setToolTip(_("Target C (Tertiary)"))
    window.btn_target_c.setStyleSheet(target_btn_style)
    window.btn_target_c.clicked.connect(lambda: window._switch_target(2))
    # nav_bar_layout.addWidget(window.btn_target_c) # Hidden
    
    window.target_name_lbl = QLabel("", window.content_wrapper)
    window.target_name_lbl.setStyleSheet("color: #aaa; margin: 0 10px; font-size: 11px;")
    # nav_bar_layout.addWidget(window.target_name_lbl) # Hidden
    
    # Hide them explicitly too
    window.btn_target_a.hide()
    window.btn_target_b.hide()
    window.btn_target_c.hide()
    window.target_name_lbl.hide()
    
    # nav_bar_layout.addWidget(QLabel("|", styleSheet="color: #555;")) # Hidden separator
    
    filter_btn_style = """
        QPushButton { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 2px 6px; }
        QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
        QPushButton:pressed { background-color: #222; }
        QPushButton:checked { background-color: #27ae60; border-color: #2ecc71; }
    """
    
    window.btn_filter_favorite = QPushButton("🌟", window.content_wrapper)
    window.btn_filter_favorite.setObjectName("nav_filter_favorite_btn")
    window.btn_filter_favorite.setFixedSize(28, 26)
    window.btn_filter_favorite.setCheckable(True)
    window.btn_filter_favorite.setToolTip(_("Show only folders with favorites"))
    window.btn_filter_favorite.setStyleSheet(filter_btn_style)
    window.btn_filter_favorite.clicked.connect(window._toggle_favorite_filter)
    nav_bar_layout.addWidget(window.btn_filter_favorite)
    
    window.btn_filter_linked = QPushButton("🔗", window.content_wrapper)
    window.btn_filter_linked.setObjectName("nav_filter_linked_btn")
    window.btn_filter_linked.setFixedSize(28, 26)
    window.btn_filter_linked.setCheckable(True)
    window.btn_filter_linked.setToolTip(_("Show only linked folders"))
    window.btn_filter_linked.setStyleSheet(filter_btn_style)
    window.btn_filter_linked.clicked.connect(window._toggle_linked_filter)
    nav_bar_layout.addWidget(window.btn_filter_linked)
    
    window.btn_filter_unlinked = QPushButton("⛓️‍💥", window.content_wrapper)
    window.btn_filter_unlinked.setObjectName("nav_filter_unlinked_btn")
    window.btn_filter_unlinked.setFixedSize(32, 26)
    window.btn_filter_unlinked.setCheckable(True)
    window.btn_filter_unlinked.setToolTip(_("Show only unlinked folders"))
    window.btn_filter_unlinked.setStyleSheet(filter_btn_style)
    window.btn_filter_unlinked.clicked.connect(window._toggle_unlinked_filter)
    nav_bar_layout.addWidget(window.btn_filter_unlinked)
    
    nav_bar_layout.addWidget(QLabel("|", window.content_wrapper, styleSheet="color: #555;"))
    
    unlink_btn_style = """
        QPushButton { background-color: #c0392b; color: #fff; border: 1px solid #e74c3c; border-radius: 4px; padding: 2px 6px; }
        QPushButton:hover { background-color: #e74c3c; border-color: #fff; }
        QPushButton:pressed { background-color: #922b21; }
    """
    window.btn_unlink_all = QPushButton("🔓", window.content_wrapper)
    window.btn_unlink_all.setObjectName("nav_unlink_all_btn")
    window.btn_unlink_all.setFixedSize(28, 26)
    window.btn_unlink_all.setToolTip(_("Unlink All Active Links"))
    window.btn_unlink_all.setStyleSheet(unlink_btn_style)
    window.btn_unlink_all.clicked.connect(window._unload_active_links)
    nav_bar_layout.addWidget(window.btn_unlink_all)
    
    nav_bar_layout.addWidget(QLabel("|", window.content_wrapper, styleSheet="color: #555;"))
    
    window.btn_trash = QPushButton("🗑", window.content_wrapper)
    window.btn_trash.setObjectName("nav_trash_btn")
    window.btn_trash.setFixedSize(28, 26)
    window.btn_trash.setToolTip(_("Open Trash"))
    window.btn_trash.setStyleSheet(filter_btn_style)
    window.btn_trash.clicked.connect(window._open_trash_view)
    nav_bar_layout.addWidget(window.btn_trash)
    
    right_layout.addLayout(nav_bar_layout)

def _setup_main_card_view(window, right_layout):
    window.v_splitter = QSplitter(Qt.Orientation.Vertical, window.sidebar_splitter)
    
    btn_style = """
        QPushButton { background-color: #3b3b3b; color: #fff; font-size: 14px; border: 1px solid #555; border-radius: 4px; padding: 2px 6px; }
        QPushButton:hover { background-color: #4a4a4a; border-color: #999; }
        QPushButton:pressed { background-color: #222; padding-top: 4px; padding-left: 8px; }
    """
    btn_selected = """
        QPushButton { background-color: #27ae60; color: #fff; font-size: 14px; border: 1px solid #2ecc71; border-radius: 4px; padding: 2px 6px; }
        QPushButton:hover { background-color: #2ecc71; border-color: #fff; }
        QPushButton:pressed { background-color: #1e8449; padding-top: 4px; padding-left: 8px; }
    """
    btn_default = """
        QPushButton { background-color: #2980b9; color: #fff; font-size: 14px; border: 1px solid #3498db; border-radius: 4px; padding: 2px 6px; }
        QPushButton:hover { background-color: #3498db; border-color: #fff; }
        QPushButton:pressed { background-color: #1a5276; padding-top: 4px; padding-left: 8px; }
    """
    
    # Categories Area
    cat_group = QWidget(window.v_splitter)
    cat_group_layout = QVBoxLayout(cat_group)
    cat_group_layout.setContentsMargins(0, 0, 0, 0)
    
    cat_header = QHBoxLayout()
    cat_header.setContentsMargins(5, 5, 5, 5)
    cat_header.setSpacing(8)
    
    window.btn_import_cat = QPushButton("📁", cat_group)
    window.btn_import_cat.setObjectName("cat_import_btn")
    window.btn_import_cat.setFixedSize(30, 26)
    window.btn_import_cat.setToolTip(_("Import Folder or Zip to Categories"))
    window.btn_import_cat.setStyleSheet(btn_style)
    window.btn_import_cat.clicked.connect(lambda: window._open_import_dialog("category"))
    cat_header.addWidget(window.btn_import_cat)
    
    window.cat_title_lbl = QLabel(_("<b>Categories</b>"), cat_group, styleSheet="color: #fff;")
    cat_header.addWidget(window.cat_title_lbl)
    window.cat_result_label = QLabel("", cat_group, styleSheet="color: #27ae60; font-weight: bold;")
    cat_header.addWidget(window.cat_result_label)
    cat_header.addStretch()
    
    from src.ui.title_bar_button import TitleBarButton
    window.btn_cat_text = TitleBarButton("T", cat_group, is_toggle=True)
    window.btn_cat_text.setObjectName("cat_mode_text_btn")
    window.btn_cat_text.setFixedSize(36, 26)
    window.btn_cat_text.clicked.connect(lambda: window._toggle_cat_display_mode("text_list"))
    cat_header.addWidget(window.btn_cat_text)
    
    window.btn_cat_image = TitleBarButton("🖼", cat_group, is_toggle=True)
    window.btn_cat_image.setObjectName("cat_mode_image_btn")
    window.btn_cat_image.setFixedSize(36, 26)
    window.btn_cat_image.clicked.connect(lambda: window._toggle_cat_display_mode("mini_image"))
    cat_header.addWidget(window.btn_cat_image)
    
    window.btn_cat_both = TitleBarButton("🖼T", cat_group, is_toggle=True)
    window.btn_cat_both.setObjectName("cat_mode_combined_btn")
    window.btn_cat_both.setFixedSize(44, 26)
    window.btn_cat_both.clicked.connect(lambda: window._toggle_cat_display_mode("image_text"))
    cat_header.addWidget(window.btn_cat_both)
    
    cat_header.addWidget(QLabel("|", cat_group, styleSheet="color: #555;"))
    
    window.btn_show_hidden = QPushButton("＝", cat_group)
    window.btn_show_hidden.setObjectName("cat_show_hidden_btn")
    window.btn_show_hidden.setFixedSize(28, 26)
    window.btn_show_hidden.setToolTip(_("Show/Hide hidden folders"))
    window.btn_show_hidden.setStyleSheet(btn_style)
    window.btn_show_hidden.clicked.connect(window._toggle_show_hidden)
    cat_header.addWidget(window.btn_show_hidden)
    
    cat_header.addWidget(QLabel("|", cat_group, styleSheet="color: #555;"))
    
    window.btn_card_settings = QPushButton("📓", cat_group)
    window.btn_card_settings.setObjectName("cat_card_settings_btn")
    window.btn_card_settings.setFixedSize(28, 26)
    window.btn_card_settings.setToolTip(_("Card Size Settings"))
    window.btn_card_settings.setStyleSheet(btn_style)
    window.btn_card_settings.clicked.connect(window._show_settings_menu)
    cat_header.addWidget(window.btn_card_settings)
    
    window.btn_quick_manage = QPushButton("⚡", cat_group)
    window.btn_quick_manage.setObjectName("cat_quick_manage_btn")
    window.btn_quick_manage.setFixedSize(28, 26)
    window.btn_quick_manage.setToolTip(_("Quick View Manager (Bulk Edit Visible Folders)"))
    window.btn_quick_manage.setStyleSheet(btn_style)
    window.btn_quick_manage.clicked.connect(window._open_quick_view_manager)
    cat_header.addWidget(window.btn_quick_manage)
    
    cat_group_layout.addLayout(cat_header)
    
    window.cat_container = QWidget(cat_group)
    window.cat_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.cat_container.customContextMenuRequested.connect(window._show_cat_context_menu)
    window.cat_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
    window.cat_layout = FlowLayout(window.cat_container, margin=10, spacing=10)
    window.cat_scroll = QScrollArea(cat_group)
    window.cat_scroll.setWindowFlags(Qt.WindowType.Widget)
    window.cat_scroll.setWidgetResizable(True)
    window.cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    window.cat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    window.cat_scroll.setFrameShape(QFrame.Shape.NoFrame)
    window.cat_scroll.setStyleSheet("background: transparent;")
    window.cat_scroll.setWidget(window.cat_container)
    window.cat_scroll.setMinimumHeight(50)
    cat_group_layout.addWidget(window.cat_scroll)
    
    # Packages Area
    pkg_group = QWidget(window.v_splitter)
    pkg_group_layout = QVBoxLayout(pkg_group)
    pkg_group_layout.setContentsMargins(0, 0, 0, 0)
    
    pkg_header = QHBoxLayout()
    pkg_header.setContentsMargins(5, 5, 5, 5)
    pkg_header.setSpacing(8)
    
    window.btn_import_pkg = QPushButton("📁", pkg_group)
    window.btn_import_pkg.setObjectName("pkg_import_btn")
    window.btn_import_pkg.setFixedSize(30, 26)
    window.btn_import_pkg.setToolTip(_("Import Folder or Zip to Packages"))
    window.btn_import_pkg.setStyleSheet(btn_style)
    window.btn_import_pkg.clicked.connect(lambda: window._open_import_dialog("package"))
    pkg_header.addWidget(window.btn_import_pkg)
    
    window.pkg_title_lbl = QLabel(_("<b>Packages</b>"), pkg_group, styleSheet="color: #fff;")
    pkg_header.addWidget(window.pkg_title_lbl)
    
    window.total_link_count_label = QLabel(_("Total Links: 0"), pkg_group, styleSheet="color: #3498db; font-weight: bold;")
    pkg_header.addWidget(window.total_link_count_label)
    
    pkg_header.addWidget(QLabel("|", pkg_group, styleSheet="color: #555;"))
    
    window.pkg_link_count_label = QLabel("", pkg_group, styleSheet="color: #27ae60; font-weight: bold;")
    pkg_header.addWidget(window.pkg_link_count_label)
    
    window.pkg_result_label = QLabel("", pkg_group, styleSheet="color: #fff;")
    pkg_header.addWidget(window.pkg_result_label)
    
    pkg_header.addStretch()
    
    pkg_header.addWidget(QLabel("|", pkg_group, styleSheet="color: #555;"))
    
    window.btn_pkg_text = TitleBarButton("T", pkg_group, is_toggle=True)
    window.btn_pkg_text.setObjectName("pkg_mode_text_btn")
    window.btn_pkg_text.setFixedSize(36, 26)
    window.btn_pkg_text.clicked.connect(lambda: window._toggle_pkg_display_mode("text_list"))
    pkg_header.addWidget(window.btn_pkg_text)
    
    window.btn_pkg_image = TitleBarButton("🖼", pkg_group, is_toggle=True)
    window.btn_pkg_image.setObjectName("pkg_mode_image_btn")
    window.btn_pkg_image.setFixedSize(36, 26)
    window.btn_pkg_image.clicked.connect(lambda: window._toggle_pkg_display_mode("mini_image"))
    pkg_header.addWidget(window.btn_pkg_image)
    
    window.btn_pkg_image_text = TitleBarButton("🖼T", pkg_group, is_toggle=True)
    window.btn_pkg_image_text.setObjectName("pkg_mode_combined_btn")
    window.btn_pkg_image_text.setFixedSize(44, 26)
    window.btn_pkg_image_text.clicked.connect(lambda: window._toggle_pkg_display_mode("image_text"))
    pkg_header.addWidget(window.btn_pkg_image_text)
    
    pkg_group_layout.addLayout(pkg_header)
    
    window.pkg_container = QWidget(pkg_group)
    window.pkg_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.pkg_container.customContextMenuRequested.connect(window._show_pkg_context_menu)
    window.pkg_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
    window.pkg_layout = FlowLayout(window.pkg_container, margin=10, spacing=10)
    window.pkg_scroll = QScrollArea(pkg_group)
    window.pkg_scroll.setWindowFlags(Qt.WindowType.Widget)
    window.pkg_scroll.setWidgetResizable(True)
    window.pkg_scroll.setWidget(window.pkg_container)
    pkg_group_layout.addWidget(window.pkg_scroll)
    
    window.v_splitter.addWidget(cat_group)
    window.v_splitter.addWidget(pkg_group)
    
    saved_cat_height = window.registry.get_global("category_view_height", 200)
    window._category_fixed_height = saved_cat_height
    window.v_splitter.setSizes([saved_cat_height, 400])
    window.v_splitter.setStretchFactor(0, 0)
    window.v_splitter.setStretchFactor(1, 1)
    window.v_splitter.splitterMoved.connect(window._on_splitter_moved)
    
    right_layout.addWidget(window.v_splitter, 1)

def _setup_floating_explorer(window):
    window.explorer_panel = ExplorerPanel(window)
    window.explorer_panel.path_selected.connect(lambda p: window._handle_tree_navigation(p, is_double_click=True))
    window.explorer_panel.item_clicked.connect(lambda p: window._handle_tree_navigation(p, is_double_click=False))
    window.explorer_panel.context_menu_provider = window._create_item_context_menu
    window.explorer_panel.config_changed.connect(window._refresh_current_view)
    window.explorer_panel.request_properties_edit.connect(window._handle_explorer_properties_edit)
    window.explorer_panel.width_changed.connect(window._on_explorer_panel_width_changed)
    window.explorer_panel.hide()
    window.explorer_panel.setStyleSheet("background-color: #2b2b2b; border-right: 1px solid #444;")
