from PySide6.QtGui import QColor, QPainterPath, QPen, QFont, QPainter, QPolygonF, QBrush
from PySide6.QtCore import Qt, QRectF
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtSvg import QSvgRenderer

from elements.network import *
from elements.group import Group
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

def render_network( painter: QPainter, net: Network, show_background: bool, label_dist: int, group: Group ):

    # Coordinate system axes
    painter.setPen(QPen(QColor('lightgray'),10))
    painter.setFont(font)
    # painter.drawLine( 0, 0, 100, 0 )
    # painter.drawText( 130, 10, "x" )
    # painter.drawLine( 0, 0, 0, 100 )
    # painter.drawText( 1, 150, "y" )

    # render background 
    if show_background: 
        for e in net.edges: 
            color = QColor('#'+e.color[0])
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
        center_index = (len(e.color) - 1) / 2
        spacing = 4
        for i in range(len(e.color)): 

            offset = (i - center_index) * spacing
            a_start, b_start = e.give_parralel_line(offset)

            ui.edge_pen.setColor(QColor('#'+e.color[i]))
            painter.setPen( ui.edge_pen )

            painter.setBrush(Qt.NoBrush )

            # a_start = e.v[0].pos
            if e.free_at(e.v[0]):
                if e.v[0]==ui.hover_node: 
                    a_1 = free_edge_handle_position(e.v[0],e)
                else: 
                    a_1 = a_start + (ui.bezier_radius*e.direction(e.v[0])).toPointF()
                    a_2 = a_start + (ui.bezier_cp*e.direction(e.v[0])).toPointF()
            else:    
                a_1 = a_start + ui.bezier_radius*port_offset[e.port[0]]
                a_2 = a_start + ui.bezier_cp*port_offset[e.port[0]]

            # b_start = e.v[1].pos
            if e.free_at(e.v[1]):
                if e.v[1]==ui.hover_node: 
                    b_1 = free_edge_handle_position(e.v[1],e)
                else: 
                    b_1 = b_start + (ui.bezier_radius*e.direction(e.v[1])).toPointF()
                    b_2 = b_start + (ui.bezier_cp*e.direction(e.v[1])).toPointF()
            else:    
                b_1 = b_start + ui.bezier_radius*port_offset[e.port[1]]
                b_2 = b_start + ui.bezier_cp*port_offset[e.port[1]]

            path = QPainterPath()

            if e.free_at(e.v[0]):
                path.moveTo( a_1 )
            else:
                path.moveTo( a_start )
                path.lineTo( a_1 )
            
            if e.bend is None: 
                path.cubicTo( a_2, b_2, b_1 )
            else:
                path.lineTo( e.give_point_offset(e.bend, offset) )
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

        if group and v in group.nodes and group.hover_label_port == None: continue 

        if (not ui.drag_node or ui.hover_node) and v.label_node.label_text != "": 
            if not v.label_node.center_label: 
                # Draw bouding box label
                painter.setPen(QPen(QColor('lightgray'),5))
                painter.setBrush(ui.rose_used_brush)
                if net.layout_set: 
                    # painter.drawLine(v.label_node.head, v.label_node.end) 
                    painter.drawPolygon(v.label_node.rectangle_points)

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
                if net.layout_set: 
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

def render_brush(painter: QPainter, points: QPolygonF, brush: QPainterPath): 
    ui.lasso_pen.setStyle(Qt.DashLine)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor(200,10,10,100)))
    all_points = points.toList()
    if len(all_points) > 2: 
        # One polygon approximation of the filled shape
        painter.drawPolygon(brush.toFillPolygon())

def render_rectangle_select(painter: QPainter, points: QPolygonF): 
    ui.lasso_pen.setStyle(Qt.DashLine)
    painter.setPen(ui.lasso_pen)
    painter.setBrush(Qt.NoBrush)
    all_points = points.toList()
    if len(all_points) >= 2: 
        rect = QRectF(all_points[0], all_points[-1])
        painter.drawRect(rect)

def render_highlighted_nodes(painter: QPainter, nodes: list[Node]): 
    painter.setPen(ui.active_pen)
    painter.setBrush(ui.active_brush)
    for node in nodes: 
        painter.drawEllipse(node.pos, 10, 10)

