from math import pi
from time import perf_counter

from elements.network import *

### GEOGRAPHIC COST CALCULATIONS ###

import numpy as np

def angle_error( a, b ):
    diff = abs(a-b) % (2*pi)
    return min(diff, 2*pi-diff)

def cost_matrix( v: Node):
    port_angles = [ i*(pi/4) for i in range(8) ]
    edge_angles = [ e.geo_angle(v) for e in v.edges ]
    return np.matrix( [ [ angle_error(pa,ea)**2 for pa in port_angles ] for ea in edge_angles ] )

# Two things to check for: 
# - We give priority to labels that are horizontal so 0 and 4 and don't want 2 and 6 and for the odd numbers they should be equal
# - We want labels that are on the outside to appear on the outside (either do this by a weighted middle point of the network or check whether labels point towards the outer face instead of an inner face)
def cost_matrix_labels(v: Node, label_strength: float, mid_point_x, old_node: Node): 
    port_angles = [ i*(pi/4) for i in range(8) ]
    edge_angles = []
    for i,e in enumerate(v.edges): 
        if old_node.locked: 
            edge_angles.append(port_angles[old_node.edges[i].port_at(old_node)])
        else: 
            edge_angles.append(e.geo_angle(v))
    # edge_angles = [ e.geo_angle(v) for e in v.edges ]
    port_edge_matrix = np.matrix( [ [ angle_error(pa,ea)**2 for pa in port_angles ] for ea in edge_angles ] )
    wl = [0.01 * label_strength, 0.02 * label_strength, 0.03 * label_strength]

    ### Based on lines add weights for labels 

    ### This is now commented out because of the feature (when dragging nodes are locked in place, but still the label positions I want to have fixed in place)
    # if the node is locked we want to choose the port of the old label 
    # if old_node.locked: 
    #     label_weights = [1 for i in range(8)]
    #     label_weights[old_node.label_node.port] = 0 
    #     return np.vstack([port_edge_matrix, label_weights])

    if len(v.edges) <= 2: 
        return left_wm(port_edge_matrix, wl) if v.left_line else right_wm(port_edge_matrix, wl)
    else : 
        return left_wm(port_edge_matrix, wl) if v.geo_pos.x() <= mid_point_x else right_wm(port_edge_matrix, wl)

    ### OLD
    # if v.geo_pos.x() <= mid_point_x: 
    #     return np.vstack([port_edge_matrix, np.array([wl[0] / 2, wl[1] /2 , wl[2], wl[1], wl[0], wl[1], wl[2], wl[1] / 2])])
    # else: 
    #     return np.vstack([port_edge_matrix, np.array([wl[0], wl[1], wl[2], wl[1] / 2, wl[0] / 2, wl[1] /2 , wl[2], wl[1]])])

# Left weighted matrix 
def left_wm(port_edge_matrix, wl): 
    return np.vstack([port_edge_matrix, np.array([wl[0] / 2, wl[1] /2 , wl[2], wl[1], wl[0], wl[1], wl[2], wl[1] / 2])])

# Right weighted matrix 
def right_wm(port_edge_matrix, wl): 
    return np.vstack([port_edge_matrix, np.array([wl[0], wl[1], wl[2], wl[1] / 2, wl[0] / 2, wl[1] /2 , wl[2], wl[1]])])

### ROUNDING ###

def assign_by_rounding( net: Network ):
    # the way it is implemented now, we can mess up the rotation system unnecessarily
    net.evict_all_labels()
    net.evict_all_edges()
    for v in net.nodes.values():
        for e in v.edges:
            port = round_angle_to_port(e.geo_angle(v))
            v.assign( e, port, force=False )
        v.assign_label(v.first_free_port())


### MATCHING ###

from scipy.optimize import linear_sum_assignment
def assign_by_local_matching( net: Network, label_strength: float ):
    net_clone = net.clone()
    clone_nodes = list(net_clone.nodes.values())
    net.evict_all_labels()
    net.evict_all_edges()
    for vi, v in enumerate(net.nodes.values()):
        # Cost matrix for labels
        costs = cost_matrix_labels(v, label_strength, net.midpoint.x(), clone_nodes[vi])
        _, cols = linear_sum_assignment(costs)
        for i,p in enumerate(cols[:-1]):
            v.assign( v.edges[int(i)], int(p) )

        # Assign the correct label 
        v.assign_label(int(cols[-1]))

### INTEGER LINEAR PROGRAMMING ###

