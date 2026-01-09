import math

from PySide6.QtWidgets import QWidget, QSizePolicy, QMenu, QMessageBox, QFileDialog
from PySide6.QtGui import QPainter, QPixmap, QColor, Qt, QTransform, QVector2D
from PySide6.QtCore import QPointF, QEvent

from io_management.fileformat_loom import read_network_from_loom, export_loom, render_loom
from io_management.fileformat_graphml import read_network_from_graphml

from helpers.layout import layout_lp

from elements.network import Label

import render
import ui

min_edge_scale = 80

class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.pixmap = QPixmap( self.size() )
        self.pixmap.fill( QColor('white') )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.grabGesture(Qt.PinchGesture)

        # history buffer
        self.history = []
        self.history_index = -1

        # UI state
        self.old_mouse = None
        self.view = QTransform()

        # load a network
        filename = 'loom-examples/wien.json'
        self.network, self.filedata = read_network_from_loom(filename)
        self.network.scale_by_shortest_edge( min_edge_scale )
        self.network.find_degree_2_lines()
        self.network.calculate_mid_point()

        self.label_dist:int = 20
        
    def render(self):
        #self.network.clone()
        painter = QPainter(self.pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # viewport
        painter.setTransform(self.view)
        # draw
        self.pixmap.fill( QColor('white') )
        ui.update_params( self.view.m11() ) # element [1,1] of the view matrix is scale in our case
        render.render_network(painter, self.network, self.show_labels.isChecked() )
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)
		
    def zoom_to_network(self):
        min_x, min_y = math.inf, math.inf
        max_x, max_y = -math.inf, -math.inf
        for name, v in self.network.nodes.items():
            min_x = min(min_x, v.pos.x())
            min_y = min(min_y, v.pos.y())
            max_x = max(max_x, v.pos.x())
            max_y = max(max_y, v.pos.y())
        x_scale = (0.9*self.width()) / (max_x - min_x)
        y_scale = (0.9*self.height()) / (max_y - min_y)
        scale = min(x_scale, y_scale)
        self.view = QTransform()
        self.view.translate(0.05*self.width(), 0.05*self.height())
        self.view.scale(scale, scale)
        self.view.translate(-min_x, -min_y)
    
    def worldspace(self, pos):
        return self.view.inverted()[0].map(QPointF(pos))
	
    def resizeEvent(self, event):
        if self.size() != self.pixmap.size():
            new_pixmap = QPixmap(self.size())
            new_pixmap.fill(QColor('white'))
            painter = QPainter(new_pixmap)
            self.render()
            painter.drawPixmap(0, 0, self.pixmap)
            self.pixmap = new_pixmap

    def drawing_is_completely_oob(self):
        # Is any node on the canvas based on the viewport? (Ignores edges.)
        rect = self.rect()
        for v in self.network.nodes.values():
            p = self.view.map(v.pos).toPoint()
            if rect.contains(p): return False
        return True

    # Forward every mouse event to the function handle_mouse 
    def mousePressEvent(self, event): self.handle_mouse(event,press=True)
    def mouseReleaseEvent(self, event): self.handle_mouse(event,release=True)
    def mouseMoveEvent(self, event): self.handle_mouse(event)
    def mouseDoubleClickEvent(self, event): self.handle_mouse(event,doubleclick=True)
    def handle_mouse(self,event, press=False, release=False, doubleclick=False):

        # Check what the current mouse position is
        pos = self.worldspace(event.position())
        if self.old_mouse is None: self.old_mouse = event.position()
        
        # Check where the mouse pointer is close to 
        ui.hover_node = None
        ui.hover_edge = None
        ui.hover_empty_port = None
        closest_dist = ui.hover_node_radius

        # Determine which node the mouse is hovering 
        for v in self.network.nodes.values():
            dist = QVector2D(v.pos - pos).length()
            if dist < closest_dist:
                closest_dist = dist
                ui.hover_node = v

        # When the mouse is hovering a node: 
        if ui.hover_node:
            closest_dist = ui.handle_radius
            # consider the rose
            for i in range(8):
                dist = QVector2D(render.handle_position(ui.hover_node,i) - pos).length()
                if dist < closest_dist:
                    closest_dist = dist
                    if ui.hover_node.ports[i] is None:
                        ui.hover_edge = None
                        ui.hover_empty_port = i
                    else:
                        ui.hover_edge = ui.hover_node.ports[i]
                        ui.hover_empty_port = None
            # consider free edges
            for e in ui.hover_node.edges:
                if e.free_at(ui.hover_node):
                    dist = QVector2D(render.free_edge_handle_position(ui.hover_node,e) - pos).length()
                    if dist < closest_dist:
                        closest_dist = dist
                        ui.hover_edge = e
                        ui.hover_empty_port = None

        # for undo message: what did we change about the network, if anything?
        network_change = None

        ### recognize which actions, if any, to trigger based on this mouse event

        self.mouse_pos = pos
        if event.buttons() == Qt.MiddleButton:
            # drag view
            drag = (event.position() - self.old_mouse) / self.view.m11() # account for view scale
            self.view.translate( drag.x(), drag.y() )

        if event.buttons() == Qt.RightButton:
            if ui.hover_edge:
                print('hellooo?')
                # Context menu when right-clicking a handle
                menu = QMenu(self)
                if not ui.hover_edge.free_at(ui.hover_node):
                    straighten = menu.addAction("Straighten")
                    menu.addSeparator()
                    evict = menu.addAction("Evict")
                    action = menu.exec(self.mapToGlobal(event.position().toPoint()))
                    if action == evict:
                        assert ui.hover_node is not None
                        assert ui.hover_edge is not None
                        ui.hover_node.try_evict(ui.hover_edge)
                        network_change = f'Evict at "{ui.hover_node.label}" toward "{ui.hover_edge.other(ui.hover_node.name).label}"'
                    if action == straighten:
                        assert ui.hover_node is not None
                        assert ui.hover_edge is not None
                        ui.hover_node.straighten_deg2(ui.hover_edge)
                        network_change = f'Straighten from "{ui.hover_node.label}" toward "{ui.hover_edge.other(ui.hover_node).label}" (context menu)'
            elif ui.hover_node is not None and ui.hover_empty_port is None:
                if ui.hover_node.is_right_angle():
                    menu = QMenu(self)
                    smoothen = menu.addAction("Smoothen")
                    action = menu.exec(self.mapToGlobal(event.position().toPoint()))
                    if action == smoothen:
                        ui.hover_node.smoothen()
                        network_change = f'Smoothen "{ui.hover_node.label}"'
                if False and ui.hover_node.is_straight_through():
                    v = ui.hover_node
                    if (not v.edges[0].consistent_ports()) ^ (not v.edges[1].consistent_ports()):
                        menu = QMenu(self)
                        bump = menu.addAction("Bump")
                        action = menu.exec(self.mapToGlobal(event.position().toPoint()))
                        if action == bump:
                            from_id = 1 if v.edges[0].consistent_ports() else 0
                            # edge that will become consistent:
                            from_e = v.edges[from_id]
                            # where does it come from?
                            thru_port = from_e.port[1-from_e.id(v)]
                            print('thru_port',thru_port)
                            # consistently assign to us
                            v.assign(from_e,opposite_port(thru_port),True)
                            from_e.bend = None
                            # go straight through here
                            to_e = v.edges[1-from_id]
                            v.assign(to_e,thru_port,True)


        if press and event.buttons() == Qt.LeftButton:
            print( ui.hover_node, ui.hover_edge, ui.hover_empty_port )
            if ui.selected_node is None:
                # nothing was selected: select the thing we clicked on
                ui.selected_node = ui.hover_node
                ui.selected_edge = ui.hover_edge
            else:
                if ui.hover_node is None or (ui.hover_edge is None and ui.hover_empty_port is None):
                    # clicked on empty space: deselect
                    ui.selected_node = None
                    ui.selected_edge = None
                elif ui.hover_node!=ui.selected_node:
                    # clicked on another node: select that instead
                    ui.selected_node = ui.hover_node
                    ui.selected_edge = ui.hover_edge
                #else: leave selection alone, maybe mouse release will do something
            
            if ui.selected_label_node is None and ui.hover_node.label_node.port == ui.hover_empty_port: 
                ui.selected_label_node = ui.hover_node

        if release and ui.selected_edge is not None:
            # release mouse and there is a selected handle
            if ui.hover_edge is None and ui.hover_empty_port is None:
                # released on nothing: deselect
                ui.selected_node = None
                ui.selected_edge = None
                
            elif ui.selected_edge==ui.hover_edge:
                pass # leave it selected?
            else:
                # we dragged here, or selected first and now click something else
                if ui.hover_node==ui.selected_node and ui.hover_empty_port is not None:

                    if type(ui.selected_edge) == Label: 
                        ui.selected_node.assign_label(ui.hover_empty_port)
                        network_change = f'Reassign at "{ui.selected_node.label}" - label to port {ui.hover_empty_port}'
                    else: 
                        # we went from one handle to another handle on the same node.
                        # assign symmetric / asymmetric based on modifier key.
                        if event.modifiers() & Qt.ShiftModifier:
                            ui.selected_node.assign( ui.selected_edge, ui.hover_empty_port, force=True)
                        else:
                            ui.selected_node.assign_both_ends( ui.selected_edge, ui.hover_empty_port, force=True )
                        network_change = f'Reassign at "{ui.selected_node.label}" - "{ui.selected_edge.other(ui.hover_node).label}" to port {ui.hover_empty_port}'

                    # if ui.selected_node.label_node.port == ui.hover_empty_port:
                    #     pass 

                # we did a thing; don't have a selection anymore
                ui.selected_node = None
                ui.selected_edge = None

        # double click handles to straighten
        if doubleclick and event.buttons() == Qt.LeftButton:
            if ui.hover_edge is not None:
                ui.hover_node.straighten_deg2( ui.hover_edge )
                network_change = f'Straighten from "{ui.hover_node.label}" toward "{ui.hover_edge.other(ui.hover_node).label}" (double click)'


        ### Did we do anything? Then solve and render as appropriate, and to undo buffer
        if network_change is not None:
            if self.auto_update.isChecked():
                resolve_shift = layout_lp(self.network, self.label_dist, ui.hover_node)
                if resolve_shift:
                    self.view.translate(-resolve_shift.x(), -resolve_shift.y())
                    if self.auto_render.isChecked():
                        export_loom(self.network,self.filedata)
                        render_loom( "render.json", "render.svg" )
                elif resolve_shift is False:
                    m = QMessageBox()
                    m.setText("Failed to realise layout.")
                    m.setIcon(QMessageBox.Warning)
                    m.setStandardButtons(QMessageBox.Ok)
                    m.exec()
            self.history_checkpoint( network_change )

        ### Remember mouse position for next time and redraw.

        self.old_mouse = event.position()
        self.render()  
    
    def handle_scale_at(self, mouse_pos, scale):
        pos = self.worldspace(mouse_pos)
        scaleAt = QTransform( scale,0, 0,scale, (1-scale)*pos.x(), (1-scale)*pos.y() )
        self.view = scaleAt * self.view

    def wheelEvent(self, event):
        if event.pixelDelta().manhattanLength() > 0 and event.source()==Qt.MouseEventSource.MouseEventSynthesizedBySystem:
            # Actually touchpad pan or 2D scroll
            if event.modifiers() & Qt.AltModifier:
                # Hold alt to zoom anyway
                s = pow( 1.2, event.angleDelta().y()/120 )
                self.handle_scale_at(event.position(), s)
            else:
                # Actually pan
                drag = event.pixelDelta() / self.view.m11() # m11 accounts for view scale
                self.view.translate( drag.x(), drag.y() )
        elif event.angleDelta().y() != 0 and event.source()==Qt.MouseEventSource.MouseEventNotSynthesized:
            # Actual mouse wheel zoom
            s = pow( 1.2, event.angleDelta().y()/120 )
            self.handle_scale_at(event.position(), s)
        self.render()

    # Fiddle with some gesture events to make pinch zoom works
    def event(self, event):
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().event(event)
    def gestureEvent(self, event):
        if pinch := event.gesture(Qt.PinchGesture):
            self.handlePinch(pinch)
        return True
    def handlePinch(self, pinch):
        if pinch.state() == Qt.GestureStarted:
            pass
        elif pinch.state() in (Qt.GestureUpdated, Qt.GestureFinished):
            self.handle_scale_at(pinch.centerPoint(), pinch.scaleFactor())
            self.render()

    def open_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(None, 'Open File', '', 'All Files (*)')
        if file_name:
            if file_name[-8:]==".graphml":
                self.network = read_network_from_graphml(file_name)
                self.filedata = None
            else:
                self.network, self.filedata = read_network_from_loom(file_name)
            self.network.scale_by_shortest_edge( min_edge_scale )
            self.history_checkpoint( f'Open "{file_name}"' )
            self.zoom_to_network()

    
    def history_checkpoint(self, text):
        # Log the message
        print( "user\t"+text )
        # Delete the future
        self.history = self.history[0:self.history_index+1]
        # Add the present
        self.history.append(( text, self.network.clone() ))
        self.history_index += 1
        self.update_history_actions()

    def update_history_actions(self):
        # Set the text and availability of the "undo" menu item based on where we are in time now.
        if self.history_index<1:
            self.undo_action.setEnabled(False)
            self.undo_action.setText("Undo")
        else:
            self.undo_action.setEnabled(True)
            self.undo_action.setText( "Undo " + self.history[self.history_index][0] )

        if self.history_index==len(self.history)-1:
            self.redo_action.setEnabled(False)
            self.redo_action.setText("Redo")
        else:
            self.redo_action.setEnabled(True)
            self.redo_action.setText( "Redo " + self.history[self.history_index+1][0] )

    def undo(self):
        # Assumes we don't undo to before the start of time
        print("user\t"+"Undo")
        self.history_index -= 1
        self.fetch_history()
        self.update_history_actions()
        self.render()
    
    def redo(self):
        # Assumes the future exists
        print("user\t"+"Redo")
        self.history_index += 1
        self.fetch_history()
        self.update_history_actions()
        self.render()
    
    def fetch_history(self):
        self.network = self.history[self.history_index][1].clone()
