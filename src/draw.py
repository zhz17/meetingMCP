import csv
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

def parse_csv(filepath):
    """
    Parses the CSV file to extract lanes, nodes, and edges.
    Returns:
        lanes: dict {lane_index: lane_name} (empty if no swimlanes)
        nodes: dict {node_id: {type, label, lane_index, ...}}
        edges: list [{source, target, label}]
    """
    lanes = {}
    nodes = {}
    edges = []
    
    with open(filepath, 'r', encoding='utf-8-sig') as f: # Use utf-8-sig to handle BOM
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Remove potential whitespace from keys
                row = {k.strip(): v.strip() for k, v in row.items() if k}
                
                name = row.get('Name', '')
                shape_id = row.get('Id')
                
                # Check if it's a Swim Lane container
                if name == 'Swim Lane':
                    # Extract lane names from Text Area columns
                    lane_idx = 1
                    # Iterate through potential Text Area columns
                    for key in [f'Text Area {i}' for i in range(1, 10)]:
                        val = row.get(key)
                        if val:
                            lanes[lane_idx] = val
                            lane_idx += 1
                            
                # Check for Shapes (Process, Decision, Terminator, etc.)
                # Common Lucidchart shapes: Process, Decision, Terminator, Document, Data (I/O), Start, End
                elif name in ['Terminator', 'Process', 'Decision', 'Data (I/O)', 'Document', 'Start', 'End', 'Preparation', 'Manual Input']:
                    # Extract label from the first non-empty Text Area
                    label = ''
                    for key in [f'Text Area {i}' for i in range(1, 4)]:
                        val = row.get(key)
                        if val:
                            label = val
                            break
                    
                    contained_by = row.get('Contained By', '')
                    lane_index = None # Default: no lane
                    
                    if lanes and ':' in contained_by:
                        parts = contained_by.split(':')
                        if len(parts) > 1:
                            try:
                                lane_index = int(parts[1])
                            except ValueError:
                                pass
                    
                    nodes[shape_id] = {
                        'type': name,
                        'label': label,
                        'lane_index': lane_index
                    }
                    
                # Check for Lines
                elif name == 'Line':
                    source = row.get('Line Source')
                    target = row.get('Line Destination')
                    label = row.get('Text Area 1') # E.g. "Yes", "No"
                    
                    if source and target:
                        edges.append({
                            'source': source,
                            'target': target,
                            'label': label
                        })
            except Exception as e:
                print(f"Skipping row due to error: {e}, Row: {row}")
                
    return lanes, nodes, edges