### For the labeling I want a few things: 
### - Labels should appear on the same side of a line 

from ortools.linear_solver import pywraplp as lp
def assign_by_ilp( net: Network, bend_cost=1, label_hor_strength=1, label_side_strength=1):
    net_clone = net.clone()
    clone_nodes = list(net_clone.nodes.values())
    net.evict_all_labels()
    net.evict_all_edges()

    # bend cost is relative to squared angle errors

    solver: lp.Solver = lp.Solver.CreateSolver("SCIP")
    start = perf_counter()
    objective = solver.Sum([])
    portvars = dict()
    portvars_labels = dict()
    for vi, v in enumerate(net.nodes.values()):
        costs = cost_matrix_labels(v, label_hor_strength, net.midpoint.x(), old_node=clone_nodes[vi])
        for i,e in enumerate(v.edges):
            my_portvars = [solver.BoolVar(f'pass_{v.name}_{i}_{p}') for p in range(8)]
            for p in range(8):
                objective += costs[i,p] * my_portvars[p]
            # pick exactly one port for an edge
            solver.Add( solver.Sum(my_portvars)==1 )
            portvars[(v,e)] = my_portvars
        
        #### For labeling ####
        portvars_label = [solver.BoolVar(f'label_{v.name}_{p}') for p in range(8)]
        for p in range(8):
            objective += costs[len(costs)-1,p] * portvars_label[p]
        # Pick one port for each label 
        solver.Add( solver.Sum(portvars_label)==1 )
        portvars_labels[v] = portvars_label

        for p in range(8):
            # assign at most one (edge or LABEL) to a port
            solver.Add( solver.Sum([ portvars[(v,e)][p] for e in v.edges ] + [portvars_label[p]]) <= 1 )

    # consistent port assignment by identifying opposite sides of the same edge
    for e in net.edges:
        for p in range(8):
            solver.Add( portvars[(e.v[0],e)][p] == portvars[(e.v[1],e)][opposite_port(p)] )

    # bend penalty
    for v in net.nodes.values():
        if len(v.edges)==2:
            penalty = solver.BoolVar(f'bend_{v.name}')
            objective += bend_cost*penalty
            e = v.edges[0]
            f = v.edges[1]
            for p in range(8):
                solver.Add( penalty >= portvars[(v,e)][p] - portvars[(v,f)][opposite_port(p)])

    # labels on the same degree 2 line should be on the same side 
    for line in net.deg_2_lines: 
        if len(line[0].edges) > 2: line.pop(0)
        if len(line[len(line) - 1].edges) > 2: line.pop(len(line) - 1)
        for p in range(8): 
            for a, b in zip(line, line[1:]): 
                penalty = solver.BoolVar(f'label_{a.name}_{b.name}')
                objective += label_side_strength/10 * penalty
                solver.Add( penalty >= portvars_labels[a][p] - portvars_labels[b][p])
                # solver.Add( penalty <= portvars_labels[a][p] - portvars_labels[b][p])

    # # Labels on the same side
    # seen = dict()
    # for v in list(net.nodes.values()):
    #     if v.name in seen: continue
    #     if is_deg2(v):
    #         seen[v.name] = True
    #         path1 = spacewalk( v.edges[0].other(v), v, seen )
    #         path2 = spacewalk( v.edges[1].other(v), v, seen )
    #         walk = path1 + [v] + [v for v in reversed(path2)]
    #         print([node.label for node in walk])
    #         for a, b in zip(walk,walk[1:]): 
    #             print(a.label, b.label)
    #         # label same side 
    #         for p in range(8): 
    #             for a, b in zip(walk,walk[1:]):
    #                 if a == b: continue 
    #                 penalty = solver.BoolVar(f'label_{a.name}_{b.name}')
    #                 objective += label_side_strength/10 * penalty
    #                 solver.Add( penalty >= portvars_labels[a][p] - portvars_labels[b][p])
    #                 # solver.Add( penalty <= portvars_labels[a][p] - portvars_labels[b][p])

    solver.Minimize(objective)
    status = solver.Solve()
    runtime = perf_counter()-start
    print( "pa-ilp\tPort assignment ILP runtime (s)\t" + str(runtime) )
    print( 'Port assignment ILP runtime', runtime, 's' )
    print( 'Solver status', status )
    if status==0:
        net.evict_all_edges()
        for (v,e), x in portvars.items():
            for p in range(8):
                if x[p].solution_value()>0.5:
                    v.assign(e,p)

        # brute force simple port assignment
        for v, x in portvars_labels.items(): 
            for p in range(8): 
                if x[p].solution_value() > 0.5: 
                    v.assign_label(p)
        # for v in net.nodes.values(): 
        #     v.assign_label(v.first_free_port())
    else:
        print( 'Port assignment ILP infeasible' )
        print( "stats\tPort assignment ILP infeasible" )

