

from PySide6.QtGui import Qt, QPolygonF, QVector2D
from PySide6.QtCore import QPointF, QRectF, QLineF

from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union, polygonize

from elements.network import Node, Edge
from math import sqrt

diag = 1/sqrt(2)

port_offset = [ QPointF(-1,0)
              , QPointF(-diag,diag)
              , QPointF(0,1)
              , QPointF(diag,diag)
              , QPointF(1,0)
              , QPointF(diag,-diag)
              , QPointF(0,-1)
              , QPointF(-diag,-diag)
              ]

class Group: 

    def __init__(self, nodes: list[Node], conn_edges: list[Edge], conn_nodes: list[Node], name: str = '', color = None):
        self.nodes: list[Node] = nodes 
        self.conn_edges: list[Edge] = conn_edges
        self.conn_nodes: list[Node] = conn_nodes
        self.name: str = name 
        self.color: str | None = color

        self.button_size = 20

        self.internal_edges = self.find_all_edges()

        # Buttons 
        self.pivot_buttons_pos: list[QPointF] = []
        self.move_button_pos: QPointF | None = None 
        self.expand_button_pos: QPointF | None = None 
        self.lock_button_pos: QPointF | None = None 
        self.label_button_pos: QPointF | None = None 

        self.label_port_active: int | None = None 
        self.hover_label_port: int | None = None 

        self.update_border()
        self.determine_pivot_buttons()


    def can_be_moved(self) -> bool: 
        return len(self.conn_nodes) > 0
    
    def has_point_in_center(self, point) -> bool: 
        dist = QVector2D(self.move_button_pos - point).length()
        # size of center point on screen
        return dist < self.button_size
    
    def has_point_in_expand(self, point) -> bool: 
        dist = QVector2D(self.expand_button_pos - point).length()
        return dist < self.button_size
    
    def has_point_in_lock(self, point) -> bool: 
        dist = QVector2D(self.lock_button_pos - point).length()
        return dist < self.button_size
    
    def has_point_in_pivot_button(self, point) -> bool: 
        for i, button in enumerate(self.pivot_buttons_pos): 
            dist = QVector2D(button - point).length()
            # size of center point on screen
            if dist < self.button_size: 
                return i 
        return None 
    
    def handle_port_offset(self, pos: QPointF, p: int): 
        return pos + 20*port_offset[p]
    
    def has_point_in_label_button(self, point) -> int | None: 
        dist_button = QVector2D(self.label_button_pos - point).length()

        # If we are outside of this range we are not close to any label
        if dist_button > self.button_size * 2: 
            self.hover_label_port = None
            return None 

        # check if we are over each port 
        for i in range(8):
            dist = QVector2D(self.handle_port_offset(self.label_button_pos, i) - point).length()

            if dist < 10:
                self.hover_label_port = i
                return i
        return None 
    
    def circular_diff(self, a, b, n=8):
        return (b - a + n//2) % n - n//2

    def pivot(self, mouse_pos: QPointF, button_index: int) -> tuple[QPointF | None, int]: 
        
        # We just pick one for now 
        outside_v = self.conn_nodes[button_index]
        outside_e = self.conn_edges[button_index]

        closer_port = outside_v.check_for_closer_port(mouse_pos)

        # Only rotate the group if the target port differs from the current one
        if closer_port != outside_e.port_at(outside_v) and closer_port in outside_v.get_free_ports(ignore_label=True): 
            # Determine rotation direction: clockwise or counterclockwise
            distance = self.circular_diff(outside_e.port_at(outside_v), closer_port)

            # rotate all nodes in the group by shifting ports in the same direction
            for v in self.nodes: 
                v.lock()
                new_label_port = (v.label_node.port + distance) % 8
                # reassign all internal edges connected to other nodes in the group
                for e in v.edges: 
                    if e.other(v) in self.nodes: 
                        v.assign(e, (e.port_at(v) + distance) % 8)

                # reassign the node label to the rotated port
                v.assign_label(new_label_port)

            # reassign the outside edge at the external node to complete the pivot
            for i in range(len(self.conn_edges)): 
                new_port = (self.conn_edges[i].port_at(self.conn_nodes[i]) + distance) % 8
                if new_port in self.conn_nodes[i].get_free_ports(ignore_label=True):
                    self.conn_nodes[i].assign_both_ends(self.conn_edges[i], new_port)
            
            return outside_v.pos, 45 * distance 
        
        return None, 0 

    def move(self, mouse_pos) -> bool : 

        closer_ports = []

        for i in range(len(self.conn_nodes)): 
            outside_v = self.conn_nodes[i]
            outside_e = self.conn_edges[i]

            closer_port = outside_v.check_for_closer_port(mouse_pos)

            if closer_port != outside_e.port_at(outside_v): 
                closer_ports.append(closer_port)

        # if not for every conn node a new port is found, we wait
        if len(closer_ports) != len(self.conn_nodes): 
            return False  
        
        for i in range(len(self.conn_nodes)): 
            outside_v = self.conn_nodes[i]
            outside_e = self.conn_edges[i]

            outside_v.assign_both_ends(outside_e, closer_ports[i])
        
        for v in self.nodes: 
            v.lock()
        
        return True 

            # cc_wise = 1 if closer_ports[i] > outside_e.port_at(outside_v) else -1
            # outside_v.assign_both_ends(outside_e, (outside_e.port_at(outside_v) + cc_wise) % 8)
    
    def expand(self, pos: QPointF): 
        vec = QVector2D(pos - self.expand_button_pos)
        if self.nodes[0].left_line: 
            if vec.x() < self.button_size and vec.y() < -self.button_size: 
                for edge in self.internal_edges: 
                    edge.min_dist += 1
            if vec.x() > -self.button_size and vec.y() > self.button_size: 
                for edge in self.internal_edges: 
                    edge.min_dist -= 1
        else: 
            if vec.x() > self.button_size and vec.y() < -self.button_size: 
                for edge in self.internal_edges: 
                    edge.min_dist += 1
            if vec.x() < -self.button_size and vec.y() > self.button_size: 
                for edge in self.internal_edges: 
                    edge.min_dist -= 1

    def check_locked_status(self) -> bool: 
        locked: int = 0 
        for v in self.nodes: 
            if v.locked: locked += 1
        return locked > len(self.nodes)/2

    # we lock if the majority is unlocked and the other way around
    def toggle_lock(self): 
        locked = self.check_locked_status()
        for v in self.nodes: 
            if locked: v.unlock()
            else: v.lock()
        return locked 

    def set_group_labels(self): 
        if self.hover_label_port == None: return 

        self.label_port_active = self.hover_label_port
        for v in self.nodes: 
            if v.isfree(self.label_port_active): 
                v.assign_label(self.label_port_active)
        return self.label_port_active

    def find_all_edges(self) -> list[Edge]:
        edges: list[Edge] = []
        for node in self.nodes: 
            for edge in node.edges: 
                if edge not in edges and edge not in self.conn_edges: 
                    edges.append(edge)
        return edges 
    
    def update_border(self): 
        node_cloud = QPolygonF([node.pos for node in self.nodes])
        self.bounding_rect = node_cloud.boundingRect()
        self.move_button_pos = self.bounding_rect.center()
        if self.nodes[0].left_line: 
            self.expand_button_pos = QPointF(self.bounding_rect.topLeft().x() - 60, self.bounding_rect.topLeft().y() - 60)
        else: 
            self.expand_button_pos = QPointF(self.bounding_rect.topRight().x() + 60, self.bounding_rect.topRight().y() - 60)
        self.lock_button_pos = QPointF(self.bounding_rect.center().x() - 30, self.bounding_rect.bottom() + 60)
        self.label_button_pos = QPointF(self.bounding_rect.center().x() + 30, self.bounding_rect.bottom() + 60)

        lines: list[LineString] = [LineString([edge.v[0].pos.toTuple(), edge.v[1].pos.toTuple()]) for edge in self.internal_edges]

        merged = unary_union(lines)    # merge all lines
        corridor = merged.buffer(50)   # width around lines

        if corridor.geom_type == "Polygon":
            border = corridor.exterior
        elif corridor.geom_type == "MultiPolygon":
            border = [poly.exterior for poly in corridor.geoms]

        polygons = list(polygonize(border))
  
        self.border = []
        for poly in polygons:
            qpoly = QPolygonF([QPointF(x, y) for x, y in poly.exterior.coords])
            self.border.append(qpoly)

    def determine_pivot_buttons(self): 
        self.pivot_buttons_pos = []
        dist_from_group = 150

        # to provent that the bounding box can't be a vertical or horizontal line 
        self.bounding_rect.setTop(self.bounding_rect.top() - 1)
        self.bounding_rect.setBottom(self.bounding_rect.bottom() + 1)
        self.bounding_rect.setLeft(self.bounding_rect.left() - 1)
        self.bounding_rect.setRight(self.bounding_rect.right() + 1)

        edges_rect = [
            QLineF(self.bounding_rect.topLeft(), self.bounding_rect.topRight()),
            QLineF(self.bounding_rect.topRight(), self.bounding_rect.bottomRight()),
            QLineF(self.bounding_rect.bottomRight(), self.bounding_rect.bottomLeft()),
            QLineF(self.bounding_rect.bottomLeft(), self.bounding_rect.topLeft()),
        ]

        for i, conn_edge in enumerate(self.conn_edges):
            
            line = QLineF(self.conn_nodes[i].pos, conn_edge.other(self.conn_nodes[i]).pos)

            points = []
            
            for edge in edges_rect:
                edge_type, edge_point = edge.intersects(line)

                if edge_type == QLineF.IntersectionType.UnboundedIntersection:
                    if self.bounding_rect.contains(edge_point.x(), edge_point.y()): 
                        direction = QLineF(line.p1(), line.p2())
                        direction.setLength(1.0) 
                        points.append(edge_point + (direction.p2() - direction.p1()) * dist_from_group)
            if len(points) > 0: 
                self.pivot_buttons_pos.append(
                    max(points, 
                        key=lambda p: (p - self.conn_nodes[i].pos).x()**2 + (p - self.conn_nodes[i].pos).y()**2
                    )
                )