def calculate_layout(nodes, edges, lanes):
    """
    Assigns (x, y) coordinates for nodes.
    Strategies:
    - If lanes exist: X = lane_index, Y = topological level
    - If no lanes: X = calculated spacing (simple BFS levels + horizontal spacing), Y = topological level
    Returns:
        layout: dict {node_id: (x, y)}
    """
    # Build adjacency list
    adj = {n: [] for n in nodes}
    in_degree = {n: 0 for n in nodes}
    
    # Filter edges to only include those connecting existing nodes
    valid_edges = []
    for edge in edges:
        u, v = edge['source'], edge['target']
        if u in nodes and v in nodes:
            adj[u].append(v)
            in_degree[v] = in_degree.get(v, 0) + 1
            valid_edges.append(edge)
            
    # Topological Sort / Level Assignment (BFS)
    levels = {}
    queue = [n for n in nodes if in_degree[n] == 0]
    
    # If cycle exists or no start node, pick arbitrary unvisited
    if not queue and nodes:
        queue = [list(nodes.keys())[0]] # Simplistic fallback
    
    visited = set()
    curr_level = 0
    
    while queue:
        next_queue = []
        for u in queue:
            if u in visited:
                continue
            visited.add(u)
            levels[u] = curr_level
            
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] <= 0:
                    next_queue.append(v)
        
        queue = next_queue
        curr_level += 1
        
    # Handle remaining disconnected components
    remaining = [n for n in nodes if n not in visited]
    while remaining:
        # Start a new component
        start_node = remaining[0]
        queue = [start_node]
        # Reset level for new component? Or continue below?
        # Let's continue below to avoid overlap
        curr_level += 1 
        
        while queue:
            next_queue = []
            for u in queue:
                if u in visited: 
                    continue
                visited.add(u)
                levels[u] = curr_level
                
                # Check neighbors even if not strictly topological (since cycle might exist)
                for v in adj[u]:
                     if v not in visited:
                        in_degree[v] -= 1
                        if in_degree[v] <= 0: # Or just add unvisited neighbors?
                            next_queue.append(v)
            if not next_queue and remaining:
                 # Check if we missed any from current component due to cycles
                 # Simplification: just pick next remaining
                 pass
            queue = next_queue
            curr_level += 1
        
        remaining = [n for n in nodes if n not in visited]

    layout = {}
    
    if lanes:
        # Swimlane Layout (Horizontal expansion, lanes as rows)
        min_lane = min(lanes.keys()) if lanes else 1
        sorted_nodes = sorted(nodes.keys(), key=lambda n: levels.get(n, 0))
        lane_next_x = {}
        
        for node_id in sorted_nodes:
            lane = nodes[node_id].get('lane_index')
            if lane is None:
                lane_y = min_lane - 1 # Above the first lane
            else:
                lane_y = lane
                
            level = levels.get(node_id, 0)
            
            # Base X is related to level to maintain topological flow
            min_x_for_level = level * 3.5 
            
            # Ensure nodes in the same lane expand horizontally without overlap
            current_lane_x = lane_next_x.get(lane_y, -3.5)
            x = max(min_x_for_level, current_lane_x + 2.5) 
            lane_next_x[lane_y] = x
            
            # Y corresponds to lane index to display lanes as rows
            y = lane_y * 2.5
            layout[node_id] = (x, y)
    else:
        # Auto-Layout without lanes (Left-to-right flow)
        nodes_by_level = {}
        for node_id, level in levels.items():
            if level not in nodes_by_level:
                nodes_by_level[level] = []
            nodes_by_level[level].append(node_id)
            
        for level, level_nodes in nodes_by_level.items():
            height = len(level_nodes)
            start_y = -(height - 1) / 2.0 * 2.0
            for i, node_id in enumerate(level_nodes):
                layout[node_id] = (level * 3.0, start_y + i * 2.0)
                
    return layout

