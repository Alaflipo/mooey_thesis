from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QWidget, QListWidget, QListWidgetItem, QHBoxLayout,
    QVBoxLayout, QLabel, QToolButton
)


class ColorDot(QWidget):
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(14, 14)

    def paintEvent(self, event):
        if not self.color:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.black)
        painter.setBrush(QColor(self.color))
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)


class ListItemWidget(QWidget):
    remove_clicked = Signal(object)

    def __init__(self, text, item_id, color=None, parent=None):
        super().__init__(parent)
        self.item_id = item_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(8)

        if color:
            self.icon_widget = ColorDot(color)
        else:
            self.icon_widget = QWidget()
            self.icon_widget.setFixedWidth(14)

        self.label = QLabel(text)

        self.remove_button = QToolButton()
        self.remove_button.setText("×")
        self.remove_button.setAutoRaise(True)
        self.remove_button.clicked.connect(
            lambda: self.remove_clicked.emit(self.item_id)
        )

        layout.addWidget(self.icon_widget)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.remove_button)


class SelectableItemList(QListWidget):
    item_removed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setUniformItemSizes(False)

    def add_entry(self, text, item_id, color=None):
        list_item = QListWidgetItem(self)
        widget = ListItemWidget(text, item_id, color)

        list_item.setSizeHint(widget.sizeHint())
        self.addItem(list_item)
        self.setItemWidget(list_item, widget)

        widget.remove_clicked.connect(self.remove_entry)

    def remove_entry(self, item_id):
        for row in range(self.count()):
            list_item = self.item(row)
            widget = self.itemWidget(list_item)
            if widget and widget.item_id == item_id:
                self.takeItem(row)
                self.item_removed.emit(item_id)
                return

    def clear_current_selection(self):
        self.clearSelection()
        self.setCurrentItem(None)


if __name__ == "__main__":
    app = QApplication([])

    window = QWidget()
    layout = QVBoxLayout(window)

    item_list = SelectableItemList()
    item_list.add_entry("Red item", "red", "#ff4d4d")
    item_list.add_entry("Green item", "green", "#55cc66")
    item_list.add_entry("Blue item", "blue", "#4d88ff")
    item_list.add_entry("No color item", "plain", None)

    item_list.item_removed.connect(lambda item_id: print("Removed:", item_id))
    item_list.itemSelectionChanged.connect(
        lambda: print(
            "Selected:",
            item_list.itemWidget(item_list.currentItem()).item_id
            if item_list.currentItem() else None
        )
    )

    layout.addWidget(item_list)

    window.resize(320, 220)
    window.show()
    app.exec()
