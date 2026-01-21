import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io

def pack_rectangles(parts):
    """
    Runs the packing algorithm in multiple orientation modes (Landscape vs Portrait)
    and returns the single best (densest/squarest) layout.
    """
    def _run_sim(mode):
        # 1. Prepare Rects based on Mode
        sim_rects = []
        for p in parts:
            for _ in range(p['count']):
                w, h = p['width'], p['height']
                
                # Orientation Logic
                if mode == 'LANDSCAPE':
                    if h > w: w, h = h, w
                elif mode == 'PORTRAIT':
                    if w > h: w, h = h, w
                # 'MIXED' leaves them as-is (random input)
                
                sim_rects.append({
                    'w': w, 'h': h, 
                    'label': p['label'],
                    'orig_L': p.get('orig_L', h), 
                    'orig_W': p.get('orig_W', w),
                    'orig_H': p.get('orig_H', 0.0)
                })
        
        sim_rects.sort(key=lambda r: -r['h'])
        
        # 2. Hunt for Best Width
        total_area = sum(r['w'] * r['h'] for r in sim_rects)
        ideal_side = math.sqrt(total_area)
        max_part_w = max(r['w'] for r in sim_rects)
        
        candidate_widths = set([
            max_part_w, max_part_w * 1.5, max_part_w * 2.0, max_part_w * 3.0,
            ideal_side, ideal_side * 1.1, ideal_side * 0.9, ideal_side * 1.25
        ])
        
        local_best = None
        local_best_score = float('inf')

        for target_w in candidate_widths:
            if target_w < max_part_w: continue
            
            placed, shelf_y, shelf_h, cursor_x, max_x = [], 0, 0, 0, 0
            
            for r in sim_rects:
                if cursor_x + r['w'] > target_w:
                    shelf_y += shelf_h
                    shelf_h = 0
                    cursor_x = 0
                
                placed.append({**r, 'x': cursor_x, 'y': shelf_y})
                cursor_x += r['w']
                shelf_h = max(shelf_h, r['h'])
                max_x = max(max_x, cursor_x)
            
            total_h = shelf_y + shelf_h
            area = max_x * total_h
            aspect = max_x / total_h if total_h > 0 else 1000
            
            # Score: Minimize Area, Penalize Skinny Towers
            score = area * (1 + 0.2 * abs(1 - aspect))
            
            if score < local_best_score:
                local_best_score = score
                local_best = placed
                
        return local_best, local_best_score

    # RUN THE TOURNAMENT
    layout_L, score_L = _run_sim('LANDSCAPE')
    layout_P, score_P = _run_sim('PORTRAIT')
    
    # Return the winner (Lower score is better)
    return layout_L if score_L < score_P else layout_P

def render_layout(placed_rects, title="Layout Preview"):
    # (Existing render code remains unchanged)
    if not placed_rects: return None
    
    max_x = max(r['x'] + r['w'] for r in placed_rects)
    max_y = max(r['y'] + r['h'] for r in placed_rects)
    
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_xlim(0, max_x * 1.1)
    ax.set_ylim(0, max_y * 1.1)
    ax.set_aspect('equal')
    ax.set_title(title)
    ax.set_xlabel("mm")
    ax.set_ylabel("mm")
    
    labels = list(set(r['label'] for r in placed_rects))
    colors = plt.cm.tab10.colors
    color_map = {lbl: colors[i % len(colors)] for i, lbl in enumerate(labels)}
    
    for r in placed_rects:
        ax.add_patch(mpatches.Rectangle((r['x'], r['y']), r['w'], r['h'], linewidth=1, edgecolor='black', facecolor=color_map[r['label']], alpha=0.7))
        if r['w'] > 0.4 and r['h'] > 0.2:
            ax.text(r['x'] + r['w']/2, r['y'] + r['h']/2, r['label'].split('GRM')[-1][:6] if 'GRM' in r['label'] else r['label'][:5], ha='center', va='center', fontsize=6, color='white')
    
    # Legend
    label_dims = {r['label']: (r.get('orig_L', r['h']), r.get('orig_W', r['w']), r.get('orig_H', 0.0)) for r in placed_rects}
    legend_patches = [mpatches.Patch(color=color_map[lbl], label=f"{lbl} ({label_dims[lbl][0]:.2f}*{label_dims[lbl][1]:.2f}*{label_dims[lbl][2]:.2f}mm)") for lbl in labels]
    ax.legend(handles=legend_patches, loc='upper right', fontsize=6)
    
    
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf