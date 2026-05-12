import math
import itertools
import pandas as pd
import streamlit as st
from rectpack import newPacker
import plotly.graph_objects as go

st.set_page_config(page_title="ALX plateberegning", layout="wide")

try:
    st.image("logo.png", width=500)
except FileNotFoundError:
    st.warning("Logo file 'logo.png' not found")

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

# Aluminum density in kg/mm³ (2.7 g/cm³ = 0.0000027 kg/mm³)
ALUMINUM_DENSITY = 0.0000027

# Profile weights per meter (kg/m)
CORNER_POST_WEIGHT_PER_M = 1.492  # Hjørnestender
WIDTH_PROFILE_WEIGHT_PER_M = 1.044  # Breddeprofil
DEPTH_PROFILE_WEIGHT_PER_M = 1.044  # Dybdeprofil
CORNER_KNIGHT_WEIGHT_EACH = 0.259  # Hjørneknute (always 8 pieces)
FRAME_PROFILE_VERTICAL_WEIGHT_PER_M = 0.468  # Omrammingsprofil (vertical)
FRAME_PROFILE_HORIZONTAL_WEIGHT_PER_M = 0.468  # Omrammingsprofil2 (horizontal)

SHEETS = {
    2: [(1250, 2500), (1250, 2000)],
    3: [(1250, 2500)],
}


def safe(x):
    return max(1, int(round(x)))


def sheet_area_from_size(sheet_size):
    sw, sh = map(int, sheet_size.split(" x "))
    return sw * sh


def calculate_weight(w, h, thickness):
    """Calculate weight in kg for a rectangular aluminum part"""
    volume = w * h * thickness  # mm³
    weight_kg = volume * ALUMINUM_DENSITY
    return round(weight_kg, 3)


def calculate_profile_weights(W, H, D, split_doors=True, door_split_offset=0, quantity=1):
    """Calculate total weight of all profiles"""
    # Hjørnestender (4 pieces) - cut length = Height
    corner_post_length_m = H / 1000  # Convert mm to meters
    corner_post_weight_total = 4 * corner_post_length_m * CORNER_POST_WEIGHT_PER_M
    
    # Breddeprofil (4 pieces) - cut length = W - 149mm
    width_profile_length_m = (W - 149) / 1000
    width_profile_weight_total = 4 * width_profile_length_m * WIDTH_PROFILE_WEIGHT_PER_M
    
    # Dybdeprofil (4 pieces) - cut length = D - 149mm
    depth_profile_length_m = (D - 149) / 1000
    depth_profile_weight_total = 4 * depth_profile_length_m * DEPTH_PROFILE_WEIGHT_PER_M
    
    # Hjørneknute (8 pieces always)
    corner_knight_weight_total = 8 * CORNER_KNIGHT_WEIGHT_EACH
    
    # Omrammingsprofil (vertical) - 2 pieces, cut length = H-25
    frame_vertical_length_m = (H - 25) / 1000
    frame_vertical_weight = 2 * frame_vertical_length_m * FRAME_PROFILE_VERTICAL_WEIGHT_PER_M
    
    # Omrammingsprofil2 (horizontal) - depends on split doors
    if split_doors:
        # Split doors: Use same formula as N1004 (left and right)
        half_w = W / 2
        left_frame_horizontal = half_w - 46 + door_split_offset
        right_frame_horizontal = half_w - 46 - door_split_offset
        
        # Ensure positive lengths
        left_frame_horizontal = max(0, left_frame_horizontal)
        right_frame_horizontal = max(0, right_frame_horizontal)
        
        left_length_m = left_frame_horizontal / 1000
        right_length_m = right_frame_horizontal / 1000
        
        frame_horizontal_weight = 2 * left_length_m * FRAME_PROFILE_HORIZONTAL_WEIGHT_PER_M + \
                                 2 * right_length_m * FRAME_PROFILE_HORIZONTAL_WEIGHT_PER_M
    else:
        # Single door: Use W-86
        frame_horizontal_length_m = (W - 86) / 1000
        frame_horizontal_weight = 2 * frame_horizontal_length_m * FRAME_PROFILE_HORIZONTAL_WEIGHT_PER_M
    
    total_profile_weight = (corner_post_weight_total + 
                           width_profile_weight_total + 
                           depth_profile_weight_total + 
                           corner_knight_weight_total +
                           frame_vertical_weight +
                           frame_horizontal_weight)
    
    return {
        "hjørnestender": round(corner_post_weight_total, 2),
        "breddeprofiler": round(width_profile_weight_total, 2),
        "dybdeprofiler": round(depth_profile_weight_total, 2),
        "hjørneknuter": round(corner_knight_weight_total, 2),
        "omrammingsprofil_vertikal": round(frame_vertical_weight, 2),
        "omrammingsprofil_horisontal": round(frame_horizontal_weight, 2),
        "total": round(total_profile_weight, 2)
    }


