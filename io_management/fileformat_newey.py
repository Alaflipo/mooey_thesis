import json
from pathlib import Path

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPolygonF

from elements.network import Network, Node, Edge, Label
from elements.group import Group

def get_unique_filename(file_path:str, extension='json'):
    name = str(file_path).split('.')[0]
    path = Path(f'{name}.{extension}')
    counter = 1

    while path.exists():
        path = Path(f"{name}_{counter}.{extension}")
        counter += 1

    return path

def write_newey_file(network: Network) -> str: 
    file = {}

    nodes_json = []
    for node in network.nodes.values(): 
        node_json = {
            "name": node.name, 
            'label': node.label, 
            'pos': [node.pos.x(), node.pos.y()], 
            'geo_pos': [node.geo_pos.x(), node.geo_pos.y()],
            'left_line': node.left_line,
            'locked': node.locked,
            'stops': [stop for stop in node.stops], 
            'label_node': {
                "name": node.label_node.label_text, 
                "head": [node.label_node.head.x(), node.label_node.head.y()],
                "geo_head": [node.label_node.geo_head.x(), node.label_node.geo_head.y()],
                "end": [node.label_node.end.x(), node.label_node.end.y()],
                "center_label": node.label_node.center_label, 
                "port": node.label_node.port,
                "rectangle_points": [[point.x(), point.y()] for point in node.label_node.rectangle_points.toList()], 
                "type": node.station_type
            }
        }
        nodes_json.append(node_json)
    file["nodes"] = nodes_json 

    edges_json = []
    for edge in network.edges: 
        edge_json = {
            "nodes": [node.name for node in edge.v], 
            "ports": [(port if port != None else "None") for port in edge.port],
            "bend": [edge.bend.x(), edge.bend.y()] if edge.bend != None else "None",
            "color": edge.color,
            "line_id": edge.line_id, 
            "min_dist": edge.min_dist,
            "max_dist": edge.max_dist, 
            "locked": edge.locked
        }
        edges_json.append(edge_json)
    file['edges'] = edges_json

    file['layout_set'] = network.layout_set
    
    file_path = get_unique_filename(network.file_path, extension='newey')

    with file_path.open("w") as f:
        json.dump(file, f, indent=4)

    return file_path.name

def read_newey_file(file_path: str) -> Network:
    file_path = Path(file_path)

    with file_path.open("r") as f:
        data = json.load(f)

    network = Network(file_path=file_path)

    ### Nodes 
    for node_json in data["nodes"]:

        node = Node(
            *node_json["pos"],
            name=node_json["name"],
            label=node_json["label"]
        )

        node.pos = QPointF(*node_json["pos"])
        node.geo_pos = QPointF(*node_json["geo_pos"])
        node.left_line = node_json["left_line"]
        node.locked = node_json["locked"]
        node.station_type = node_json["type"] if "type" in node_json else ""
        node.stops = node_json["stops"] if "stops" in node_json else []

        # Label Node
        ln = node_json["label_node"]

        label_node = Label(
            node=node,
            label=ln["name"]
        )

        label_node.head = QPointF(*ln["head"])
        label_node.geo_head = QPointF(*ln["geo_head"])
        label_node.end = QPointF(*ln["end"])
        label_node.center_label = ln["center_label"]
        label_node.port = ln["port"]

        label_node.rectangle_points = QPolygonF(
            [QPointF(x, y) for x, y in ln["rectangle_points"]]
        )

        # add it to the node
        node.label_node = label_node
        if label_node.port is not None: 
            node.ports[label_node.port] = label_node 

        # Add for nod lookup 
        network.nodes[node.name] = node

    #### Edges 

    metro_lines: dict[str, list[Node]] = {}
    metro_edges: dict[str, list[Edge]] = {}
    colors_lines: dict[str, str] = {}
    groups: dict[str, Group] = {}

    check=0
    for edge_json in data["edges"]:
        
        nodes = [network.nodes[name] for name in edge_json["nodes"]]
        edge = Edge(*nodes)

        edge.port = [ (None if p == "None" else int(p)) for p in edge_json["ports"]]

        if edge_json["bend"] != "None":
            edge.bend = QPointF(edge_json["bend"][0], edge_json["bend"][1])

        edge.color = edge_json["color"]
        edge.line_id = edge_json["line_id"]
        edge.min_dist = edge_json["min_dist"]
        edge.max_dist = edge_json["max_dist"] if "max_dist" in edge_json else None 
        edge.locked = edge_json["locked"] if "locked" in edge_json else True

        # add edges and ports to nodes 
        for i, node in enumerate(nodes): 
            node.edges.append(edge)
            if edge.port[i] != None: 
                node.ports[edge.port[i]] = edge 

        network.edges.append(edge)

        # guard for if the line_ids are not correctly saved (from old version)
        if type(edge.line_id) != list: edge.line_id = edge.color
        
        for i, id in enumerate(edge.line_id): 
            colors_lines[id] = edge.color[i]
            if id in metro_edges: metro_edges[id].append(edge)
            else: metro_edges[id] = [edge]
    
    for line in metro_edges: 
        nodes: list[Node] = []
        for edge in metro_edges[line]: 
            if edge.v[0] not in nodes: nodes.append(edge.v[0])
            if edge.v[1] not in nodes: nodes.append(edge.v[1])
        groups[line] = Group(nodes, line, colors_lines[line], edges=metro_edges[line])
    
    network.layout_set = data['layout_set']



    return network, groups

