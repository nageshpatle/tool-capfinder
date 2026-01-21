"""
Layout Packer Module
Implements a simple shelf-based bin packing algorithm for capacitor layout visualization.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io
import base64

def pack_rectangles(parts):
    """
    Pack rectangles using a simple shelf algorithm.
    
    Args:
        parts: List of dicts with keys: 'label', 'width', 'height', 'count'
    
    Returns:
        List of placed rectangles: {'x', 'y', 'w', 'h', 'label'}
    """
    # Expand parts by count
    rects = []
    for p in parts:
        for i in range(p['count']):
            # Try both orientations, prefer wider-than-tall
            w, h = p['width'], p['height']
            orig_L, orig_W, orig_H = p.get('orig_L', h), p.get('orig_W', w), p.get('orig_H', 0.0)
            if h > w:
                w, h = h, w  # Rotate to landscape
            rects.append({'w': w, 'h': h, 'label': p['label'], 'orig_L': orig_L, 'orig_W': orig_W, 'orig_H': orig_H})
    
    if not rects:
        return []
    
    # Sort by height descending (shelf packing heuristic)
    rects.sort(key=lambda r: -r['h'])
    
    placed = []
    shelf_y = 0
    shelf_h = 0
    cursor_x = 0
    
    # Determine a reasonable bin width (sum of all widths / sqrt(n))
    total_area = sum(r['w'] * r['h'] for r in rects)
    bin_width = max(r['w'] for r in rects) * 2  # At least 2 of the widest
    bin_width = max(bin_width, total_area ** 0.5)  # Or sqrt of total area
    
    for r in rects:
        # Does it fit on the current shelf?
        if cursor_x + r['w'] > bin_width:
            # Move to next shelf
            shelf_y += shelf_h
            shelf_h = 0
            cursor_x = 0
        
        # Place the rectangle
        placed.append({
            'x': cursor_x,
            'y': shelf_y,
            'w': r['w'],
            'h': r['h'],
            'label': r['label'],
            'orig_L': r.get('orig_L', r['h']),
            'orig_W': r.get('orig_W', r['w']),
            'orig_H': r.get('orig_H', 0.0)
        })
        
        cursor_x += r['w']
        shelf_h = max(shelf_h, r['h'])
    
    return placed


def render_layout(placed_rects, title="Layout Preview"):
    """
    Render placed rectangles to a matplotlib figure.
    
    Args:
        placed_rects: List of {'x', 'y', 'w', 'h', 'label'}
        title: Title for the plot
    
    Returns:
        Base64-encoded PNG image string
    """
    if not placed_rects:
        return None
    
    # Calculate bounds
    max_x = max(r['x'] + r['w'] for r in placed_rects)
    max_y = max(r['y'] + r['h'] for r in placed_rects)
    
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_xlim(0, max_x * 1.1)
    ax.set_ylim(0, max_y * 1.1)
    ax.set_aspect('equal')
    ax.set_title(title)
    ax.set_xlabel("mm")
    ax.set_ylabel("mm")
    
    # Color map for different labels
    labels = list(set(r['label'] for r in placed_rects))
    colors = plt.cm.tab10.colors
    color_map = {lbl: colors[i % len(colors)] for i, lbl in enumerate(labels)}
    
    for r in placed_rects:
        rect = mpatches.Rectangle(
            (r['x'], r['y']), r['w'], r['h'],
            linewidth=1, edgecolor='black', facecolor=color_map[r['label']],
            alpha=0.7
        )
        ax.add_patch(rect)
        
        # Add label inside if rect is big enough
        if r['w'] > 0.5 and r['h'] > 0.3:
            ax.text(
                r['x'] + r['w']/2, r['y'] + r['h']/2,
                r['label'][:10],
                ha='center', va='center', fontsize=6, color='white'
            )
    
    # Legend with dimensions
    # Group by label to get unique parts with their dimensions
    label_dims = {}
    for r in placed_rects:
        if r['label'] not in label_dims:
            label_dims[r['label']] = (
                r.get('orig_L', r['h']), 
                r.get('orig_W', r['w']), 
                r.get('orig_H', 0.0)
            )
    
    legend_patches = [
        mpatches.Patch(
            color=color_map[lbl], 
            label=f"{lbl} ({label_dims[lbl][0]:.2f}*{label_dims[lbl][1]:.2f}*{label_dims[lbl][2]:.2f} mm)"
        ) 
        for lbl in labels
    ]
    ax.legend(handles=legend_patches, loc='upper right', fontsize=6)
    
    plt.tight_layout()
    
    # Convert to base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100)
    plt.close(fig)
    buf.seek(0)
    
    return buf