def make_door_split(W, split_offset=0, split_doors=True):
    if split_doors:
        # Split doors: Two N1004 profiles (left and right)
        half_w = W / 2
        left_n1004 = safe(half_w - 46 + split_offset)
        right_n1004 = safe(half_w - 46 - split_offset)
        left_w = left_n1004 + 58  # Add back the 46+12 for door width calculation
        right_w = right_n1004 + 58
        return left_n1004, right_n1004, left_w, right_w, True
    else:
        # Single door: One N1004 profile
        n1004 = safe(W - 88)
        return n1004, 0, 0, 0, False


def make_parts(W, H, D, split_back=False, quantity=1, door_split_offset=0, split_doors=True):
    if split_doors:
        left_n1004, right_n1004, left_w, right_w, is_split = make_door_split(W, door_split_offset, split_doors)
        n1004_display = f"{left_n1004} / {right_n1004}"
    else:
        n1004_display, left_w, right_w, _, is_split = make_door_split(W, door_split_offset, split_doors)
        n1004_display = str(n1004_display)

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

    # Base parts (always included) - NO N1004 here, it's a profile not sheet metal
    parts = [
        {"name": "Ytre sidevegg", "w": side_w, "h": side_h, "t": 2, "pcs": 2},
        {"name": "Indre sidevegg", "w": inner_side_w, "h": inner_side_h, "t": 2, "pcs": 2},

        {"name": "Ytre bakvegg", "w": back_w_split, "h": back_h, "t": 2, "pcs": back_pcs},
        {"name": "Indre bakvegg", "w": inner_back_w_split, "h": inner_back_h, "t": 2, "pcs": back_pcs},

        {"name": "Ytertak", "w": safe(W + 132), "h": safe(D + 121), "t": 3, "pcs": 1},
        {"name": "Innertak", "w": safe(W + 34), "h": safe(D + 41), "t": 2, "pcs": 1},

        {"name": "Mont.plate", "w": safe(H - 112), "h": safe(W - 117), "t": 3, "pcs": 1},
        {"name": "Z-vinkel", "w": safe(W - 200), "h": 94, "t": 3, "pcs": 2},
    ]
    
    # Add door parts
    if is_split:
        ytre_venstre_w = safe(left_w - 12)
        indre_venstre_w = safe(left_w - 22)
        ytre_hoyre_w = safe(right_w - 12)
        indre_hoyre_w = safe(right_w - 22)
        
        door_parts = [
            {"name": "Ytre venstre dør", "w": ytre_venstre_w, "h": safe(H - 37), "t": 2, "pcs": 1},
            {"name": "Indre venstre dør", "w": indre_venstre_w, "h": safe(H - 48), "t": 2, "pcs": 1},
            {"name": "Ytre høyre dør", "w": ytre_hoyre_w, "h": safe(H - 37), "t": 2, "pcs": 1},
            {"name": "Indre høyre dør", "w": indre_hoyre_w, "h": safe(H - 48), "t": 2, "pcs": 1},
        ]
        parts.extend(door_parts)
    else:
        # Single door scenario
        ytre_door_w = safe(W - 24)  # Full width minus gaps on both sides
        indre_door_w = safe(W - 44)  # Full width minus inner gaps
        
        door_parts = [
            {"name": "Ytre dør", "w": ytre_door_w, "h": safe(H - 37), "t": 2, "pcs": 1},
            {"name": "Indre dør", "w": indre_door_w, "h": safe(H - 48), "t": 2, "pcs": 1},
        ]
        parts.extend(door_parts)

    expanded = []

    for p in parts:
        total_pcs = int(p["pcs"] * quantity)
        for i in range(total_pcs):
            weight = calculate_weight(p["w"], p["h"], p["t"])
            expanded.append({
                "id": f'{p["name"]}_{i + 1}',
                "name": p["name"],
                "w": p["w"],
                "h": p["h"],
                "t": p["t"],
                "area": p["w"] * p["h"],
                "weight": weight,
            })

    return pd.DataFrame(expanded), n1004_display


