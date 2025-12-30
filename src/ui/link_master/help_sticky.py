from PyQt6.QtWidgets import QWidget, QTextEdit, QVBoxLayout, QMenu, QColorDialog, QApplication
from src.core.lang_manager import _
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal, QEvent, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPolygon, QPen, QBrush, QPainterPath, QPolygonF, QMouseEvent
import math

class StickyHelpWidget(QWidget):
    """
    ユーザーが自由に配置できる付箋型ヘルプウィジェット。
    """
    closed = pyqtSignal()
    data_changed = pyqtSignal()

    def __init__(self, element_id, target_widget, parent=None):
        super().__init__(None) # ウィンドウとして独立（親を持つとクリッピングされるため）
        self.element_id = element_id
        self.target_widget = target_widget
        self.parent_window = parent # 座標計算のための参照

        # 基本フラグ
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 状態管理
        self.is_edit_mode = False
        self.bg_color = QColor(40, 40, 40, 200)
        self.text_color = QColor(255, 255, 255, 255)
        self.text_content = _("Help text here...")
        
        # 幾何学データ (相対座標)
        self.offset = QPoint(50, 50) # ターゲットの中心からの本体のズレ
        self.tail_target_offset = QPoint(0, 0) # 本体中心からのしっぽ先端の相対位置
        
        # ドラッグ用
        self._dragging_body = False
        self._dragging_tail = False
        self._resizing_body = False
        self._forwarding_event = False # ループ防止フラグ
        self._drag_start_pos = QPoint()
        self._start_body_size = QSize()
        
        # アンカーモード: 0=比例(Center), 1=固定(TopLeft), 2=追従(Full/Delta)
        self.anchor_mode = 0 # 0=Center, 1=TopLeft, 2=BottomRight/Full
        
        # UI
        self._init_ui()
        self.resize(150, 80)
        
    def _init_ui(self):
        # レイアウトは使わず、手動でQTextEditの位置を管理する
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(self.text_content)
        self._update_text_style()
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.installEventFilter(self)
        
        # 本体の標準サイズ (to_dict/from_dictで保存される)
        self.body_size = QSize(160, 40)
        self.set_edit_mode(False)

    def _update_text_style(self):
        rgba_str = f"rgba({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()}, {self.text_color.alpha()})"
        self.text_edit.setStyleSheet(f"background: transparent; border: none; color: {rgba_str};")

    def set_edit_mode(self, enabled):
        self.is_edit_mode = enabled
        if enabled:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
            self.text_edit.setReadOnly(False)
            # エディットモードでも最初はマウスを透過させ、背後のWidget(自分自身)でドラッグを拾えるようにする
            # ただし、ダブルクリックで入力を有効にする
            self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            self.text_edit.setReadOnly(True)
            self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            
        self.update()
        if self.isVisible():
            self.show()

    def update_position(self):
        """ターゲットに合わせて、本体とアンカーの両方を覆うサイズに自身のウィンドウを広げて移動する。"""
        if not self.target_widget or not self.parent_window:
            return
            
        # 1. 基準点の計算
        target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
        
        if self.anchor_mode == 1: # TopLeft 固定
            base_g = target_global
        elif self.anchor_mode == 2: # BottomRight / Window相対 (サイズ変更と同じ量移動)
            # ターゲットの右下を基準にする
            base_g = target_global + QPoint(self.target_widget.width(), self.target_widget.height())
        else: # 0 = Center (比例)
            center_x = target_global.x() + self.target_widget.width() // 2
            center_y = target_global.y() + self.target_widget.height() // 2
            base_g = QPoint(center_x, center_y)
            
        # 本体の中心（グローバル）を計算
        body_center_g = base_g + self.offset
        
        # 2. しっぽの先端（グローバル）を計算
        tail_tip_g = body_center_g + self.tail_target_offset
        
        # 3. 本体の矩形（グローバル）
        body_rect_g = QRect(body_center_g.x() - self.body_size.width() // 2,
                            body_center_g.y() - self.body_size.height() // 2,
                            self.body_size.width(), self.body_size.height())
        
        # 4. ウィンドウ全体の矩形（グローバル）: 本体としっぽの先端の両方を含む必要がある
        margin = 30 # ハンドル等のために少し余裕を持たせる
        widget_rect_g = body_rect_g.united(QRect(tail_tip_g, QSize(1,1))).adjusted(-margin, -margin, margin, margin)
        
        # ジオメトリ更新
        self.setGeometry(widget_rect_g)
        
        # 5. 子要素のテキストエディタを本体部分に配置（ローカル座標）
        # mapFromGlobal is avoided here to ensure accurate positioning even when the widget is hidden.
        local_body_topLeft = body_rect_g.topLeft() - widget_rect_g.topLeft()
        body_local = QRect(local_body_topLeft, self.body_size)
        self.text_edit.setGeometry(body_local.adjusted(4, 4, -4, -4))
        self.update()

    def _on_text_changed(self):
        self.text_content = self.text_edit.toPlainText()
        self.data_changed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 本体の中心（ローカル座標）
        target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
        
        if self.anchor_mode == 1:
            base_g = target_global
        elif self.anchor_mode == 2:
            base_g = target_global + QPoint(self.target_widget.width(), self.target_widget.height())
        else:
            center_x = target_global.x() + self.target_widget.width() // 2
            center_y = target_global.y() + self.target_widget.height() // 2
            base_g = QPoint(center_x, center_y)
            
        body_center_g = base_g + self.offset
        
        # Calculate local positions mathematically to avoid mapFromGlobal reliability issues
        widget_topLeft = self.geometry().topLeft()
        local_body_center = body_center_g - widget_topLeft
        tail_tip = (body_center_g + self.tail_target_offset) - widget_topLeft
        
        body_rect = QRectF(local_body_center.x() - self.body_size.width() / 2,
                           local_body_center.y() - self.body_size.height() / 2,
                           self.body_size.width(), self.body_size.height())
        
        body_path = QPainterPath()
        body_path.addRoundedRect(body_rect, 8, 8)
        
        dx = tail_tip.x() - local_body_center.x()
        dy = tail_tip.y() - local_body_center.y()
        base_width = 25
        margin_edge = 10
        
        if abs(dx) > abs(dy):
            bx = body_rect.left() if dx < 0 else body_rect.right()
            by = max(body_rect.top() + margin_edge + base_width/2, 
                     min(body_rect.bottom() - margin_edge - base_width/2, tail_tip.y()))
            p1 = QPointF(bx, by - base_width / 2)
            p2 = QPointF(bx, by + base_width / 2)
        else:
            by = body_rect.top() if dy < 0 else body_rect.bottom()
            bx = max(body_rect.left() + margin_edge + base_width/2, 
                     min(body_rect.right() - margin_edge - base_width/2, tail_tip.x()))
            p1 = QPointF(bx - base_width / 2, by)
            p2 = QPointF(bx + base_width / 2, by)

        dist = math.sqrt(dx*dx + dy*dy)
        if dist > 0:
            tail_path = QPainterPath()
            tail_poly = QPolygonF([p1, p2, QPointF(tail_tip)])
            tail_path.addPolygon(tail_poly)
            merged_path = body_path.united(tail_path)
        else:
            merged_path = body_path

        painter.setBrush(QBrush(self.bg_color))
        if self.is_edit_mode:
            painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        
        painter.drawPath(merged_path)
        
        if self.is_edit_mode:
            # 尻尾先端のアンカー
            painter.setBrush(QBrush(QColor(255, 0, 0, 200)))
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawEllipse(tail_tip, 8, 8)
            
            # リサイズハンドル（右下）
            handle_size = 12
            handle_rect = QRectF(body_rect.right() - handle_size, body_rect.bottom() - handle_size, handle_size, handle_size)
            painter.setBrush(QBrush(QColor(255, 255, 255, 100)))
            painter.setPen(Qt.PenStyle.NoPen)
            # 斜め線の装飾
            for i in range(3):
                offset = i * 4
                painter.drawLine(QPointF(handle_rect.right() - offset, handle_rect.bottom()),
                                 QPointF(handle_rect.right(), handle_rect.bottom() - offset))

    def eventFilter(self, obj, event):
        if obj == self.text_edit and event.type() == QEvent.Type.FocusOut:
            if self.is_edit_mode:
                self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if self._forwarding_event:
            return
            
        if not self.is_edit_mode:
            super().mousePressEvent(event)
            return
            
        target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
        
        if self.anchor_mode == 1:
            base_g = target_global
        elif self.anchor_mode == 2:
            base_g = target_global + QPoint(self.target_widget.width(), self.target_widget.height())
        else:
            center_x = target_global.x() + self.target_widget.width() // 2
            center_y = target_global.y() + self.target_widget.height() // 2
            base_g = QPoint(center_x, center_y)
            
        body_center_g = base_g + self.offset
        
        widget_topLeft = self.geometry().topLeft()
        local_body_center = body_center_g - widget_topLeft
        tail_tip = (body_center_g + self.tail_target_offset) - widget_topLeft
        local_pos = event.pos()
        
        # 1. アンカー（尻尾先端）チェック
        if (local_pos - tail_tip).manhattanLength() < 25:
            self._dragging_tail = True
            self._drag_start_pos = event.globalPosition().toPoint()
            event.accept()
            return

        body_rect = QRect(local_body_center.x() - self.body_size.width() // 2,
                          local_body_center.y() - self.body_size.height() // 2,
                          self.body_size.width(), self.body_size.height())
        
        # 2. リサイズハンドル（右下）チェック
        handle_size = 20 # 判定は広めにする
        resize_rect = QRect(body_rect.right() - handle_size, body_rect.bottom() - handle_size, handle_size, handle_size)
        if resize_rect.contains(local_pos):
            self._resizing_body = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._start_body_size = self.body_size
            event.accept()
            return

        # 3. 本体（中央）チェック
        if body_rect.contains(local_pos):
            if event.button() == Qt.MouseButton.LeftButton:
                # 枠に近いところ（外周15px）を触った場合は移動、内側は編集フォーカス
                edge_margin = 15
                if (local_pos.x() < body_rect.left() + edge_margin or 
                    local_pos.x() > body_rect.right() - edge_margin or
                    local_pos.y() < body_rect.top() + edge_margin or
                    local_pos.y() > body_rect.bottom() - edge_margin):
                    
                    self._dragging_body = True
                    self._drag_start_pos = event.globalPosition().toPoint()
                    event.accept()
                else:
                    # 内側クリック: 即座にテキスト編集を有効にする
                    self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
                    self.text_edit.setFocus()
                    # イベントを自分（text_edit）に振り向ける
                    local_pos_f = QPointF(self.text_edit.mapFromGlobal(event.globalPosition().toPoint()))
                    new_event = QMouseEvent(event.type(), local_pos_f, 
                                            event.button(), event.buttons(), event.modifiers())
                    self._forwarding_event = True
                    try:
                        QApplication.sendEvent(self.text_edit, new_event)
                    finally:
                        self._forwarding_event = False
            elif event.button() == Qt.MouseButton.RightButton:
                self._show_context_menu(event.globalPosition().toPoint())
                event.accept()

    def mouseMoveEvent(self, event):
        if not self.is_edit_mode:
            return
            
        if self._resizing_body:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_w = max(80, self._start_body_size.width() + delta.x())
            new_h = max(20, self._start_body_size.height() + delta.y())
            self.body_size = QSize(new_w, new_h)
            self.update_position()
            self.data_changed.emit()
            
        elif self._dragging_body:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            self.offset += delta
            self._drag_start_pos = event.globalPosition().toPoint()
            self.update_position()
            self.data_changed.emit()
            
        elif self._dragging_tail:
            # 本体の中心（グローバル）を基準にオフセットを再計算
            target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
            
            if self.anchor_mode == 1:
                base_g = target_global
            elif self.anchor_mode == 2:
                base_g = target_global + QPoint(self.target_widget.width(), self.target_widget.height())
            else:
                center_x = target_global.x() + self.target_widget.width() // 2
                center_y = target_global.y() + self.target_widget.height() // 2
                base_g = QPoint(center_x, center_y)
                
            body_center_g = base_g + self.offset
            
            # 新しいオフセット = マウスのグローバル位置 - 本体のグローバル中心
            self.tail_target_offset = event.globalPosition().toPoint() - body_center_g
            self.update_position()
            self.data_changed.emit()

    def mouseReleaseEvent(self, event):
        self._dragging_body = False
        self._dragging_tail = False
        self._resizing_body = False

    def mouseDoubleClickEvent(self, event):
        """ダブルクリックでも編集モードに入れる（内側シングルクリックでも入れるようになったのでバックアップ的役割）"""
        if self.is_edit_mode:
            self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.text_edit.setFocus()
            event.accept()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        
        reset_anchor_action = menu.addAction(_("Reset Anchor (Jump Out)"))
        
        mode_menu = menu.addMenu(_("Follow Mode"))
        m0 = mode_menu.addAction(_("Proportional (Center)"))
        m1 = mode_menu.addAction(_("Fixed (Top-Left)"))
        m2 = mode_menu.addAction(_("Full Follow (Size Delta)"))
        
        change_bg_action = menu.addAction(_("Change Background Color"))
        change_text_action = menu.addAction(_("Change Text Color"))
        
        menu.addSeparator()
        delete_action = menu.addAction(_("Delete (Clear Content)"))
        
        action = menu.exec(pos)
        if action == reset_anchor_action:
            # アンカーを本体の右側に飛ばす
            self.tail_target_offset = QPoint(self.body_size.width() // 2 + 50, 0)
            self.update_position()
            self.data_changed.emit()
        elif action == m0:
            self.anchor_mode = 0
            self._recalc_offset_after_mode_change()
            self.data_changed.emit()
        elif action == m1:
            self.anchor_mode = 1
            self._recalc_offset_after_mode_change()
            self.data_changed.emit()
        elif action == m2:
            self.anchor_mode = 2
            self._recalc_offset_after_mode_change()
            self.data_changed.emit()
        elif action == change_bg_action:
            color = QColorDialog.getColor(self.bg_color, self, _("Select Background Color"), QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if color.isValid():
                self.bg_color = color
                self.update()
                self.data_changed.emit()
        elif action == change_text_action:
            color = QColorDialog.getColor(self.text_color, self, _("Select Text Color"), QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if color.isValid():
                self.text_color = color
                self._update_text_style()
                self.data_changed.emit()
        elif action == delete_action:
            self.text_edit.clear()

    def _recalc_offset_after_mode_change(self):
        """モード変更時に見た目の位置が変わらないように offset を再計算する。"""
        if not self.target_widget: return
        
        # 現在のグローバル位置を取得
        target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
        
        # 現在の「本体中心グリッド」を以前のモード計算で出す
        # (すでに update_position で計算されているはずだが、正確を期すため self.offset はそのまま使い、
        # 逆算して新しいオフセットを求める)
        
        # 現在の本体中心(Global)
        current_rect_g = self.geometry().adjusted(30, 30, -30, -30) # margin=30
        current_body_center_g = current_rect_g.center()
        
        if self.anchor_mode == 1: # 新しいモードが TopLeft
            new_base_g = target_global
        elif self.anchor_mode == 2: # 新しいモードが BottomRight
            new_base_g = target_global + QPoint(self.target_widget.width(), self.target_widget.height())
        else: # 0 = Center
            center_x = target_global.x() + self.target_widget.width() // 2
            center_y = target_global.y() + self.target_widget.height() // 2
            new_base_g = QPoint(center_x, center_y)
            
        self.offset = current_body_center_g - new_base_g
        self.update_position()

    def to_dict(self):
        return {
            "body_size": [self.body_size.width(), self.body_size.height()],
            "offset": [self.offset.x(), self.offset.y()],
            "tail_target": [self.tail_target_offset.x(), self.tail_target_offset.y()],
            "bg_style": self.bg_color.rgba(),
            "text_style": self.text_color.rgba(),
            "content": self.text_content,
            "anchor_mode": self.anchor_mode
        }

    def from_dict(self, data):
        if "body_size" in data:
            self.body_size = QSize(data["body_size"][0], data["body_size"][1])
        if "offset" in data:
            self.offset = QPoint(data["offset"][0], data["offset"][1])
        if "tail_target" in data:
            self.tail_target_offset = QPoint(data["tail_target"][0], data["tail_target"][1])
        if "bg_style" in data:
            self.bg_color = QColor.fromRgba(data["bg_style"])
        elif "style" in data: # Legacy support
            self.bg_color = QColor.fromRgba(data["style"])
        if "text_style" in data:
            self.text_color = QColor.fromRgba(data["text_style"])
            self._update_text_style()
        if "content" in data:
            self.text_content = data["content"]
        if "anchor_mode" in data:
            self.anchor_mode = data["anchor_mode"]
        
        self.text_edit.setPlainText(self.text_content)
        self.update_position()