def is_deg2(v: Node):
    return len(v.edges)==2

def spacewalk( v: Node, prev, seen ):
    seen[v.name] = True
    walk = []
    if is_deg2(v):
        v0 = v.edges[0].other(v)
        v1 = v.edges[1].other(v)
        next = v0 if v1==prev else v1
        if not next.name in seen:
            walk = spacewalk( next, v, seen )
    walk.append(v)
    return walk

def post_fix_overlap_ilp(net: Network, label_dist, label_hor_strength): 

    overlaps = net.check_label_overlaps()

    solver: lp.Solver = lp.Solver.CreateSolver("SCIP")
    start = perf_counter()
    objective = solver.Sum([])
    portvars_labels = dict()

    for vi, v in enumerate(net.nodes.values()):
        costs = cost_matrix_labels(v, label_hor_strength, net.midpoint.x(), old_node=v)

        free_ports = v.get_free_ports() + [v.label_node.port]
        
        #### For labeling ####
        portvars_label = [solver.BoolVar(f'label_{v.name}_{p}') for p in free_ports]
        for i, p in enumerate(free_ports):
            objective += costs[len(costs)-1,p] * portvars_label[i]
        # Pick one port for each label 
        solver.Add( solver.Sum(portvars_label)==1 )
        portvars_labels[v] = portvars_label   

        # Penalty if we choose a different port then previously assigned 
        for i in range(len(free_ports[:-1])):
            penalty = solver.BoolVar(f'label_{v.name}_{free_ports[i]}')
            objective += penalty
            solver.Add( penalty >= portvars_labels[v][i])
    
    # make sure that overlaps don't have the same port 
    for overlap in overlaps: 
        if len(overlap) == 2: 
            v1 = overlap[0]
            v2 = overlap[1]
            solver.Add( portvars_labels[v1][len(portvars_labels[v1]) - 1] + portvars_labels[v2][len(portvars_labels[v2]) - 1] <= 1)
        
        # bigger penalty if we stay on the edge overlap 
        if len(overlap) == 1: 
            v = overlap[0]
            penalty = solver.BoolVar(f'edge_overlap_{v.name}_{free_ports[i]}')
            objective += 10 * penalty
            solver.Add( penalty >= portvars_labels[v][len(portvars_labels[v]) - 1])
    
    ##### NOTE: For each vertex in which there is currently overlap with either edge or other label need to compare every configuration that is possible between them all.  ###

    # for overlap in overlaps: 
    #     v = overlap[0]
    #     p_candidates = []
    #     for p in v.get_free_ports(): 
    #         rect_to_check = v.label_node.get_rectangle_port(p, label_dist=label_dist)
    #         if not net.overlaps_with_label(rect_to_check): 
    #             p_candidates.append(p)
    #     candidates = [solver.BoolVar(f'label_{v.name}_{p}') for p in p_candidates]
    #     candidates()

    solver.Minimize(objective)
    status = solver.Solve()
    runtime = perf_counter()-start
    print( "pa-ilp\tPort assignment ILP runtime (s)\t" + str(runtime) )
    print( 'Port assignment ILP runtime', runtime, 's' )
    print( 'Solver status', status )
    if status==0:
        for v, x in portvars_labels.items(): 
            free_ports = v.get_free_ports() + [v.label_node.port]
            for i, p in enumerate(free_ports): 
                if x[i].solution_value() > 0.5: 
                    v.evict_label()
                    v.assign_label(p)
    else:
        print( 'Port assignment ILP infeasible' )
        print( "stats\tPort assignment ILP infeasible" )

def get_possible_ports(net: Network, label_dist: int) -> list[list[int]]:
    free_ports_mat = []
    for v in net.nodes.values():
        free_ports = []
        for p in v.get_free_ports(): 
            rect_to_check = v.label_node.get_rectangle_port(p, label_dist=label_dist)
            if not net.overlaps_with_label(rect_to_check): 
                free_ports.append(p)
        free_ports.append(v.label_node.port)
        free_ports_mat.append(free_ports)
    return free_ports_mat
