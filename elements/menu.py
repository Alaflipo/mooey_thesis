from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QLabel, QCheckBox, QMessageBox, QDialog, QSlider, QWidgetAction
from PySide6.QtGui import Qt, QAction, QKeySequence

import datetime

from elements.canvas import Canvas
from elements.bend_dialog import BendPenaltyDialog

import helpers.port_assign as port_assign 
import helpers.layout as layout

from io_management.fileformat_loom import export_loom, render_loom

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mooey")
        self.setMinimumSize(1280, 720)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        button_layout = QVBoxLayout()
        button_layout.setAlignment(Qt.AlignTop)
        layout.addLayout(button_layout)
        
        self.canvas = Canvas()
        
        self.construct_sidebar(button_layout)
        self.construct_menubar()
        
        layout.addWidget(self.canvas)

        # TODO: add history stuff 
        self.canvas.history_checkpoint( "Initial drawing" )
        self.canvas.update_history_actions()

        # Control variables
        self.label_strength: float = 0.1


    def construct_sidebar(self, layout):

        # Buttons to control the view 
        add_group_separator(layout)
        layout.addWidget(QLabel("View"))
        add_sidebar_button(layout, "Zoom to fit", lambda: self.do_zoom_to_fit())
        self.canvas.show_labels = QCheckBox("Show station IDs")
        self.canvas.show_labels.setChecked(False)
        self.canvas.show_labels.clicked.connect(lambda: self.canvas.render())
        layout.addWidget(self.canvas.show_labels)

        # Buttons to control port assignment methods 
        add_group_separator(layout)
        layout.addWidget(QLabel("Port assignment"))
        add_sidebar_button(layout, "Evict all", lambda: self.do_assign_reset())
        add_sidebar_button(layout, "Rounding", lambda: self.do_assign_round())
        add_sidebar_button(layout, "Matching", lambda: self.do_assign_matching())
        add_sidebar_button(layout, "Global...", lambda: self.do_assign_ilp())

        # Buttons to control the labeling
        add_group_separator(layout)
        layout.addWidget(QLabel("Labeling"))
        add_slider(layout, self.do_set_label_values)

        # Buttons to control the layout algorithm
        add_group_separator(layout)
        layout.addWidget(QLabel("Layout"))
        add_sidebar_button(layout, "Update layout", lambda: self.do_layout())
        self.canvas.auto_update = QCheckBox("Auto-update")
        self.canvas.auto_update.setChecked(False)
        layout.addWidget(self.canvas.auto_update)
        add_sidebar_button(layout, "Reset", lambda: self.do_reset_layout())

        # Buttons to control the rendering
        add_group_separator(layout)
        layout.addWidget(QLabel("Rendering"))
        add_sidebar_button(layout, "Render using Loom", lambda: self.do_render())
        self.canvas.auto_render = QCheckBox("Auto-render")
        self.canvas.auto_render.setChecked(False)
        layout.addWidget(self.canvas.auto_render)

    def do_zoom_to_fit(self):
        self.canvas.zoom_to_network()
        self.canvas.render()

    def do_assign_reset(self):
        self.canvas.network.evict_all_edges()
        self.canvas.history_checkpoint("Evict all")
        self.canvas.render()

    def update_layout_if_auto(self):
        if self.canvas.auto_update.isChecked():
            self.do_layout()

    def do_assign_round(self):
        port_assign.assign_by_rounding(self.canvas.network)
        self.update_layout_if_auto()
        self.canvas.history_checkpoint("Assign ports by rounding")
        self.canvas.render()

    def do_assign_matching(self):
        port_assign.assign_by_local_matching(self.canvas.network, self.label_strength)
        self.update_layout_if_auto()
        self.canvas.history_checkpoint("Assign ports by matching")
        self.canvas.render()

    def do_set_label_values(self, value: float): 
        self.label_strength = value
        print(value)
        self.do_assign_matching()

    def do_assign_ilp(self):
        bend_cost = 1
        dialog = BendPenaltyDialog()
        if dialog.exec() == QDialog.Accepted:
            bend_cost = dialog.get_value()
            port_assign.assign_by_ilp(self.canvas.network,bend_cost)
            self.update_layout_if_auto()
            self.canvas.history_checkpoint(f"Assign ports globally (bend cost {bend_cost})")
            self.canvas.render()

    def do_layout(self):
        if layout.layout_lp(self.canvas.network) is False:
            print( "user\t"+"Failed to realize layout.")
            m = QMessageBox()
            m.setText("Failed to realize layout.")
            m.setIcon(QMessageBox.Warning)
            m.setStandardButtons(QMessageBox.Ok)
            m.exec()
        else: 
            self.canvas.network.layout_set = True 
        self.canvas.history_checkpoint("Automated layout")
        if self.canvas.drawing_is_completely_oob():
            self.canvas.zoom_to_network()
        self.canvas.render()

    def update_layout_if_auto(self):
        if self.canvas.auto_update.isChecked():
            self.do_layout()

    def do_reset_layout(self):
        self.canvas.network.layout_set = False 
        for v in self.canvas.network.nodes.values():
            v.pos = v.geo_pos
        for e in self.canvas.network.edges:
            e.bend = None
        self.canvas.zoom_to_network()
        self.canvas.history_checkpoint("Reset layout")
        self.canvas.render()

    def do_render(self, tag=None):
        if self.canvas.filedata is None:
            m = QMessageBox()
            m.setText("Cannot render: opened file was not from Loom.")
            m.setIcon(QMessageBox.Warning)
            m.setStandardButtons(QMessageBox.Ok)
            m.exec()
        else:
            export_loom( self.canvas.network, self.canvas.filedata )
            if tag is None: filename = "render.svg"
            else: filename = f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}-render-{tag}.svg"
            render_loom( "render.json", filename )

    def construct_menubar(self):
        menu_bar = self.menuBar()
        # File menu
        file_menu = menu_bar.addMenu("File")
        open_action = QAction("Open...", self)
        open_action.setShortcut(QKeySequence('Ctrl+O'))
        open_action.triggered.connect(self.canvas.open_dialog)
        file_menu.addAction(open_action)
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence('Ctrl+Q'))
        file_menu.addAction(exit_action)
        exit_action.triggered.connect(self.close)
        # Edit menu
        edit_menu = menu_bar.addMenu("Edit")
        ## TODO: Fix self.canvas.undo_action ... does not make sense at the moment 
        self.canvas.undo_action = QAction("Undo", self)
        edit_menu.addAction(self.canvas.undo_action)
        self.canvas.undo_action.setShortcut(QKeySequence('Ctrl+Z'))
        self.canvas.undo_action.triggered.connect(self.canvas.undo)
        self.canvas.redo_action = QAction("Redo", self)
        edit_menu.addAction(self.canvas.redo_action)
        self.canvas.redo_action.setShortcut(QKeySequence('Ctrl+Shift+Z'))
        self.canvas.redo_action.triggered.connect(self.canvas.redo)

def add_sidebar_button(layout, text, action):
    button = QPushButton(text)
    button.clicked.connect(action)
    layout.addWidget(button)

def add_slider(layout, action): 
    slider = QSlider(Qt.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)
    slider.setValue(2)
    slider.setTickPosition(QSlider.TicksBelow)
    slider.setTickInterval(1)
    slider.setFixedWidth(120)
    slider.valueChanged.connect(action)
    layout.addWidget(slider)

def add_group_separator(layout):
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    layout.addWidget(line) 
      