def pack_group(df, thickness, sheet_plan):
    items = df[df["t"] == thickness].copy().reset_index(drop=True)

    innertak_items = items[items["name"] == "Innertak"].copy()
    other_items = items[items["name"] != "Innertak"].sort_values("area", ascending=False).reset_index(drop=True)
    items = pd.concat([innertak_items, other_items], ignore_index=True)

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
                "part_weight": row["weight"],
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
        candidates = [(1250, 2500), (1250, 2000)]
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
        score = (sheet_count, scrap_pct, total_sheet_area)

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
            "part_weight": row["weight"],
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

        actual_sheet_count = packed["sheet_no"].nunique()
        first_sheet_no = packed["sheet_no"].min()
        display_packed = packed[packed["sheet_no"] == first_sheet_no].copy()
        display_packed["sheet_no"] = 1

        used_sheets = display_packed[["thickness", "sheet_no", "sheet_size"]].drop_duplicates()
        total_sheet_area = used_sheets["sheet_size"].apply(sheet_area_from_size).sum()
        total_part_area = display_packed["part_area"].sum()
        scrap_pct = 100 * (1 - total_part_area / total_sheet_area) if total_sheet_area else 0.0

        score = (actual_sheet_count, scrap_pct, total_sheet_area)

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
    best = None

    for cabinets_per_group in range(quantity, 0, -1):
        remainder = quantity % cabinets_per_group if quantity % cabinets_per_group != 0 else 0

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
                    "weight": r["part_weight"],
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
            groups_needed = quantity // cabinets_per_group
            sheets_per_cabinet = actual_sheets / cabinets_per_group

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
                        "weight": r["part_weight"],
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
    final_groups = []
    scrap_map = get_sheet_scrap_map(base_packed_df)

    for thickness in sorted(base_packed_df["thickness"].unique()):
        thickness_base = base_packed_df[base_packed_df["thickness"] == thickness].copy()

        good_parts = []
        bad_parts = []

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

        if quantity <= 1:
            bad_once_df["run_qty"] = 1
            bad_once_df["layout_type"] = "repeat_bad"
            final_groups.append(bad_once_df)
            continue

        next_sheet_no = 1
        existing_groups_this_thickness = [
            g for g in final_groups
            if not g.empty and int(g["thickness"].iloc[0]) == thickness
        ]
        if existing_groups_this_thickness:
            existing_df = pd.concat(existing_groups_this_thickness, ignore_index=True)
            next_sheet_no = int(existing_df["sheet_no"].max()) + 1

        best_grouping = find_optimal_cabinet_grouping(
            bad_once_df=bad_once_df,
            thickness=thickness,
            quantity=quantity,
            start_sheet_no=next_sheet_no
        )

        if best_grouping is None:
            bad_once_df["run_qty"] = quantity
            bad_once_df["layout_type"] = "repeat_bad"
            final_groups.append(bad_once_df)
            continue

        repacked_main = best_grouping["repacked"].copy()
        total_main_sheets = best_grouping["sheets_per_group"] * best_grouping["groups_needed"]
        repacked_main["run_qty"] = total_main_sheets
        repacked_main["layout_type"] = "repacked_bad"
        final_groups.append(repacked_main)

        if best_grouping["remainder_parts"] is not None and best_grouping["remainder_sheets"] > 0:
            remainder_packed = best_grouping["remainder_parts"].copy()
            remainder_packed["run_qty"] = best_grouping["remainder_sheets"]
            remainder_packed["layout_type"] = "repacked_bad"

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
        part_weight_single_layout = group["part_weight"].sum()
        sheet_area_total = sheet_area * run_qty
        part_area_total = part_area_single_layout * run_qty
        part_weight_total = part_weight_single_layout * run_qty
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
            "Vekt plater (kg)": round(part_weight_total, 2),
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
        weight_text = f"{r['part_weight']:.2f} kg"

        fig.add_annotation(
            x=x + w / 2,
            y=y + h / 2,
            text=f"<b>{i}</b><br>"
                 f"{r['part']}<br>"
                 f"<span style='font-size:13px; color:#ddd;'>{measurement}</span><br>"
                 f"<span style='font-size:11px; color:#aaa;'>{weight_text}</span>",
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

        sheet_data = packed_df[
            (packed_df["thickness"] == thickness) &
            (packed_df["sheet_no"] == sheet_no) &
            (packed_df["sheet_size"] == sheet_size) &
            (packed_df["layout_type"] == layout_type)
        ]

        if col_index % 2 == 0:
            cols = st.columns(2)

        sw, sh = map(int, sheet_size.split(" x "))
        run_qty = int(sheet_data["run_qty"].iloc[0])

        sheet_area = sheet_area_from_size(sheet_size)
        part_area = sheet_data["part_area"].sum()
        part_weight = sheet_data["part_weight"].sum()
        scrap_pct = 100 * (1 - part_area / sheet_area)

        title = f"Sheet {sheet_no} • {sheet_size} • {thickness} mm"

        with cols[col_index % 2]:
            caption_text = f"{title} • {layout_type}"
            if run_qty > 1:
                caption_text += f" • ×{run_qty}"
            caption_text += f" • Skrap {scrap_pct:.2f}% • Vekt {part_weight:.2f} kg"
            if run_qty > 1:
                caption_text += f" (Totalt: {part_weight * run_qty:.2f} kg)"

            st.caption(caption_text)
            fig = draw_sheet(sw, sh, sheet_data, title)
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                    "staticPlot": True,
                    "responsive": True
                }
            )

        col_index += 1


