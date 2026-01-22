from PySide6.QtGui import QColor, QPainterPath, QPen, QFont, QPainter, QPolygonF
from PySide6.QtCore import Qt

from elements.network import *
from math import sqrt

import ui

diag = 1/sqrt(2) # notational convenience

rotation_factor = [0, -45, -90, 45, 0, -45, -90, 45]

min_edge_length = 100 

def opposite_port( p ):
    return (p+4)%8

port_offset = [ QPointF(-1,0)
              , QPointF(-diag,diag)
              , QPointF(0,1)
              , QPointF(diag,diag)
              , QPointF(1,0)
              , QPointF(diag,-diag)
              , QPointF(0,-1)
              , QPointF(-diag,-diag)
              ]

font = QFont("Helvetica", 30, QFont.Bold)

def render_network( painter: QPainter, net: Network, show_background: bool, label_dist: int ):

    # Coordinate system axes
    painter.setPen(QPen(QColor('lightgray'),10))
    painter.setFont(font)
    painter.drawLine( 0, 0, 100, 0 )
    painter.drawText( 130, 10, "x" )
    painter.drawLine( 0, 0, 0, 100 )
    painter.drawText( 1, 150, "y" )

    # render background 
    if show_background: 
        for e in net.edges: 
            color = QColor('#'+e.color)
            color.setAlpha(20) 
            ui.edge_pen.setColor(color)
            painter.setPen( ui.edge_pen )
            painter.setBrush(Qt.NoBrush )

            painter.drawLine(e.v[0].background_pos, e.v[1].background_pos)

        for _, v in net.nodes.items(): 
            painter.setPen(ui.node_pen_background)
            painter.setBrush(ui.node_brush)
            painter.drawEllipse(v.background_pos, 10, 10)

    # Draw the edges
    for e in net.edges:
        ui.edge_pen.setColor(QColor('#'+e.color))
        painter.setPen( ui.edge_pen )

        painter.setBrush(Qt.NoBrush )

        a_start = e.v[0].pos
        if e.free_at(e.v[0]):
            if e.v[0]==ui.hover_node: a_1 = free_edge_handle_position(e.v[0],e)
            else: a_1 = e.v[0].pos + (ui.bezier_radius*e.direction(e.v[0])).toPointF()
            a_2 = e.v[0].pos + (ui.bezier_cp*e.direction(e.v[0])).toPointF()
        else:    
            a_1 = e.v[0].pos + ui.bezier_radius*port_offset[e.port[0]]
            a_2 = e.v[0].pos + ui.bezier_cp*port_offset[e.port[0]]

        b_start = e.v[1].pos
        if e.free_at(e.v[1]):
            if e.v[1]==ui.hover_node: b_1 = free_edge_handle_position(e.v[1],e)
            else: b_1 = e.v[1].pos + (ui.bezier_radius*e.direction(e.v[1])).toPointF()
            b_2 = e.v[1].pos + (ui.bezier_cp*e.direction(e.v[1])).toPointF()
        else:    
            b_1 = e.v[1].pos + ui.bezier_radius*port_offset[e.port[1]]
            b_2 = e.v[1].pos + ui.bezier_cp*port_offset[e.port[1]]

        path = QPainterPath()
        if e.free_at(e.v[0]):
            path.moveTo( a_1 )
        else:
            path.moveTo( a_start )
            path.lineTo( a_1 )
        if e.bend is None: path.cubicTo( a_2, b_2, b_1 )
        else:
            path.lineTo( e.bend )
            path.lineTo( b_1 )
        if not e.free_at(e.v[1]):
            path.lineTo( b_start)
        painter.drawPath(path)

    # for indicator lines (should be done earlier because that looks prettier)
    if ui.hover_node: 
        for e in ui.hover_node.edges:  
            # For minimal length indicator
            if (e.length() >= min_edge_length): 
                if not e.bend: 
                    draw_indicator_lines(painter, QLineF(ui.hover_node.pos, e.other(ui.hover_node).pos))
                else: 
                    first_part = QLineF(ui.hover_node.pos, e.bend)
                    draw_indicator_lines(painter, first_part)
                    left_over = (first_part.length() % min_edge_length)
                    second_part = QLineF(e.bend, e.other(ui.hover_node).pos)
                    draw_indicator_lines(painter, second_part, start=-1 * left_over)


    # Draw the nodes
    painter.setPen(ui.node_pen)
    painter.setBrush(ui.node_brush)
    for name, v in net.nodes.items():
        
        if v.locked: 
            painter.setPen(ui.lock_pen)
        else: 
            painter.setPen(ui.node_pen)
        
        painter.setBrush(ui.node_brush)
        painter.drawEllipse(v.pos, 10, 10)

        if not ui.drag_node or ui.hover_node: 
            if not v.label_node.center_label: 
                # Draw bouding box label
                painter.setPen(QPen(QColor('lightgray'),20))
                if net.layout_set: 
                    painter.drawLine(v.label_node.head, v.label_node.end) 

                # Draw text in bounding box  
                painter.setPen(QPen(QColor('black'),20))
                painter.setFont(QFont("Arial", 15))
                painter.save()
                painter.translate(handle_label_text_position(v, v.label_node.port))
                if v.label_node.port is not None: painter.rotate(rotation_factor[v.label_node.port])   
                painter.drawText( QPointF(0, 5), v.label )
                painter.restore()
            else: 
                # For horizontal labels 
                vert_dist = label_dist if v.label_node.port == 2 else -label_dist
                vert_dist_text = vert_dist + 5 if v.label_node.port == 2 else vert_dist + 5
                painter.setPen(QPen(QColor('lightgray'),20))
                painter.drawLine(v.pos + QPointF(-v.label_node.text_width/2, vert_dist), v.pos + QPointF(v.label_node.text_width/2, vert_dist))
                
                painter.setPen(QPen(QColor('black'),20))
                painter.setFont(QFont("Arial", 15))
                painter.drawText(v.pos + QPointF(-v.label_node.text_width/2, vert_dist_text), v.label)

    
    # Draw UI for the node close to the mouse
    if ui.hover_node:
        draw_rose( painter, ui.hover_node )
        for e in ui.hover_node.edges:
            if e.free_at(ui.hover_node):
                painter.setPen( ui.rose_used_pen)
                painter.setBrush( ui.rose_used_brush )
                if e==ui.selected_edge: painter.setBrush( ui.selected_brush )
                if e==ui.hover_edge: painter.setBrush( ui.highlight_brush )
                handle_pos = free_edge_handle_position(ui.hover_node, e)
                painter.drawEllipse(handle_pos,ui.handle_radius,ui.handle_radius)
                

