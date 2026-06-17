import json

from elements.network import Network, Node, Edge

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
                edge_id_2 = f'{s_id}-{t_id}'
                if edge_id_1 in edges: 
                    edges[edge_id_1].color.append(color)
                    edges[edge_id_1].line_id.append(line_id)
                    network.metro_lines[edge_id_1].append(edges[edge_id_1])
                elif edge_id_2 in edges: 
                    edges[edge_id_2].color.append(color)
                    edges[edge_id_2].line_id.append(line_id)
                    network.metro_lines[edge_id_2].append(edges[edge_id_2])
                elif s_id in network.nodes and t_id in network.nodes: 
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

    return network, data
