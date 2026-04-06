from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QSlider, QSizePolicy
)


class ColorSquare(QWidget):
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(14, 14)

    def paintEvent(self, event):
        if not self.color:
            return
        painter = QPainter(self)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(Qt.black)
        painter.setBrush(QColor(self.color))
        painter.drawRect(rect)


class SliderRow(QWidget):
    value_changed = Signal(int)

    def __init__(self, name, value=0, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(name)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(value)
        self.value_label = QLabel(str(value))
        self.value_label.setFixedWidth(30)

        self.slider.valueChanged.connect(
            lambda v: self.value_label.setText(str(v))
        )
        self.slider.valueChanged.connect(self.value_changed)

        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)


class ListItemWidget(QWidget):
    clicked = Signal(object)
    remove_clicked = Signal(object)

    def __init__(self, text, item_id, color=None, slider_values=(20, 50, 80), parent=None):
        super().__init__(parent)
        self.item_id = item_id

        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 4)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        if color:
            self.icon_widget = ColorSquare(color)
        else:
            self.icon_widget = QWidget()
            self.icon_widget.setFixedWidth(14)

        self.label = QLabel(text)

        self.remove_button = QToolButton()
        self.remove_button.setText("×")
        self.remove_button.setAutoRaise(True)
        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self.item_id))

        top_row.addWidget(self.icon_widget)
        top_row.addWidget(self.label, 1)
        top_row.addWidget(self.remove_button)

        outer.addLayout(top_row)

        self.sliders_container = QWidget()
        sliders_layout = QVBoxLayout(self.sliders_container)
        sliders_layout.setContentsMargins(22, 0, 0, 0)
        sliders_layout.setSpacing(4)

        self.slider1 = SliderRow("Slider 1", slider_values[0])
        self.slider2 = SliderRow("Slider 2", slider_values[1])
        self.slider3 = SliderRow("Slider 3", slider_values[2])

        sliders_layout.addWidget(self.slider1)
        sliders_layout.addWidget(self.slider2)
        sliders_layout.addWidget(self.slider3)

        outer.addWidget(self.sliders_container)
        self.sliders_container.hide()

        self._selected = False
        self.update_style()

    def set_selected(self, selected):
        self._selected = selected
        self.sliders_container.setVisible(selected)
        self.update_style()
        self.adjustSize()

    def update_style(self):
        if self._selected:
            self.setStyleSheet("""
                ListItemWidget {
                    background: palette(highlight);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                }
                QLabel {
                    color: palette(highlighted-text);
                }
            """)
        else:
            self.setStyleSheet("""
                ListItemWidget {
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                }
            """)

    def mousePressEvent(self, event):
        if not self.remove_button.geometry().contains(event.pos()):
            self.clicked.emit(self.item_id)
        super().mousePressEvent(event)


class StaticItemList(QWidget):
    selection_changed = Signal(object)
    item_removed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

        self.items = {}
        self.current_id = None

    def add_item(self, text, item_id, color=None, slider_values=(20, 50, 80)):
        widget = ListItemWidget(text, item_id, color, slider_values)
        widget.clicked.connect(self.select_item)
        widget.remove_clicked.connect(self.remove_item)

        self.layout.addWidget(widget)
        self.items[item_id] = widget

    def select_item(self, item_id):
        if self.current_id == item_id:
            self.clear_selection()
            return

        if self.current_id is not None and self.current_id in self.items:
            self.items[self.current_id].set_selected(False)

        self.current_id = item_id
        self.items[item_id].set_selected(True)
        self.selection_changed.emit(item_id)

    def clear_selection(self):
        if self.current_id is not None and self.current_id in self.items:
            self.items[self.current_id].set_selected(False)
        self.current_id = None
        self.selection_changed.emit(None)

    def remove_item(self, item_id):
        widget = self.items.pop(item_id, None)
        if not widget:
            return

        if self.current_id == item_id:
            self.current_id = None
            self.selection_changed.emit(None)

        self.layout.removeWidget(widget)
        widget.deleteLater()
        self.item_removed.emit(item_id)


if __name__ == "__main__":
    app = QApplication([])

    window = QWidget()
    root = QVBoxLayout(window)

    item_list = StaticItemList()
    item_list.add_item("Red item", "red", "#ff4d4d", (10, 30, 50))
    item_list.add_item("Green item", "green", "#55cc66", (20, 40, 60))
    item_list.add_item("Blue item", "blue", "#4d88ff", (70, 80, 90))

    root.addWidget(item_list)

    window.resize(450, 300)
    window.show()
    app.exec()