def render_lasso(painter: QPainter, points: QPolygonF): 
    ui.lasso_pen.setStyle(Qt.DashLine)
    painter.setPen(ui.lasso_pen)
    painter.drawPolyline(points)


def handle_position( v: Node, p: int ):
    return v.pos + ui.rose_radius*port_offset[p]

def handle_center_rose_position(v: Node, p: int): 
    assert p == 8 or p == 9
    if p == 8: return v.pos + (ui.rose_radius + ui.handle_radius + 10)*port_offset[2]
    else: return v.pos - (ui.rose_radius + ui.handle_radius + 10)*port_offset[2]

def handle_label_pos(point: QPointF, p: int): 
    if p is not None: 
        return point + 30*port_offset[p]
    else: 
        return point + 30*port_offset[0]
    
def handle_label_text_position(v: Node, p: int): 
    if p is not None: 
        if p in [0,1,2,7]: 
            return v.label_node.head
        else: 
            return v.label_node.end
    else: 
        return v.pos

def free_edge_handle_position( v, e ):
    dir = e.direction(v).toPointF()
    return v.pos + 2*ui.rose_radius*dir

def is_hovered( v, i ):
    if v!=ui.hover_node: return False
    if v.ports[i] is None and i==ui.hover_empty_port: return True
    return ui.hover_edge is not None and v.ports[i]==ui.hover_edge

def draw_rose( painter, v: Node ):
    ui.rose_free_pen.setCosmetic(True)
    ui.rose_used_pen.setCosmetic(True)
    ui.active_handle_pen.setCosmetic(True)
    for i in range(8):
        if v.ports[i] is None:
            painter.setPen(ui.rose_free_pen)
            painter.setBrush(ui.rose_free_brush)
        else:
            painter.setPen(ui.rose_used_pen)
            painter.setBrush(ui.rose_used_brush)
        if ui.selected_node is not None:
            painter.setPen( ui.active_handle_pen )
        if ui.selected_node==v and ui.selected_edge is not None and ui.selected_edge==v.ports[i]:
            painter.setBrush(ui.selected_brush)
        if is_hovered( v, i ):
            painter.setBrush(ui.highlight_brush)
        painter.drawEllipse( handle_position(v,i), ui.handle_radius, ui.handle_radius )
    
    if ui.selected_node is not None and type(ui.selected_edge) == Label: 
        vert_dist = [(ui.rose_radius + ui.handle_radius + 5), -1 * (ui.rose_radius + ui.handle_radius + 15)]
        for i in range(2): 
            # for the horizontal center labels
            painter.setPen(ui.active_handle_pen)
            painter.setBrush(ui.rose_free_brush)
            if ui.hover_empty_port == i+8: 
                painter.setBrush(ui.highlight_brush)
            start = v.pos + QPointF(-2 * ui.handle_radius, vert_dist[i])
            painter.drawRect(start.x(), start.y(), 4 * ui.handle_radius, 10)

# Direction is always from p1 to p2 
def draw_indicator_lines(painter: QPainter, line: QLineF, start: float = 0): 
    direction = QVector2D(line.p2() - line.p1()).normalized()
    normal = line.normalVector()
    normal = (QVector2D(normal.dx(), normal.dy()).normalized() * 4).toPointF()
    for i in range(int((line.length() - start)/min_edge_length)): 
        indicator_point = line.p1() + (direction * ((i+1) * 100 + start)).toPointF()
        indicator_line = QLineF(indicator_point + normal, indicator_point - normal)
        painter.setPen( ui.node_pen )
        painter.drawLine(indicator_line)
