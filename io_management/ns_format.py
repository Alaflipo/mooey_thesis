import json
import math 
from PySide6.QtCore import QPointF

from elements.network import Network, Node, Edge

diag = 1/math.sqrt(2)

port_offset = [ QPointF(-1,0)
              , QPointF(-diag,diag)
              , QPointF(0,1)
              , QPointF(diag,diag)
              , QPointF(1,0)
              , QPointF(diag,-diag)
              , QPointF(0,-1)
              , QPointF(-diag,-diag)
              ]

def read_ns_network(stations, lines):
    network = Network(file_path=stations)
    with open(stations) as fp:
        data = json.load(fp)
        assert data['type'] == "FeatureCollection"
        for feat in data['features']:
            geom = feat['geometry']
            if geom['type']=="Point":
                prop = feat['properties']
                name = prop['id'] 
                label = prop['name']
                x, y = geom['coordinates']
                network.nodes[name] = Node( x, -y, name, label )
        
    with open(lines) as tl:
        train_lines = json.load(tl)
        edges: dict[str, Edge] = {}
        for train in train_lines: 
            line_id = train['lijn']
            for i, id in enumerate(train['station_ids'][:-1]): 
                s_id = str(train['station_ids'][i])
                t_id = str(train['station_ids'][i+1])
                color = train['color']
                edge_id_1 = f'{s_id}-{t_id}'
                edge_id_2 = f'{t_id}-{s_id}'
                if edge_id_1 in edges: 
                    edges[edge_id_1].color.append(color)
                    edges[edge_id_1].line_id.append(line_id)
                    network.metro_lines[edge_id_1].append(edges[edge_id_1])
                elif edge_id_2 in edges: 
                    edges[edge_id_2].color.append(color)
                    edges[edge_id_2].line_id.append(line_id)
                    network.metro_lines[edge_id_2].append(edges[edge_id_2])
                elif s_id in network.nodes and t_id in network.nodes and not edge_id_2 in edges and not edge_id_1 in edges: 
                    s = network.nodes[s_id]
                    t = network.nodes[t_id]
                    e = Edge(s,t)
                    s.edges.append(e)
                    t.edges.append(e)
                    e.color = [color]
                    e.line_id = [line_id]
                    network.edges.append(e)
                    edges[edge_id_1] = e 
                    network.metro_lines[edge_id_1] = [e]
    create_front_stations(network)

    return network, data

def create_front_stations(network: Network): 
    front_edges: list[Edge] = []
    front_stations: list[Node] = []

    for node in network.nodes.values(): 
        if len(node.edges) >= 8: 
            groups: dict[int, list[Edge]] = {i:[] for i in range(8)}
            for edge in node.edges: 
                other = edge.other(node)
                closest_port = node.check_for_closer_port(other.pos)
                groups[closest_port].append(edge)
            
            for i, group in groups.items(): 
                if len(group) <= 1: continue 

                pos = node.pos + port_offset[i]/100
                front_id = node.name+f'_{i}'
                front_station = Node(pos.x(), pos.y(), front_id, label='')
                front_stations.append(front_station)

                front_edge = Edge(front_station, node)
                front_edges.append(front_edge)
                front_edge.color = []
                front_edge.line_id = []

                front_station.edges.append(front_edge)

                # add the new edge 
                node.edges.append(front_edge)

                for edge in group: 
                    id_dest = edge.id(node)
                    edge.v[id_dest] = front_station
                    front_station.edges.append(edge)
                    front_edge.color += edge.color
                    front_edge.line_id += edge.line_id
                    # remove the old edge 
                    node.edges.remove(edge)

    for edge in front_edges: 
        network.edges.append(edge)
    for node in front_stations: 
        network.nodes[node.name] = node
