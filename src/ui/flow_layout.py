""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QLayout, QSizePolicy
from PyQt6.QtCore import Qt, QRect, QPoint, QSize

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
        self._batch_mode = False
        self._spacing_cache = {}

    def setBatchMode(self, enabled: bool):
        """Phase 1.0.7: Toggle batch mode to skip doLayout during bulk additions."""
        if self._batch_mode == enabled:
            return
        self._batch_mode = enabled
        if not enabled:
            self.invalidate()

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        if not self._batch_mode:
            self.doLayout(rect, False)

    def sizeHint(self):
        # Return size needed to show all items in one row as a hint
        width = 0
        height = 0
        for item in self.itemList:
            width += item.sizeHint().width() + self.spacing()
            height = max(height, item.sizeHint().height())
        
        left, top, right, bottom = self.getContentsMargins()
        return QSize(width + left + right, height + top + bottom)

    def minimumSize(self):
        # Return size of largest item
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()
        
        for item in self.itemList:
            wid = item.widget()
            # Phase 28: Skip hidden widgets so they don't take up space
            if wid is None or not wid.isVisible():
                continue
                
            # Optimized: Cache layout spacing lookups
            style = wid.style()
            cache_key = (style, QSizePolicy.ControlType.PushButton) # Buttons are mostly used
            if cache_key not in self._spacing_cache:
                sx = style.layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Horizontal)
                sy = style.layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Vertical)
                self._spacing_cache[cache_key] = (sx, sy)
            
            sx, sy = self._spacing_cache[cache_key]
            spaceX = spacing + sx
            spaceY = spacing + sy
            
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            
            if not testOnly:
                new_rect = QRect(QPoint(x, y), item.sizeHint())
                if wid.geometry() != new_rect:
                    item.setGeometry(new_rect)
            
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
            
        return y + lineHeight - rect.y()
