from __future__ import annotations 

from math import inf, atan2, pi, sqrt

from PySide6.QtCore import QPointF, QLineF
from PySide6.QtGui import QVector2D
from PySide6.QtGui import QFont, QFontMetrics

from shapely.geometry import Polygon

def opposite_port( p ):
    return (p+4)%8

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

class Network:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.metro_lines: dict[str, list[Edge]] = []

        # Midpoint of the network
        self.midpoint: QPointF = QPointF(0,0)
        self.layout_set: bool = False 

    def clone(self):
        other = Network()
        other.midpoint = self.midpoint
        node_clones = dict()
        for k,v in self.nodes.items():
            other_v = Node(v.pos.x(), v.pos.y(), v.name, v.label)
            node_clones[v] = other_v
            other_v.geo_pos = v.geo_pos
            other.nodes[k] = other_v
        edge_clones = dict()
        for e in self.edges:
            a = other.nodes[ e.v[0].name ]
            b = other.nodes[ e.v[1].name ]
            other_e = Edge(a,b)
            other_e.color = e.color
            edge_clones[e] = other_e
            a.edges.append( other_e )
            b.edges.append( other_e )
            other.edges.append( other_e )
            other_e.bend = e.bend
            other_e.port = e.port[:] # new copy of list
        for v in self.nodes.values():
            node_clones[v].ports = [ edge_clones.get(e,None) for e in v.ports ]
        return other

    def scale_by_shortest_edge( self, lb ):
        min_length = min([ e.geo_vector(e.v[0]).length() for e in self.edges ])
        factor = lb/min_length
        for v in self.nodes.values():
            v.pos = factor * v.pos
            v.geo_pos = factor * v.geo_pos

    def evict_all_edges(self):
        for v in self.nodes.values():
            for e in v.edges:
                v.try_evict(e)
    
    def evict_all_labels(self): 
        for v in self.nodes.values():
            v.evict_label()

    def get_label_nodes(self): 
        node_labels: list[Node] = []
        for v in self.nodes.values():
            node_labels.append(v.label_node)
        return node_labels
    
    def calculate_mid_point(self): 
        self.midpoint = midpoint([node.geo_pos for node in self.nodes.values()])

        for line in self.deg_2_lines: 
            midpoint_line: QPointF = midpoint([node.geo_pos for node in line])
            for v in line: 
                v.left_line = midpoint_line.x() <= self.midpoint.x()

    def check_label_overlaps(self): 
        overlaps: list[tuple[Node]] = []
        for v1 in self.nodes.values(): 
            for v2 in self.nodes.values(): 
                if v1 == v2: continue 
                if (v2, v1) in overlaps: continue 
                if v1.label_node.overlaps(v2.label_node): 
                    overlaps.append((v1,v2))
        return overlaps 
    
    def label_overlaps_with_rect(self, rect): 
        for v in self.nodes.values(): 
            if v.label_node.rectangle_points.overlaps(rect): 
                return True
        return False 

    def find_degree_2_lines(self): 
        self.deg_2_lines: list[list[Node]] = []
        seen: dict = dict()
        for name, v in self.nodes.items(): 
            if name in seen: continue

            if len(v.edges) == 2:
                seen[name] = True 

                path1 = spacewalk( v.edges[0].other(v), v, seen )
                path2 = spacewalk( v.edges[1].other(v), v, seen )
                walk: list[Node] = path1 + [v] + [v for v in reversed(path2)]
                self.deg_2_lines.append(walk)
            else: # We skip degree 1 and > 2 because they will be taken into account with one of the walks 
                continue 
            
            print(len(walk), [node.label for node in walk])
            

class Node:
    def __init__(self, x, y, name: str, label:str = "" ):
        self.pos: QPointF = QPointF(x,y)
        self.geo_pos: QPointF = self.pos
        self.name: str = name
        self.label: str = label

        # Used for labeling
        self.label_node: Label = Label(self, label) 

        self.edges: list[Edge] = []
        self.ports = [None]*8

        self.left_line: bool = True 

    def set_position( self, x, y ):
        self.pos = QPointF(x,y)

    def neighbors(self):
        return [e.other(self) for e in self.edges]
    
    def sort_edges_by_geo(self):
        self.edges.sort(key=lambda e: e.geo_angle(self))
    def sort_edges(self):
        self.edges.sort(key=lambda e: e.angle(self))

    def set_label(self, port_number: int | None): 
        if port_number is not None: 
            self.port_number_label = port_number

    def assign(self, e: Edge, i: int, force=False) -> bool:
        if self.ports[i] is not None:
            if force: self.evict(self.ports[i])
            else: return False
        me = e.id(self)
        old_port = e.port[me]
        if old_port is not None: self.ports[old_port] = None
        e.port[me] = i
        self.ports[i] = e
        return True
    
    def assign_both_ends( self, e: Edge, i: int, force=False ):
        self.assign(e,i,force)
        e.other(self).assign( e, opposite_port(i), force )

    def evict( self, e: Edge ):
        me = e.id(self)
        assert self.ports[e.port[me]] == e
        self.ports[e.port[me]] = None
        e.port[me] = None
        e.bend = None

    def assign_label(self, new_port): 
        # First make sure that the label is evicted (if there is a new edge there we leave it)
        if self.label_node.port is not None and (type(self.ports[self.label_node.port]) == Label): 
            self.ports[self.label_node.port] = None 
        self.label_node.port = new_port
        self.ports[new_port] = self.label_node 

    def evict_label(self): 
        if self.label_node.port is not None: 
            self.ports[self.label_node.port] = None 
            self.label_node.port = None 

    # If the edge is connected to the vertex it will evict it 
    def try_evict( self, e: Edge ):
        if not e.free_at(self): self.evict(e)
    
    def is_deg2(self): 
        return len(self.edges) == 2

    def straighten_deg2( self, e: Edge ):
        port = e.port[e.id(self)]
        label_port = self.label_node.port 

        # If the label is in the direction of the straigten call we choose a different port 
        if label_port == opposite_port(port): 
            label_port = self.first_free_port(exceptions=[label_port])

        v = e.other(self)
        v.assign_label(label_port)
        while len(v.edges)==2:
            if v==self: break # loop?
            prev_e = e
            e = v.edges[0] if v.edges[0]!=prev_e else v.edges[1]
            # Make sure that the label port is reassigned to the port position of the first vertex in the straigten call
            e.other(v).assign_label(label_port)
            v.assign_both_ends(e,port,force=True)
            v = e.other(v)

    def is_straight_through( self ):
        if len(self.edges)==2:
            a = self.edges[0].port_at(self)
            b = self.edges[1].port_at(self)
            return a==opposite_port(b)

    def is_right_angle( self ):
        if len(self.edges)==2:
            a = self.edges[0].port_at(self)
            b = self.edges[1].port_at(self)
            return (a+2)%8==b or (b+2)%8==a
        else: return False

    def smoothen( self ):
        if self.is_right_angle():
            a = self.edges[0].port_at(self)
            b = self.edges[1].port_at(self)
            if (a+2)%8==b: a = (a-1)%8
            else: a = (a+1)%8
            self.assign(self.edges[0],a)
            self.assign(self.edges[1],opposite_port(a))
        else: return False

    def get_free_ports(self): 
        free_ports = []
        for i, port in enumerate(self.ports): 
            if port == None: free_ports.append(i)
        return free_ports
    
    def first_free_port(self, exceptions=[]): 
        for i, port in enumerate(self.ports): 
            if i in exceptions: 
                continue 
            if port is None: 
                return i 
        return None 