def render_group(painter: QPainter, group: Group,  move_group: bool, pivot_group: None | int): 
    ui.lasso_pen.setStyle(Qt.SolidLine)
    painter.setBrush(QBrush(QColor(200,10,10,100)))
    painter.setPen(ui.lasso_pen)
    
    # draw border 
    if group.hover_label_port == None: 
        for border_part in group.border: 
            painter.drawPolygon(border_part)
    
    # painter.drawRect(group.bounding_rect)

    painter.setPen(ui.button_pen)
    # draw pivot buttons 
    if not move_group and group.hover_label_port == None: 
        for i, button in enumerate(group.pivot_buttons_pos): 
            if type(pivot_group) == int and pivot_group != i: continue  
            painter.setBrush(QBrush(QColor('lightgreen')))
            painter.drawEllipse(button, 20, 20)
            painter.setBrush(Qt.NoBrush )
            open_dir = angle_from_points(button, group.conn_nodes[i].pos) + 90
            draw_arc_with_arrows(painter, button, 40, arc_deg=90, open_direction_deg=open_dir)

    painter.setBrush(QBrush(QColor('red')))
    # draw middle buttons
    if pivot_group == None and group.hover_label_port == None: 
        move_but = group.move_button_pos
        painter.drawEllipse(move_but, group.button_size, group.button_size)
        renderer = QSvgRenderer("assets/move_icon.svg")
        icon_size = group.button_size + 10
        renderer.render(painter, 
                        QRectF(move_but.x() - 15, move_but.y() - icon_size/2, icon_size, icon_size))

    painter.setBrush(QBrush(QColor('lightblue')))
    if pivot_group == None and not move_group: 
        if group.hover_label_port == None: 
            # for expand button 
            expand_but = group.expand_button_pos
            painter.drawEllipse(expand_but, group.button_size, group.button_size)
            renderer = QSvgRenderer("assets/expand_rot.svg" if group.nodes[0].left_line else "assets/expand.svg")
            icon_size = group.button_size + 10
            renderer.render(painter, QRectF(expand_but.x() - 15, expand_but.y() - icon_size/2, icon_size, icon_size))

            # For lock button 
            lock_but = group.lock_button_pos
            painter.drawEllipse(lock_but, group.button_size, group.button_size)
            renderer = QSvgRenderer("assets/lock.svg" if group.check_locked_status() else "assets/unlock.svg")
            icon_size = group.button_size
            renderer.render(painter, QRectF(lock_but.x() - 10, lock_but.y() - icon_size/2, icon_size, icon_size))

        # For label button 
        label_but = group.label_button_pos
        painter.drawEllipse(label_but, group.button_size, group.button_size)
        renderer = QSvgRenderer("assets/label.svg")
        icon_size = group.button_size - 2
        renderer.render(painter, QRectF(label_but.x() - 8, label_but.y() - icon_size/2 + 1, icon_size, icon_size))

        # Draw label rose 
        ui.rose_free_pen.setCosmetic(True)
        ui.rose_used_pen.setCosmetic(True)
        ui.active_handle_pen.setCosmetic(True)
    
        for i in range(8):
            if group.label_port_active == i: 
                painter.setBrush(ui.rose_used_brush)
            else:
                painter.setBrush(ui.rose_free_brush)

            if group.hover_label_port == i: 
                painter.setBrush(ui.highlight_brush)

            painter.drawEllipse( group.label_button_pos + 20*port_offset[i], 6, 6)

def angle_from_points(p1: QPointF, p2: QPointF) -> float:
    dx = p2.x() - p1.x()
    dy = p1.y() - p2.y() 
    return math.degrees(math.atan2(dy, dx))

def draw_arrow_head(painter: QPainter, tip: QPointF, direction_deg: float, size: float = 12, spread_deg: float = 28):
    a1 = math.radians(direction_deg + 180 - spread_deg)
    a2 = math.radians(direction_deg + 180 + spread_deg)

    p1 = QPointF(tip.x() + size * math.cos(a1), tip.y() - size * math.sin(a1))
    p2 = QPointF(tip.x() + size * math.cos(a2), tip.y() - size * math.sin(a2))

    painter.drawLine(tip, p1)
    painter.drawLine(tip, p2)

def draw_arc_with_arrows(painter: QPainter, center: QPointF, radius: float, arc_deg: float, open_direction_deg: float):
    
    rect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)

    start_deg = open_direction_deg + arc_deg/2

    path = QPainterPath()
    path.arcMoveTo(rect, start_deg)
    path.arcTo(rect, start_deg, arc_deg)
    painter.drawPath(path)

    # endpoints from the path itself
    p_start = path.pointAtPercent(0.0)
    p_end = path.pointAtPercent(1.0)

    # nearby points to determine tangent direction
    eps = 0.01
    p_start_next = path.pointAtPercent(eps)
    p_end_prev = path.pointAtPercent(1.0 - eps)

    start_dir = angle_from_points(p_start, p_start_next) + 185
    end_dir = angle_from_points(p_end_prev, p_end) - 5

    draw_arrow_head(painter, p_start, start_dir)
    draw_arrow_head(painter, p_end, end_dir)


def render_concentric_circles(painter: QPainter): 
    #For displaying concentric circles 
    if ui.drag_node and len(ui.drag_node.edges) == 1:
        radius = ui.drag_node.edges[0].min_dist / 2
        
        for i in range(8, 0, -1): 
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0,0,0,5 * i)))
            painter.drawEllipse(ui.drag_node.pos, radius * i, radius * i)

            painter.setPen(QPen( QColor('white'), 3 ))
            painter.drawText(ui.drag_node.pos + ((radius * (i-0.5)) * port_offset[5]) + QPointF(-10, 0), str(i))

        painter.setPen(QPen( QColor('white'), 3 ))
        painter.drawLine(ui.drag_node.pos, ui.drag_node.pos + (radius * 8 * port_offset[5]))


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