def draw_flowchart(lanes, nodes, edges, layout, output_file='flowchart.png'):
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Constants
    NODE_HEIGHT = 0.8
    NODE_WIDTH = 1.4
    
    # Determine bounds for styling
    xs = [x for x, y in layout.values()]
    ys = [y for x, y in layout.values()]
    
    if not xs:
        print("Empty layout")
        return

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    # Margin
    margin_left = 6 if lanes else 2
    ax.set_xlim(min_x - margin_left, max_x + 2)
    ax.set_ylim(min_y - 2, max_y + 2)
    ax.invert_yaxis()
    ax.axis('off')

    # Draw Lanes (if any)
    if lanes:
        sorted_lanes = sorted(lanes.items())
        has_no_lane_nodes = any(data.get('lane_index') is None for data in nodes.values())
        
        if has_no_lane_nodes and sorted_lanes:
            first_lane_y = sorted_lanes[0][0] * 2.5
            sep_y = first_lane_y - 1.25
            ax.axhline(y=sep_y, color='lightgray', linestyle='--', alpha=0.5, zorder=0)

        for i, (idx, name) in enumerate(sorted_lanes):
            lane_y = idx * 2.5
            import textwrap
            wrapped_name = "\n".join(textwrap.wrap(name, width=15))
            ax.text(min_x - 1.2, lane_y, wrapped_name, 
                    ha='right', va='center', fontsize=12, fontweight='bold',
                    bbox=dict(facecolor='#f0f0f0', edgecolor='gray', boxstyle='round,pad=0.5'))
            # Draw separators half-way between indices
            if i < len(sorted_lanes) - 1:
                next_idx = sorted_lanes[i+1][0]
                next_lane_y = next_idx * 2.5
                sep_y = (lane_y + next_lane_y) / 2.0
                ax.axhline(y=sep_y, color='lightgray', linestyle='--', alpha=0.5, zorder=0)

    # Draw Edges
    for edge in edges:
        u, v = edge['source'], edge['target']
        if u not in layout or v not in layout:
            continue
            
        x1, y1 = layout[u]
        x2, y2 = layout[v]
        
        arrow = patches.FancyArrowPatch((x1, y1), (x2, y2),
                                        connectionstyle="arc3,rad=0",
                                        arrowstyle="-|>",
                                        color="#555555",
                                        mutation_scale=15,
                                        zorder=1)
        ax.add_patch(arrow)
        
        # Label
        label = edge.get('label')
        if label:
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            ax.text(mid_x, mid_y, label, 
                    fontsize=8, color='blue', 
                    bbox=dict(facecolor='white', edgecolor='none', alpha=0.6, pad=0))

    # Draw Nodes
    for node_id, (x, y) in layout.items():
        data = nodes[node_id]
        label = data['label']
        shape_type = data['type']
        
        # Wrap text
        import textwrap
        wrapped_label = "\n".join(textwrap.wrap(label, width=15)) if label else ""
        
        # Styles
        fc = "white"
        ec = "black"
        shape_patch = None
        
        if shape_type in ['Terminator', 'Start', 'End']:
            fc = "#ffe6cc" # Light orange
            shape_patch = patches.FancyBboxPatch((x - NODE_WIDTH/2, y - NODE_HEIGHT/2),
                                         NODE_WIDTH, NODE_HEIGHT,
                                         boxstyle="round,pad=0.1,rounding_size=0.4",
                                         ec=ec, fc=fc, zorder=2)
                                         
        elif shape_type == 'Decision':
            fc = "#fff2cc" # Light yellow
            verts = [
                (x, y - NODE_HEIGHT/1.5), 
                (x + NODE_WIDTH/1.3, y), 
                (x, y + NODE_HEIGHT/1.5), 
                (x - NODE_WIDTH/1.3, y)
            ]
            shape_patch = patches.Polygon(verts, closed=True, ec=ec, fc=fc, zorder=2)
            
        elif shape_type == 'Data (I/O)':
            fc = "#d5e8d4" # Light green
            # Parallelogram
            skew = 0.3
            verts = [
                (x - NODE_WIDTH/2 + skew, y - NODE_HEIGHT/2),
                (x + NODE_WIDTH/2 + skew, y - NODE_HEIGHT/2),
                (x + NODE_WIDTH/2 - skew, y + NODE_HEIGHT/2),
                (x - NODE_WIDTH/2 - skew, y + NODE_HEIGHT/2)
            ]
            shape_patch = patches.Polygon(verts, closed=True, ec=ec, fc=fc, zorder=2)
            
        elif shape_type == 'Document':
            fc = "#dae8fc" # Light blue
            # Rectangle with wavy bottom (simplified as regular rect distinct color)
            shape_patch = patches.Rectangle((x - NODE_WIDTH/2, y - NODE_HEIGHT/2),
                                     NODE_WIDTH, NODE_HEIGHT,
                                     ec=ec, fc=fc, zorder=2)
            # Add a small wave annotation or just keep color distinctive
            
        else: # Process, Manual Input, Preparation, etc.
            fc = "white"
            shape_patch = patches.Rectangle((x - NODE_WIDTH/2, y - NODE_HEIGHT/2),
                                     NODE_WIDTH, NODE_HEIGHT,
                                     ec=ec, fc=fc, zorder=2)
            
        if shape_patch:
            ax.add_patch(shape_patch)
            
        ax.text(x, y, wrapped_label, 
                ha='center', va='center', fontsize=8, zorder=3)

    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Flowchart saved to {output_file}")

if __name__ == '__main__':
    # Default to SalesProcess2.csv as requested for checking generic support
    # But let's verify logic works for both if needed.
    # For now, let's use the second one to test the non-swimlane logic.
    files = ['src/SalesProcess.csv', 'src/SalesProcess2.csv']
    
    for csv_path in files:
        print(f"Processing {csv_path}...")
        try:
            lanes, nodes, edges = parse_csv(csv_path)
            if not nodes:
                print(f"No nodes found in {csv_path}.")
                continue
                
            layout = calculate_layout(nodes, edges, lanes)
            output_name = csv_path.replace('.csv', '.png').replace('src/', '')
            draw_flowchart(lanes, nodes, edges, layout, output_file=output_name)
        except Exception as e:
            print(f"Error processing {csv_path}: {e}")