def calculate_base_layout(W, H, D, door_split_offset=0, split_doors=True):
    parts_df, n1004 = make_parts(W, H, D, split_back=False, quantity=1, door_split_offset=door_split_offset, split_doors=split_doors)

    all_results = []
    back_split_needed = False

    for thickness in sorted(parts_df["t"].unique()):
        best = try_all_sheet_combinations(parts_df, thickness)

        if best is None:
            back_split_needed = True
            break

        all_results.append(best["packed"])

    if back_split_needed:
        parts_df, n1004 = make_parts(W, H, D, split_back=True, quantity=1, door_split_offset=door_split_offset, split_doors=split_doors)
        all_results = []

        for thickness in sorted(parts_df["t"].unique()):
            best = try_all_sheet_combinations(parts_df, thickness)

            if best is None:
                return pd.DataFrame(), True, n1004

            all_results.append(best["packed"])

    if not all_results:
        return pd.DataFrame(), False, n1004

    return pd.concat(all_results, ignore_index=True), False, n1004


st.title("ALX plateforbruk")

with st.form("form"):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.caption("Bredde")  # Small label
        W = st.number_input("", min_value=400, value=800, step=50, label_visibility="collapsed")
    
    with col2:
        st.caption("Høyde")
        H = st.number_input("", min_value=400, value=1200, step=50, label_visibility="collapsed", key="H")
    
    with col3:
        st.caption("Dybde")
        D = st.number_input("", min_value=230, value=400, step=50, label_visibility="collapsed", key="D")
    
    with col4:
        st.caption("Antall")
        Q = st.number_input("", min_value=1, value=1, step=1, label_visibility="collapsed", key="Q")
    
    with col5:
        split_doors = st.checkbox("Deling", value=False)
    
    with col6:
        if split_doors:
            st.caption("Offset +/- venstre/høyre")
            door_split_offset = st.number_input(
                "",
                min_value=-500,
                max_value=500,
                value=0,
                step=50,
                key="door_split_offset",
                label_visibility="collapsed"
            )
        else:
            door_split_offset = 0
    
    submitted = st.form_submit_button("Kalkuler", type="primary")