class Label: 

    def __init__(self, node: Node, label: str):
        self.label_text: str = label
        self.text_width = self.measure_text_width()

        self.node: Node = node 
        self.head: QPointF = node.pos + QPointF(self.text_width, 10)
        self.geo_head: QPointF = self.head
        self.port: int | None = None 

        self.rectangle_points = [None, None, None, None]

    def measure_text_width(self): 
        font = QFont("Arial", 15)
        metrics = QFontMetrics(font)
        return metrics.horizontalAdvance(self.label_text)
    
    def get_rectangle_port(self, port: int, label_dist: int): 
        end = self.node.pos + ((self.text_width + label_dist) * port_offset[port])
        return self.get_label_border(self.node.pos, end)
    
    def set_position( self, x, y ):
        self.head = QPointF(x,y)
        self.end = self.head + (self.text_width * port_offset[opposite_port(self.port)])
        
        self.rectangle_points = self.get_label_border(self.head, self.end)

    def get_label_border(self, start: QPointF, end: QPointF):
        normal = QLineF(start, end).normalVector()
        # The box height is 20 so we multiply by 10
        vector = (QVector2D(normal.dx(), normal.dy()).normalized() * 10).toPointF()
        rectangle_points = [end + vector, end - vector, start - vector, start + vector]
        return Polygon([(p.x(), p.y()) for p in rectangle_points])

    def overlaps(self, other: Label): 
        return self.rectangle_points.overlaps(other.rectangle_points) 


class Edge:
    def __init__(self, a, b):
        self.v: list[Node] = [a,b]
        self.port: list[None | int] = [None,None]
        self.bend = None
        self.color: str = '000000'
        self.line_id: str = ''
    
    def id(self,v):
        if self.v[0]==v: return 0
        if self.v[1]==v: return 1
        assert False

    def other(self, v):
        if self.v[0]==v: return self.v[1]
        if self.v[1]==v: return self.v[0]
        assert False

    def port_at(self, v):
        if self.v[0]==v: return self.port[0]
        if self.v[1]==v: return self.port[1]
        assert False

    # returns whether the edge is actually connected to v 
    def free_at(self,v):
        return self.port[self.id(v)]==None

    def direction(self,v):
        return QVector2D(self.v[1-self.id(v)].pos - v.pos).normalized()
    def geo_direction(self,v):
        return QVector2D(self.v[1-self.id(v)].geo_pos - v.geo_pos).normalized()
    
    def vector(self,v):
        return QVector2D(self.v[1-self.id(v)].pos - v.pos)
    def geo_vector(self,v):
        return QVector2D(self.v[1-self.id(v)].geo_pos - v.geo_pos)

    # CCW angles, start at 0 = left
    def angle(self,v):
        dir = self.vector(v)
        return pi-atan2(dir.y(),dir.x())
    def geo_angle(self,v):
        dir = self.geo_vector(v)
        return pi-atan2(dir.y(),dir.x())
    
    def consistent_ports(self):
        return self.port[0]==opposite_port(self.port[1])

def round_angle_to_port(angle):
    return int(((angle+pi/8)%(2*pi))/(pi/4))

def midpoint(points: list[QPointF]): 
    sum_x = 0 
    sum_y = 0 
    for v in points:
        sum_x += v.x()
        sum_y += v.y()
    return QPointF(sum_x / len(points), sum_y / len(points))

def spacewalk( v: Node, prev, seen ):
    seen[v.name] = True
    walk = []
    if v.is_deg2():
        v0 = v.edges[0].other(v)
        v1 = v.edges[1].other(v)
        next = v0 if v1==prev else v1
        # We want to add deg 1 and deg > 2 to the walk because they do belong to the part of the metro line
        if next.is_deg2():
            if not next.name in seen:
                walk = spacewalk( next, v, seen )
        else: 
            walk.append(next)
    walk.append(v)
    return walk
