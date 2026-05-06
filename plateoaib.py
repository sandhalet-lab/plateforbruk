import math
import itertools
import pandas as pd
import streamlit as st
from rectpack import newPacker
import plotly.graph_objects as go

st.set_page_config(page_title="ALX plateberegning", layout="wide")

st.image("logo.png", width=500)  

# ----- Dark theme for the whole page -----
st.markdown(
    """
    <style>
    .main {
        background-color: #111;
        color: #eee;
        font-size: 18px;
    }
    body, .block-container, .main {
        font-size: 18px;
    }
    h1, h2, h3 {
        color: #ccc;
    }
    h1 { font-size: 2.5rem; }
    h2 { font-size: 2rem; }
    h3 { font-size: 1.75rem; }
    .stMetricValue {
        color: #ccc;
        font-size: 1.5rem;
    }
    div[data-testid="stMarkdownContainer"] {
        font-size: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

SHEETS = {
    2: [(1250, 2500), (1250, 2000)],
    3: [(1250, 2500)],
}

def safe(x):
    return max(1, int(round(x)))

def sheet_area_from_size(sheet_size):
    sw, sh = map(int, sheet_size.split(" x "))
    return sw * sh

def make_parts(W, H, D, split_back=False, quantity=1):
    # Doors: split WIDTH when cabinet is wide
    if W > 1000:
        door_pcs = 2
        W_half = W / 2
        door_w = safe(W_half - 58)
        door_h = safe(H - 37)
    else:
        door_pcs = 1
        door_w = safe(W - 100)
        door_h = safe(H - 37)

    side_w = safe(H + 34)
    side_h = safe(D - 42)
    inner_side_w = safe(H + 3)
    inner_side_h = safe(D - 53)

    if split_back:
        back_w_split = safe(W / 2 - 18)
        inner_back_w_split = safe(W / 2 - 29)
        back_pcs = 2
    else:
        back_w_split = safe(W - 42)
        inner_back_w_split = safe(W - 53)
        back_pcs = 1

    back_h = safe(H + 34)
    inner_back_h = safe(H + 3)

    parts = [
        {"name": "Ytre sidevegg", "w": side_w, "h": side_h, "t": 2, "pcs": 2},
        {"name": "Indre sidevegg", "w": inner_side_w, "h": inner_side_h, "t": 2, "pcs": 2},

        {"name": "Ytre bakvegg", "w": back_w_split, "h": back_h, "t": 2, "pcs": back_pcs},
        {"name": "Indre bakvegg", "w": inner_back_w_split, "h": inner_back_h, "t": 2, "pcs": back_pcs},

        {"name": "Ytertak",  "w": safe(W + 132), "h": safe(D + 121), "t": 3, "pcs": 1},
        {"name": "Innertak", "w": safe(W + 34),  "h": safe(D + 41),  "t": 2, "pcs": 1},

        {"name": "Ytre dør", "w": door_w, "h": door_h, "t": 2, "pcs": door_pcs},
        {"name": "Indre dør", "w": safe(door_w - 10), "h": safe(door_h - 11), "t": 2, "pcs": door_pcs},

        {"name": "Mont.plate", "w": safe(H - 112), "h": safe(W - 117), "t": 3, "pcs": 1},
        {"name": "Z-vinkel", "w": safe(W - 200), "h": 94, "t": 3, "pcs": 2},
    ]

    expanded = []

    for p in parts:
        total_pcs = int(p["pcs"] * quantity)

        for i in range(total_pcs):
            expanded.append({
                "id": f'{p["name"]}_{i + 1}',
                "name": p["name"],
                "w": p["w"],
                "h": p["h"],
                "t": p["t"],
                "area": p["w"] * p["h"],
            })

    return pd.DataFrame(expanded)

def pack_group(df, thickness, sheet_plan):
    items = df[df["t"] == thickness].copy().reset_index(drop=True)
    remaining = items.copy()
    packed_rows = []
    sheet_no = 0

    while len(remaining) > 0:
        best = None

        for sw, sh in sheet_plan:
            packer = newPacker(rotation=True)

            for _, r in remaining.iterrows():
                packer.add_rect(int(r["w"]), int(r["h"]), rid=r["id"])

            packer.add_bin(sw, sh)
            packer.pack()

            placed = packer.rect_list()

            if best is None or len(placed) > len(best["placed"]):
                best = {"sheet": (sw, sh), "placed": placed}

        if best is None or len(best["placed"]) == 0:
            break

        sheet_no += 1
        sw, sh = best["sheet"]
        used_ids = set()

        for b, x, y, w, h, rid in best["placed"]:
            row = remaining[remaining["id"] == rid].iloc[0]
            used_ids.add(rid)

            packed_rows.append({
                "thickness": int(row["t"]),
                "sheet_no": sheet_no,
                "sheet_size": f"{sw} x {sh}",
                "part": row["name"],
                "part_id": rid,
                "part_w": int(row["w"]),
                "part_h": int(row["h"]),
                "part_area": int(row["area"]),
                "x": int(x),
                "y": int(y),
                "placed_w": int(w),
                "placed_h": int(h),
                "sheet_w": int(sw),
                "sheet_h": int(sh),
                "run_qty": 1,
                "layout_type": "base",
            })

        remaining = remaining[~remaining["id"].isin(used_ids)].reset_index(drop=True)

    packed_df = pd.DataFrame(packed_rows)

    if packed_df.empty:
        return packed_df, remaining, None

    used_sheets = packed_df[["thickness", "sheet_no", "sheet_size"]].drop_duplicates()

    total_sheet_area = used_sheets["sheet_size"].apply(sheet_area_from_size).sum()
    total_part_area = packed_df["part_area"].sum()
    scrap_pct = 100 * (1 - total_part_area / total_sheet_area) if total_sheet_area else None

    return packed_df, remaining, scrap_pct

def try_all_sheet_combinations(df, thickness):
    if thickness == 2:
        candidates = [(1250, 2000), (1250, 2500)]
    else:
        candidates = SHEETS[thickness]

    best = None

    for counts in itertools.product(range(1, 8), repeat=len(candidates)):
        plan = []

        for (sw, sh), n in zip(candidates, counts):
            plan.extend([(sw, sh)] * n)

        packed, remaining, scrap = pack_group(df, thickness, plan)

        if len(remaining) > 0:
            continue

        used_sheets = packed[["thickness", "sheet_no", "sheet_size"]].drop_duplicates()

        total_sheet_area = used_sheets["sheet_size"].apply(sheet_area_from_size).sum()
        total_part_area = packed["part_area"].sum()
        scrap_pct = 100 * (1 - total_part_area / total_sheet_area) if total_sheet_area > 0 else 0.0
        sheet_count = used_sheets.shape[0]

        score = (scrap_pct, total_sheet_area, sheet_count)

        if best is None or score < best["score"]:
            best = {
                "packed": packed,
                "scrap": scrap_pct,
                "score": score,
                "plan": plan,
                "total_sheet_area": total_sheet_area,
            }

    return best

def pack_group_unlimited(df, thickness, sheet_size, start_sheet_no=1, layout_type="repacked_bad"):
    items = df[df["t"] == thickness].copy().reset_index(drop=True)

    if items.empty:
        return pd.DataFrame(), pd.DataFrame(), None

    sw, sh = sheet_size

    packer = newPacker(rotation=True)

    for _, r in items.iterrows():
        packer.add_rect(int(r["w"]), int(r["h"]), rid=r["id"])

    # Simulate unlimited sheets safely.
    for _ in range(len(items)):
        packer.add_bin(sw, sh)

    packer.pack()

    placed = packer.rect_list()
    placed_ids = set()
    packed_rows = []

    for b, x, y, w, h, rid in placed:
        row = items[items["id"] == rid].iloc[0]
        placed_ids.add(rid)

        packed_rows.append({
            "thickness": int(row["t"]),
            "sheet_no": int(start_sheet_no + b),
            "sheet_size": f"{sw} x {sh}",
            "part": row["name"],
            "part_id": rid,
            "part_w": int(row["w"]),
            "part_h": int(row["h"]),
            "part_area": int(row["area"]),
            "x": int(x),
            "y": int(y),
            "placed_w": int(w),
            "placed_h": int(h),
            "sheet_w": int(sw),
            "sheet_h": int(sh),
            "run_qty": 1,
            "layout_type": layout_type,
        })

    packed_df = pd.DataFrame(packed_rows)
    remaining = items[~items["id"].isin(placed_ids)].reset_index(drop=True)

    if packed_df.empty:
        return packed_df, remaining, None

    used_sheets = packed_df[["thickness", "sheet_no", "sheet_size"]].drop_duplicates()

    total_sheet_area = used_sheets["sheet_size"].apply(sheet_area_from_size).sum()
    total_part_area = packed_df["part_area"].sum()
    scrap_pct = 100 * (1 - total_part_area / total_sheet_area) if total_sheet_area else None

    return packed_df, remaining, scrap_pct

def choose_best_repack_for_bad_parts(df, thickness, start_sheet_no=1):
    """Repack bad parts and find best sheet size.
    
    Returns the first sheet layout (all sheets are identical) along with
    the actual number of sheets needed.
    """
    candidates = SHEETS[thickness]
    best = None

    for sheet_size in candidates:
        packed, remaining, scrap = pack_group_unlimited(
            df=df,
            thickness=thickness,
            sheet_size=sheet_size,
            start_sheet_no=start_sheet_no,
            layout_type="repacked_bad"
        )

        if len(remaining) > 0:
            continue

        # Count actual sheets used
        actual_sheet_count = packed["sheet_no"].nunique()
        
        # Get first sheet for display
        first_sheet_no = packed["sheet_no"].min()
        display_packed = packed[packed["sheet_no"] == first_sheet_no].copy()
        display_packed["sheet_no"] = 1

        used_sheets = display_packed[["thickness", "sheet_no", "sheet_size"]].drop_duplicates()
        total_sheet_area = used_sheets["sheet_size"].apply(sheet_area_from_size).sum()
        total_part_area = display_packed["part_area"].sum()
        scrap_pct = 100 * (1 - total_part_area / total_sheet_area) if total_sheet_area else 0.0
        sheet_count = used_sheets.shape[0]

        score = (total_sheet_area * actual_sheet_count, scrap_pct, sheet_count)

        if best is None or score < best["score"]:
            best = {
                "packed": display_packed,
                "remaining": remaining,
                "scrap": scrap_pct,
                "score": score,
                "sheet_size": sheet_size,
                "total_sheet_area": total_sheet_area,
                "actual_sheet_count": actual_sheet_count,
            }

    return best

def find_optimal_cabinet_grouping(bad_once_df, thickness, quantity, start_sheet_no=1):
    """Find optimal number of cabinets to nest together for bad parts repacking.
    
    Tests grouping sizes (1, 2, 3... N cabinets per layout) and returns
    the grouping that minimizes sheets per cabinet. Handles remainders properly.
    """
    best = None
    
    for cabinets_per_group in range(quantity, 0, -1):  # Try from largest to smallest
        if quantity % cabinets_per_group == 0:
            # Perfect divisor - no remainder
            remainder = 0
        else:
            # Has remainder - we'll handle it separately
            remainder = quantity % cabinets_per_group
        
        # Expand parts for this group size
        expanded_bad = []
        for cabinet_idx in range(cabinets_per_group):
            for _, r in bad_once_df.iterrows():
                expanded_bad.append({
                    "id": f"{r['part_id']}_C{cabinet_idx + 1}",
                    "name": r["part"],
                    "w": int(r["part_w"]),
                    "h": int(r["part_h"]),
                    "t": int(r["thickness"]),
                    "area": int(r["part_area"]),
                })
        
        bad_df = pd.DataFrame(expanded_bad)
        
        repack_result = choose_best_repack_for_bad_parts(
            df=bad_df,
            thickness=thickness,
            start_sheet_no=start_sheet_no
        )
        
        if repack_result is None:
            continue
        
        remaining = repack_result.get("remaining", pd.DataFrame())
        if len(remaining) > 0:
            continue
        
        repacked = repack_result["packed"].copy()
        actual_sheets = repack_result["actual_sheet_count"]
        
        if remainder == 0:
            groups_needed = quantity // cabinets_per_group
            sheets_per_cabinet = actual_sheets / cabinets_per_group
            total_physical_sheets = actual_sheets * groups_needed
            
            score = (sheets_per_cabinet, total_physical_sheets)
            
            if best is None or score < best["score"]:
                best = {
                    "repacked": repacked,
                    "sheets_per_group": actual_sheets,
                    "groups_needed": groups_needed,
                    "remainder_parts": None,
                    "remainder_sheets": 0,
                    "cabinets_per_group": cabinets_per_group,
                    "score": score,
                }
        else:
            # Has remainder - calculate sheets for remainder separately
            groups_needed = quantity // cabinets_per_group
            sheets_per_cabinet = actual_sheets / cabinets_per_group
            
            # Calculate remainder parts
            remainder_expanded = []
            for cabinet_idx in range(remainder):
                for _, r in bad_once_df.iterrows():
                    remainder_expanded.append({
                        "id": f"{r['part_id']}_R{cabinet_idx + 1}",
                        "name": r["part"],
                        "w": int(r["part_w"]),
                        "h": int(r["part_h"]),
                        "t": int(r["thickness"]),
                        "area": int(r["part_area"]),
                    })
            
            remainder_df = pd.DataFrame(remainder_expanded)
            remainder_repack = choose_best_repack_for_bad_parts(
                df=remainder_df,
                thickness=thickness,
                start_sheet_no=start_sheet_no + actual_sheets
            )
            
            if remainder_repack is None:
                continue
            
            remainder_check = remainder_repack.get("remaining", pd.DataFrame())
            if len(remainder_check) > 0:
                continue
            
            remainder_sheets = remainder_repack["actual_sheet_count"]
            total_physical_sheets = (actual_sheets * groups_needed) + remainder_sheets
            
            # Score considers: sheets per cabinet in main group, then total sheets
            score = (sheets_per_cabinet, total_physical_sheets)
            
            if best is None or score < best["score"]:
                best = {
                    "repacked": repacked,
                    "sheets_per_group": actual_sheets,
                    "groups_needed": groups_needed,
                    "remainder_parts": remainder_repack["packed"].copy(),
                    "remainder_sheets": remainder_sheets,
                    "cabinets_per_group": cabinets_per_group,
                    "score": score,
                }
    
    return best

def get_sheet_scrap_map(packed_df):
    scrap_map = {}

    for key, group in packed_df.groupby(["thickness", "sheet_no", "sheet_size"]):
        thickness, sheet_no, sheet_size = key
        sheet_area = sheet_area_from_size(sheet_size)
        part_area = group["part_area"].sum()
        scrap_pct = 100 * (1 - part_area / sheet_area)
        scrap_map[key] = scrap_pct

    return scrap_map

def total_physical_sheet_area(df):
    if df.empty:
        return 0

    total = 0

    for _, r in df[["thickness", "sheet_no", "sheet_size", "run_qty"]].drop_duplicates().iterrows():
        total += sheet_area_from_size(r["sheet_size"]) * int(r["run_qty"])

    return total

def total_physical_sheet_count(df):
    if df.empty:
        return 0

    total = 0

    for _, r in df[["thickness", "sheet_no", "sheet_size", "run_qty"]].drop_duplicates().iterrows():
        total += int(r["run_qty"])

    return total

def build_quantity_optimized_from_base(base_packed_df, quantity, bad_scrap_threshold):
    """Build quantity-optimized layout with intelligent bad part consolidation.
    
    For bad scrap parts, finds the optimal number of cabinets to group together
    so that parts are nested as efficiently as possible. Handles remainders.
    """
    final_groups = []
    scrap_map = get_sheet_scrap_map(base_packed_df)

    for thickness in sorted(base_packed_df["thickness"].unique()):
        thickness_base = base_packed_df[base_packed_df["thickness"] == thickness].copy()

        good_parts = []
        bad_parts = []

        # Split base sheets into good and bad sheets for this thickness.
        for key, group in thickness_base.groupby(["thickness", "sheet_no", "sheet_size"]):
            scrap_pct = scrap_map[key]

            if scrap_pct >= bad_scrap_threshold:
                bad_parts.append(group.copy())
            else:
                good_group = group.copy()
                good_group["run_qty"] = int(quantity)
                good_group["layout_type"] = "repeat_good"
                good_parts.append(good_group)

        if good_parts:
            final_groups.append(pd.concat(good_parts, ignore_index=True))

        if not bad_parts:
            continue

        bad_once_df = pd.concat(bad_parts, ignore_index=True)

        # Quantity 1 cannot benefit from pooling across multiple cabinets
        if quantity <= 1:
            bad_once_df["run_qty"] = 1
            bad_once_df["layout_type"] = "repeat_bad"
            final_groups.append(bad_once_df)
            continue

        # Find next available sheet_no
        next_sheet_no = 1
        existing_groups_this_thickness = [
            g for g in final_groups
            if not g.empty and int(g["thickness"].iloc[0]) == thickness
        ]
        if existing_groups_this_thickness:
            existing_df = pd.concat(existing_groups_this_thickness, ignore_index=True)
            next_sheet_no = int(existing_df["sheet_no"].max()) + 1

        # Find optimal cabinet grouping for bad parts
        best_grouping = find_optimal_cabinet_grouping(
            bad_once_df=bad_once_df,
            thickness=thickness,
            quantity=quantity,
            start_sheet_no=next_sheet_no
        )

        if best_grouping is None:
            # Fallback: simple repeat of base layout
            bad_once_df["run_qty"] = quantity
            bad_once_df["layout_type"] = "repeat_bad"
            final_groups.append(bad_once_df)
            continue

        # Build the final result with main group
        repacked_main = best_grouping["repacked"].copy()
        total_main_sheets = best_grouping["sheets_per_group"] * best_grouping["groups_needed"]
        repacked_main["run_qty"] = total_main_sheets
        repacked_main["layout_type"] = "repacked_bad"
        final_groups.append(repacked_main)

        # Handle remainder if it exists
        if best_grouping["remainder_parts"] is not None and best_grouping["remainder_sheets"] > 0:
            remainder_packed = best_grouping["remainder_parts"].copy()
            remainder_packed["run_qty"] = best_grouping["remainder_sheets"]
            remainder_packed["layout_type"] = "repacked_bad"
            
            # Adjust sheet numbers for remainder
            max_sheet_no = repacked_main["sheet_no"].max()
            remainder_packed["sheet_no"] = remainder_packed["sheet_no"] + int(max_sheet_no)
            
            final_groups.append(remainder_packed)

    if not final_groups:
        return pd.DataFrame()

    return pd.concat(final_groups, ignore_index=True)

def summarize_quantity_optimized(packed_df):
    rows = []

    for key, group in packed_df.groupby(["thickness", "sheet_no", "sheet_size"]):
        thickness, sheet_no, sheet_size = key
        run_qty = int(group["run_qty"].iloc[0])
        layout_type = group["layout_type"].iloc[0]

        sheet_area = sheet_area_from_size(sheet_size)
        part_area_single_layout = group["part_area"].sum()
        sheet_area_total = sheet_area * run_qty
        part_area_total = part_area_single_layout * run_qty
        scrap_pct = 100 * (1 - part_area_single_layout / sheet_area)

        rows.append({
            "Tykkelse": thickness,
            "Plate": sheet_no,
            "Plateformat": sheet_size,
            "Type": layout_type,
            "Kjøringer": run_qty,
            "Fysiske plater": run_qty,
            "Deler i layout": len(group),
            "Skrap % per layout": round(scrap_pct, 2),
            "Plateareal totalt": sheet_area_total,
            "Delareal totalt": part_area_total,
        })

    return pd.DataFrame(rows)

def draw_sheet(sheet_w, sheet_h, parts_df, title):
    fig = go.Figure()

    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=sheet_w, y1=sheet_h,
        line=dict(color="#555", width=2),
        fillcolor="#333"
    )

    for i, (_, r) in enumerate(parts_df.iterrows(), start=1):
        x = r["x"]
        y = r["y"]
        w = r["placed_w"]
        h = r["placed_h"]

        color = "rgba(0, 120, 255, 0.25)" if r["thickness"] == 2 else "rgba(255, 120, 0, 0.25)"

        fig.add_shape(
            type="rect",
            x0=x, y0=y, x1=x + w, y1=y + h,
            line=dict(color="#888", width=1.5),
            fillcolor=color
        )

        measurement = f"{int(r['part_w'])} × {int(r['part_h'])} mm"

        fig.add_annotation(
            x=x + w / 2,
            y=y + h / 2,
            text=f"<b>{i}</b><br>"
                 f"{r['part']}<br>"
                 f"<span style='font-size:13px; color:#ddd;'>{measurement}</span>",
            showarrow=False,
            font=dict(size=13, color="#eee"),
            align="center",
            bgcolor="rgba(0,0,0,0.6)",
            bordercolor="#666",
            borderwidth=1,
            borderpad=4,
        )

    fig.update_xaxes(range=[0, sheet_w], visible=False, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(range=[0, sheet_h], visible=False, autorange="reversed")

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#ccc")),
        paper_bgcolor="#111",
        plot_bgcolor="#333",
        margin=dict(l=10, r=10, t=50, b=20),
        width=300,
        height=600,
        showlegend=False,
        hovermode=False,
        dragmode=False,
    )

    return fig

def show_sheet_views(packed_df):
    """Display unique sheet layouts.
    
    Each unique cutting pattern is shown once with run_qty indicating
    how many times to repeat it.
    """
    
    # Get unique layouts
    layout_combinations = packed_df.groupby(
        ["thickness", "sheet_no", "sheet_size", "layout_type"], 
        as_index=False
    ).first().reset_index(drop=True)
    
    layout_combinations = layout_combinations.sort_values(
        ["thickness", "layout_type", "sheet_no"]
    ).reset_index(drop=True)
    
    col_index = 0
    cols = None
    
    for idx, layout_info in layout_combinations.iterrows():
        thickness = int(layout_info["thickness"])
        sheet_no = int(layout_info["sheet_no"])
        sheet_size = layout_info["sheet_size"]
        layout_type = layout_info["layout_type"]
        
        # Get all parts for this layout
        sheet_data = packed_df[
            (packed_df["thickness"] == thickness) &
            (packed_df["sheet_no"] == sheet_no) &
            (packed_df["sheet_size"] == sheet_size) &
            (packed_df["layout_type"] == layout_type)
        ]
        
        # Create new row of columns every 2 sheets
        if col_index % 2 == 0:
            cols = st.columns(2)
        
        sw, sh = map(int, sheet_size.split(" x "))
        run_qty = int(sheet_data["run_qty"].iloc[0])
        
        sheet_area = sheet_area_from_size(sheet_size)
        part_area = sheet_data["part_area"].sum()
        scrap_pct = 100 * (1 - part_area / sheet_area)
        
        title = f"Sheet {sheet_no} • {sheet_size} • {thickness} mm"
        
        with cols[col_index % 2]:
            caption_text = f"{title} • {layout_type}"
            if run_qty > 1:
                caption_text += f" • ×{run_qty}"
            caption_text += f" • Skrap {scrap_pct:.2f}%"
            
            st.caption(caption_text)
            fig = draw_sheet(sw, sh, sheet_data, title)
            st.plotly_chart(fig, use_container_width=True, 
                           config={"displayModeBar": False})
        
        col_index += 1

def calculate_base_layout(W, H, D):
    parts_df = make_parts(W, H, D, split_back=False, quantity=1)

    all_results = []
    back_split_needed = False

    for thickness in sorted(parts_df["t"].unique()):
        best = try_all_sheet_combinations(parts_df, thickness)

        if best is None:
            back_split_needed = True
            break

        all_results.append(best["packed"])

    if back_split_needed:
        parts_df = make_parts(W, H, D, split_back=True, quantity=1)
        all_results = []

        for thickness in sorted(parts_df["t"].unique()):
            best = try_all_sheet_combinations(parts_df, thickness)

            if best is None:
                return pd.DataFrame(), True

            all_results.append(best["packed"])

    if not all_results:
        return pd.DataFrame(), False

    return pd.concat(all_results, ignore_index=True), False

st.title("ALX plateforbruk")

with st.form("form"):
    c1, c2, c3, c4, c5 = st.columns(5)

    W = c1.number_input("Bredde", min_value=400, value=800, step=50)
    H = c2.number_input("Høyde", min_value=400, value=1200, step=50)
    D = c3.number_input("Dybde", min_value=230, value=400, step=50)
    Q = c4.number_input("Antall", min_value=1, value=1, step=1)

    bad_scrap_threshold = c5.number_input(
        "Optimaliser over skrap %",
        min_value=0,
        max_value=100,
        value=35,
        step=5
    )

    run = st.form_submit_button("Kalkuler")

if run:
    base_packed, failed = calculate_base_layout(W, H, D)

    if failed or base_packed.empty:
        st.error("No valid base nesting found.")
    else:
        if Q == 1:
            final_packed = base_packed.copy()
            final_packed["run_qty"] = 1
            final_packed["layout_type"] = "base"
        else:
            final_packed = build_quantity_optimized_from_base(
                base_packed_df=base_packed,
                quantity=Q,
                bad_scrap_threshold=bad_scrap_threshold
            )

        if final_packed.empty:
            st.error("No valid quantity nesting found.")
        else:
            st.subheader("Plater", divider="gray")

            if not final_packed.empty:
                detail_df = summarize_quantity_optimized(final_packed)
                total_sheets = int(detail_df["Fysiske plater"].sum())
                total_area = int(detail_df["Plateareal totalt"].sum())
                total_parts = int(detail_df["Deler i layout"].sum())
                total_part_area = int(detail_df["Delareal totalt"].sum())
                total_scrap_pct = 100 * (1 - total_part_area / total_area) if total_area > 0 else 0.0
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Plater", total_sheets)
                col4.metric("Total Skrap %", f"{total_scrap_pct:.2f}%")
                
                # Count sheets by thickness and size
                st.write("**Plateformat:**")
                for thickness in sorted(detail_df["Tykkelse"].unique()):
                    thickness_data = detail_df[detail_df["Tykkelse"] == thickness]
                    sheets_by_size = thickness_data.groupby("Plateformat")["Fysiske plater"].sum()
                    
                    st.write(f"*{thickness}mm:*")
                    for size, count in sheets_by_size.items():
                        st.write(f"  • {int(count)}x {size}")

            show_sheet_views(final_packed)