if submitted:
    base_packed, failed, n1004_display = calculate_base_layout(W, H, D, door_split_offset=door_split_offset, split_doors=split_doors)

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
                bad_scrap_threshold=35
            )

        if final_packed.empty:
            st.error("No valid quantity nesting found.")
        else:
            # Calculate profile weights (only for display, not affecting cutting)
            profile_weights = calculate_profile_weights(W, H, D, split_doors, door_split_offset, Q)
            
            montasjeplate_w = safe(H - 112)
            montasjeplate_h = safe(W - 117)
            lysapning_w = safe(W - 128)
            lysapning_h = safe(H - 110)
            
            # Calculate door widths based on split_doors setting
            if split_doors:
                half_w = W / 2
                left_n1004 = safe(half_w - 48 + door_split_offset)
                right_n1004 = safe(half_w - 48 - door_split_offset)
                left_outer = safe(left_n1004 + 58 - 12)
                right_outer = safe(right_n1004 + 58 - 12)
                left_inner = safe(left_n1004 + 58 - 22)
                right_inner = safe(right_n1004 + 58 - 22)
                
                # Calculate frame horizontal lengths for split doors
                left_frame_h = max(0, half_w - 46 + door_split_offset)
                right_frame_h = max(0, half_w - 46 - door_split_offset)
                
                st.markdown(
                    f"**Dørbredde (venstre/høyre):** {left_n1004} / {right_n1004} mm  \n"
                    f"**Montasjeplate BxH:** {safe(W - 136)} × {montasjeplate_w} mm  \n"
                    f"**Lysåpning BxH:** {lysapning_w} × {lysapning_h} mm  \n"
                )
            else:
                n1004_single = safe(W - 88)
                frame_horizontal_length = W - 86
                st.markdown(
                    f"**Dørbredde** {n1004_single} mm  \n"
                    f"**Montasjeplate BxH:** {safe(W - 136)} × {montasjeplate_w} mm  \n"
                    f"**Lysåpning BxH:** {lysapning_w} × {lysapning_h} mm  \n"
                )

            st.subheader("Plater", divider="gray")

            if not final_packed.empty:
                detail_df = summarize_quantity_optimized(final_packed)
                total_sheets = int(detail_df["Fysiske plater"].sum())
                total_area = int(detail_df["Plateareal totalt"].sum())
                total_parts = int(detail_df["Deler i layout"].sum())
                total_part_area = int(detail_df["Delareal totalt"].sum())
                total_sheet_weight = detail_df["Vekt plater (kg)"].sum()
                total_scrap_pct = 100 * (1 - total_part_area / total_area) if total_area > 0 else 0.0
                
                # Total weight including profiles
                total_weight_all = total_sheet_weight + (profile_weights["total"] * Q)

                # Metrics row
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                col1.metric("Total Plater", total_sheets)
                col2.metric("Vekt Plater", f"{total_sheet_weight:.2f} kg")
                col3.metric("Vekt Profiler", f"{profile_weights['total'] * Q:.2f} kg")
                col5.metric("Skrap plater %", f"{total_scrap_pct:.2f}%")
                col6.metric("Vekt Per Skap", f"{(total_sheet_weight/Q + profile_weights['total']):.2f} kg" if Q > 0 else "N/A")

                # Show profile weight breakdown with cut lengths
                with st.expander("📦 Profiler", expanded=False):
                    # Calculate cut lengths for display
                    corner_post_length_mm = H
                    width_profile_length_mm = W - 149
                    depth_profile_length_mm = D - 149
                    frame_vertical_length_mm = H - 25
                    
                    if split_doors:
                        half_w = W / 2
                        left_frame_h_mm = max(0, half_w - 46 + door_split_offset)
                        right_frame_h_mm = max(0, half_w - 46 - door_split_offset)
                        frame_horizontal_display = f"{int(round(left_frame_h_mm))} / {int(round(right_frame_h_mm))} mm"
                        st.write(f"**Hjørnestender (4 stk):** {profile_weights['hjørnestender']:.2f} kg (Lengde: {corner_post_length_mm} mm)")
                        st.write(f"**Breddeprofiler (4 stk):** {profile_weights['breddeprofiler']:.2f} kg (Lengde: {width_profile_length_mm} mm)")
                        st.write(f"**Dybdeprofiler (4 stk):** {profile_weights['dybdeprofiler']:.2f} kg (Lengde: {depth_profile_length_mm} mm)")
                        st.write(f"**Hjørneknuter (8 stk):** {profile_weights['hjørneknuter']:.2f} kg (Fast vekt pr stk)")
                        st.write(f"**Omrammingsprofil (vertikal, 2 stk):** {profile_weights['omrammingsprofil_vertikal']:.2f} kg (Lengde: {frame_vertical_length_mm} mm)")
                        st.write(f"**Omrammingsprofil2 (horisontal, 2 stk):** {profile_weights['omrammingsprofil_horisontal']:.2f} kg (Lengde: {frame_horizontal_display})")
                        st.write(f"**Sum profiler per skap:** {profile_weights['total']:.2f} kg")
                        st.write(f"**Sum profiler totalt ({Q} stk):** {profile_weights['total'] * Q:.2f} kg")
                    else:
                        frame_horizontal_length_mm = W - 86
                        st.write(f"**Hjørnestender (4 stk):** {profile_weights['hjørnestender']:.2f} kg (Lengde: {corner_post_length_mm} mm)")
                        st.write(f"**Breddeprofiler (4 stk):** {profile_weights['breddeprofiler']:.2f} kg (Lengde: {width_profile_length_mm} mm)")
                        st.write(f"**Dybdeprofiler (4 stk):** {profile_weights['dybdeprofiler']:.2f} kg (Lengde: {depth_profile_length_mm} mm)")
                        st.write(f"**Hjørneknuter (8 stk):** {profile_weights['hjørneknuter']:.2f} kg (Fast vekt pr stk)")
                        st.write(f"**Omrammingsprofil (vertikal, 2 stk):** {profile_weights['omrammingsprofil_vertikal']:.2f} kg (Lengde: {frame_vertical_length_mm} mm)")
                        st.write(f"**Omrammingsprofil2 (horisontal, 2 stk):** {profile_weights['omrammingsprofil_horisontal']:.2f} kg (Lengde: {frame_horizontal_length_mm} mm)")
                        st.write(f"**Sum profiler per skap:** {profile_weights['total']:.2f} kg")
                        st.write(f"**Sum profiler totalt ({Q} stk):** {profile_weights['total'] * Q:.2f} kg")

                st.write("**Plateformat:**")
                for thickness in sorted(detail_df["Tykkelse"].unique()):
                    thickness_data = detail_df[detail_df["Tykkelse"] == thickness]
                    sheets_by_size = thickness_data.groupby("Plateformat")["Fysiske plater"].sum()
                    weight_by_thickness = thickness_data["Vekt plater (kg)"].sum()

                    st.write(f"*{thickness}mm:* Vekt: {weight_by_thickness:.2f} kg")
                    for size, count in sheets_by_size.items():
                        st.write(f"  • {int(count)}x {size}")

            show_sheet_views(final_packed)
