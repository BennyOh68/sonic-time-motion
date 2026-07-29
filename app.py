import streamlit as st
import pandas as pd
import datetime
from datetime import time
import plotly.graph_objects as go
import json
from pathlib import Path
from google_sheets_helper import GoogleSheetsExporter

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Time & Motion Study",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Persistence helpers ──────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "log.json"
ACTIVITIES_FILE = DATA_DIR / "activities.json"
RIGS_FILE = DATA_DIR / "rigs.json"
PROJECTS_FILE = DATA_DIR / "projects.json"
ACCESS_LOG_FILE = DATA_DIR / "access_log.json"


# ── Authentication helpers ────────────────────────────────────────────────────
def log_access(username: str) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    try:
        with open(ACCESS_LOG_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        entries = []
    entries.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "username": username,
    })
    # Keep only last 200 entries
    if len(entries) > 200:
        entries = entries[-200:]
    with open(ACCESS_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


COLUMNS = [
    "Date", "Project", "JGP/Grout Hole", "Team/Rig", "Activity",
    "Start Time", "End Time", "Start Depth (m)", "End Depth (m)",
]


def check_authentication() -> bool:
    """Show login page if not authenticated. Returns True if authenticated."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = ""

    if st.session_state.authenticated:
        return True

    st.markdown("<h2 style='text-align:center;margin-top:3rem;'>🔐 Time & Motion Study</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input("Username", key="login_username", placeholder="Enter your username")
        st.text_input("Password", type="password", key="login_password", placeholder="Enter password")

        if st.button("Login", use_container_width=True, type="primary"):
            uname = st.session_state.login_username.strip()
            pwd = st.session_state.login_password
            # Simple credential check via secrets
            try:
                users = st.secrets["auth"]["users"]
            except (KeyError, FileNotFoundError):
                # Fallback for local dev
                users = "admin:admin123"

            for pair in users.split(","):
                u, p = pair.strip().split(":")
                if uname == u and pwd == p:
                    st.session_state.authenticated = True
                    st.session_state.username = uname
                    log_access(uname)
                    st.rerun()
            st.error("Invalid credentials")

        st.divider()
        # Show last 5 access log entries
        try:
            with open(ACCESS_LOG_FILE, "r", encoding="utf-8") as f:
                entries = json.load(f)
            if entries:
                st.caption("Recent logins:")
                for entry in entries[-5:]:
                    ts_raw = entry.get("timestamp", "")
                    try:
                        ts = datetime.datetime.fromisoformat(ts_raw).strftime("%d-%m-%Y %H:%M")
                    except (ValueError, TypeError):
                        ts = ts_raw
                    st.caption(f"  {ts} — {entry.get('username', '?')}")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    return False

# ── Session display ───────────────────────────────────────────────────────────
if st.session_state.get("authenticated"):
    cols = st.columns([10, 1])
    with cols[0]:
        pass  # title intentionally left blank as per original design
    with cols[1]:
        st.caption(f"👤 {st.session_state.username}")

st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

with st.sidebar:
    if st.button("🚪 Logout"):
        for key in ["authenticated", "username"]:
            st.session_state.pop(key, None)
        st.rerun()

# ── Guard ─────────────────────────────────────────────────────────────────────
if not check_authentication():
    st.stop()


def load_data() -> pd.DataFrame:
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        df = pd.DataFrame(records)
        for col in ["Start Depth (m)", "End Depth (m)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    return pd.DataFrame(columns=COLUMNS)


def save_data(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    records = df.to_dict(orient="records")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)


def load_activities() -> list:
    if ACTIVITIES_FILE.exists():
        with open(ACTIVITIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        "Mobilization", "Drilling Setup", "Casing Installation",
        "Coring", "SPT Test", "Water Testing", "Grouting",
        "Backfilling", "Demobilization",
    ]


def save_activities(acts: list) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(ACTIVITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(acts, f, indent=2)


def load_rigs() -> list:
    if RIGS_FILE.exists():
        with open(RIGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return ["Rig-A", "Rig-B", "Team-1", "Team-2"]


def save_rigs(rigs: list) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(RIGS_FILE, "w", encoding="utf-8") as f:
        json.dump(rigs, f, indent=2)


def load_projects() -> list:
    if PROJECTS_FILE.exists():
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return ["Project Alpha", "Project Beta"]


def save_projects(projects: list) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=2)


def parse_hole_id(hole_id: str) -> tuple:
    """Parse hole ID like 'JGP-01' or 'GH-02A' into (type, ref_no)."""
    if not hole_id:
        return ("JGP", "01")
    if hole_id.startswith("GH-"):
        return ("Grout Hole", hole_id[3:])
    elif hole_id.startswith("JGP-"):
        return ("JGP", hole_id[4:])
    # Fallback
    parts = hole_id.split("-", 1)
    if len(parts) == 2:
        htype = "Grout Hole" if parts[0] == "GH" else parts[0]
        return (htype, parts[1])
    return ("JGP", "01")


def load_row_into_sidebar(row: pd.Series) -> None:
    """Load a row's values into sidebar widget session state."""
    from datetime import datetime

    # Time
    try:
        st.session_state.start_time_input = datetime.strptime(
            str(row["Start Time"]), "%H:%M:%S"
        ).time()
        st.session_state.end_time_input = datetime.strptime(
            str(row["End Time"]), "%H:%M:%S"
        ).time()
    except (ValueError, KeyError):
        pass

    # Depth
    try:
        st.session_state.start_depth_input = float(row["Start Depth (m)"])
        st.session_state.end_depth_input = float(row["End Depth (m)"])
    except (ValueError, KeyError):
        pass

    # Date
    try:
        st.session_state.activity_date = datetime.strptime(
            str(row["Date"]), "%d-%m-%Y"
        ).date()
    except (ValueError, KeyError):
        pass

    # Dropdown values for pre-selection
    st.session_state.edit_project = str(row.get("Project", ""))
    st.session_state.edit_hole = str(row.get("JGP/Grout Hole", ""))
    st.session_state.edit_rig = str(row.get("Team/Rig", ""))
    st.session_state.edit_activity = str(row.get("Activity", ""))


# ── Initialize session state ─────────────────────────────────────────────────
if "log" not in st.session_state:
    st.session_state.log = load_data()
if "activity_list" not in st.session_state:
    st.session_state.activity_list = load_activities()
if "rig_list" not in st.session_state:
    st.session_state.rig_list = load_rigs()
if "project_list" not in st.session_state:
    st.session_state.project_list = load_projects()

# ── Edit mode state ──────────────────────────────────────────────────────────
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "editing_index" not in st.session_state:
    st.session_state.editing_index = None
if "edit_project" not in st.session_state:
    st.session_state.edit_project = ""
if "edit_hole" not in st.session_state:
    st.session_state.edit_hole = ""
if "edit_rig" not in st.session_state:
    st.session_state.edit_rig = ""
if "edit_activity" not in st.session_state:
    st.session_state.edit_activity = ""

# ── Row load pending flag (must be checked BEFORE widget instantiation) ─────
if "row_load_pending" not in st.session_state:
    st.session_state.row_load_pending = False
if "restore_selection_pending" not in st.session_state:
    st.session_state.restore_selection_pending = False
if "clear_selection_pending" not in st.session_state:
    st.session_state.clear_selection_pending = False
if "sync_date_pending" not in st.session_state:
    st.session_state.sync_date_pending = False
if "sync_date_value" not in st.session_state:
    st.session_state.sync_date_value = None
if "undo_snapshot" not in st.session_state:
    st.session_state.undo_snapshot = None

if st.session_state.row_load_pending:
    row_data = st.session_state.pending_row_data
    idx = st.session_state.pending_row_index

    try:
        st.session_state.start_time_input = datetime.datetime.strptime(
            str(row_data["Start Time"]), "%H:%M:%S"
        ).time()
        st.session_state.end_time_input = datetime.datetime.strptime(
            str(row_data["End Time"]), "%H:%M:%S"
        ).time()
    except (ValueError, KeyError):
        pass
    try:
        st.session_state.start_depth_input = float(row_data["Start Depth (m)"])
        st.session_state.end_depth_input = float(row_data["End Depth (m)"])
    except (ValueError, KeyError):
        pass
    try:
        st.session_state.activity_date = datetime.datetime.strptime(
            str(row_data["Date"]), "%d-%m-%Y"
        ).date()
    except (ValueError, KeyError):
        pass
    st.session_state.edit_project = str(row_data.get("Project", ""))
    st.session_state.edit_hole = str(row_data.get("JGP/Grout Hole", ""))
    st.session_state.edit_rig = str(row_data.get("Team/Rig", ""))
    st.session_state.edit_activity = str(row_data.get("Activity", ""))
    st.session_state.edit_mode = True
    st.session_state.editing_index = idx

    st.session_state.row_load_pending = False

# ── Sync sidebar activity_date from chart nav (must run BEFORE date_input widget) ─
if st.session_state.get("sync_date_pending", False):
    st.session_state.activity_date = st.session_state.sync_date_value
    st.session_state.sync_date_pending = False

# ── Sidebar: Data Entry ──────────────────────────────────────────────────────
with st.sidebar:
    if st.session_state.edit_mode:
        st.header("✏️ Edit Activity Entry")
    else:
        st.header("📝 Log New Activity")

    # ── Project dropdown + custom ──────────────────────────────────────────
    proj_options = st.session_state.project_list + ["✏️ Custom..."]

    # Pre-select in edit mode
    if st.session_state.edit_mode and st.session_state.edit_project:
        if st.session_state.edit_project in st.session_state.project_list:
            default_proj_idx = st.session_state.project_list.index(st.session_state.edit_project)
        else:
            default_proj_idx = len(proj_options) - 1  # Custom
        proj_choice = st.selectbox("Project Title", options=proj_options, index=default_proj_idx)
    else:
        proj_choice = st.selectbox("Project Title", options=proj_options)

    if proj_choice == "✏️ Custom...":
        default_val = st.session_state.edit_project if st.session_state.edit_mode else ""
        project = st.text_input(
            "Enter custom project",
            value=default_val,
            placeholder="Type project name...",
            key="custom_project",
        )
    else:
        project = proj_choice

    # ── Manage project list ────────────────────────────────────────────────
    with st.expander("⚙️ Edit Project List"):
        new_proj = st.text_input("Add new project to list", placeholder="e.g., Project Gamma")
        if st.button("➕ Add Project"):
            if new_proj.strip() and new_proj.strip() not in st.session_state.project_list:
                st.session_state.project_list.append(new_proj.strip())
                save_projects(st.session_state.project_list)
                st.success(f"'{new_proj.strip()}' added!")
                st.rerun()

        proj_to_remove = st.selectbox(
            "Remove project",
            options=[""] + st.session_state.project_list,
        )
        if proj_to_remove and st.button("🗑️ Remove Project"):
            st.session_state.project_list.remove(proj_to_remove)
            save_projects(st.session_state.project_list)
            st.success(f"'{proj_to_remove}' removed!")
            st.rerun()

    # ── Hole type radio + ref no ──────────────────────────────────────────
    # Parse hole ID in edit mode
    if st.session_state.edit_mode and st.session_state.edit_hole:
        parsed_type, parsed_ref = parse_hole_id(st.session_state.edit_hole)
        default_ref = parsed_ref
        default_type_idx = 0 if parsed_type == "JGP" else 1
    else:
        default_ref = "01"
        default_type_idx = 0

    ref_col, hole_col = st.columns([3, 2])
    with ref_col:
        hole_ref = st.text_input("Ref. No.", value=default_ref, placeholder="e.g., 01, 02A")
    with hole_col:
        hole_type = st.radio("Hole Type", options=["JGP", "Grout Hole"], index=default_type_idx, horizontal=True, label_visibility="collapsed")
    hole_prefix = "GH" if hole_type == "Grout Hole" else hole_type
    jgp_hole = f"{hole_prefix}-{hole_ref}"
    st.markdown(f"<span style='font-size:1.2em;font-weight:bold;color:white;'>Point ID: {jgp_hole}</span>", unsafe_allow_html=True)

    # ── Date picker ────────────────────────────────────────────────────────
    activity_date = st.date_input(
        "Activity Date",
        value=datetime.date.today(),
        format="DD-MM-YYYY",
        key="activity_date",
    )

    # ── Team/Rig dropdown + custom ───────────────────────────────────────
    rig_options = st.session_state.rig_list + ["✏️ Custom..."]

    # Pre-select in edit mode
    if st.session_state.edit_mode and st.session_state.edit_rig:
        if st.session_state.edit_rig in st.session_state.rig_list:
            default_rig_idx = st.session_state.rig_list.index(st.session_state.edit_rig)
        else:
            default_rig_idx = len(rig_options) - 1
        rig_choice = st.selectbox("Team / Rig", options=rig_options, index=default_rig_idx)
    else:
        rig_choice = st.selectbox("Team / Rig", options=rig_options)

    if rig_choice == "✏️ Custom...":
        default_val = st.session_state.edit_rig if st.session_state.edit_mode else ""
        team_rig = st.text_input(
            "Enter custom team/rig",
            value=default_val,
            placeholder="Type team/rig name...",
            key="custom_rig",
        )
    else:
        team_rig = rig_choice

    # ── Manage rig list ──────────────────────────────────────────────────
    with st.expander("⚙️ Edit Team/Rig List"):
        new_rig = st.text_input("Add new team/rig to list", placeholder="e.g., Rig-C")
        if st.button("➕ Add Rig"):
            if new_rig.strip() and new_rig.strip() not in st.session_state.rig_list:
                st.session_state.rig_list.append(new_rig.strip())
                save_rigs(st.session_state.rig_list)
                st.success(f"'{new_rig.strip()}' added!")
                st.rerun()

        rig_to_remove = st.selectbox(
            "Remove team/rig",
            options=[""] + st.session_state.rig_list,
        )
        if rig_to_remove and st.button("🗑️ Remove Rig"):
            st.session_state.rig_list.remove(rig_to_remove)
            save_rigs(st.session_state.rig_list)
            st.success(f"'{rig_to_remove}' removed!")
            st.rerun()

    # ── Activity dropdown + custom ───────────────────────────────────────────
    act_options = st.session_state.activity_list + ["✏️ Custom..."]

    # Pre-select in edit mode
    if st.session_state.edit_mode and st.session_state.edit_activity:
        if st.session_state.edit_activity in st.session_state.activity_list:
            default_act_idx = st.session_state.activity_list.index(st.session_state.edit_activity)
        else:
            default_act_idx = len(act_options) - 1
        act_choice = st.selectbox("Activity", options=act_options, index=default_act_idx)
    else:
        act_choice = st.selectbox("Activity", options=act_options)

    if act_choice == "✏️ Custom...":
        default_val = st.session_state.edit_activity if st.session_state.edit_mode else ""
        activity = st.text_input(
            "Enter custom activity",
            value=default_val,
            placeholder="Type activity name...",
            key="custom_activity",
        )
    else:
        activity = act_choice

    # ── Manage activity list ─────────────────────────────────────────────────
    with st.expander("⚙️ Edit Activity List"):
        new_act = st.text_input("Add new activity to list", placeholder="e.g., Concrete Pouring")
        if st.button("➕ Add to List"):
            if new_act.strip() and new_act.strip() not in st.session_state.activity_list:
                st.session_state.activity_list.append(new_act.strip())
                save_activities(st.session_state.activity_list)
                st.success(f"'{new_act.strip()}' added!")
                st.rerun()

        act_to_remove = st.selectbox(
            "Remove activity",
            options=[""] + st.session_state.activity_list,
        )
        if act_to_remove and st.button("🗑️ Remove from List"):
            st.session_state.activity_list.remove(act_to_remove)
            save_activities(st.session_state.activity_list)
            st.success(f"'{act_to_remove}' removed!")
            st.rerun()

    # ── Time & Depth state initialisation ─────────────────────────────────────
    if "time_window_start" not in st.session_state:
        st.session_state.time_window_start = 7
    if "time_window_end" not in st.session_state:
        st.session_state.time_window_end = 17
    tw_s = st.session_state.time_window_start
    tw_e = st.session_state.time_window_end

    if "start_time_input" not in st.session_state:
        st.session_state.start_time_input = time(8, 0)
    if "end_time_input" not in st.session_state:
        st.session_state.end_time_input = time(9, 0)
    if "start_depth_input" not in st.session_state:
        st.session_state.start_depth_input = 0.0
    if "end_depth_input" not in st.session_state:
        st.session_state.end_depth_input = 0.0

    # ── Pending copy flags (must be checked BEFORE widget instantiation) ──
    if "copy_time_pending" not in st.session_state:
        st.session_state.copy_time_pending = False
    if "copy_depth_pending" not in st.session_state:
        st.session_state.copy_depth_pending = False

    if st.session_state.copy_time_pending:
        st.session_state.start_time_input = st.session_state.pending_start_time
        st.session_state.copy_time_pending = False

    if st.session_state.copy_depth_pending:
        st.session_state.start_depth_input = st.session_state.pending_start_depth
        st.session_state.copy_depth_pending = False

    # ── TIME row ──────────────────────────────────────────────────────────────
    st.caption(f"⏱️ Time ({tw_s}:00 – {tw_e}:00 window)")

    col_t1, col_t2, col_t3 = st.columns([5, 5, 1])
    with col_t1:
        start_time = st.time_input(
            "Start",
            step=300,
            key="start_time_input",
        )
    with col_t2:
        end_time = st.time_input(
            "End",
            step=300,
            key="end_time_input",
        )
    with col_t3:
        st.write("")
        if st.button("⬆️", help="Copy End → Start", key="copy_time_btn"):
            st.session_state.copy_time_pending = True
            st.session_state.pending_start_time = end_time
            st.rerun()

    # Validate time
    time_valid = True
    err_style = "color:#ff4b4b; font-size:0.75rem; margin:0; padding:0;"
    if start_time.hour < tw_s or start_time.hour > tw_e:
        st.markdown(f"<p style='{err_style}'>⚠️ Start time must be between {tw_s}:00 and {tw_e}:00</p>", unsafe_allow_html=True)
        time_valid = False
    if end_time.hour < tw_s or end_time.hour > tw_e:
        st.markdown(f"<p style='{err_style}'>⚠️ End time must be between {tw_s}:00 and {tw_e}:00</p>", unsafe_allow_html=True)
        time_valid = False
    if end_time <= start_time:
        st.markdown(f"<p style='{err_style}'>⚠️ End time must be after start time</p>", unsafe_allow_html=True)
        time_valid = False

    if time_valid:
        start_time_str = start_time.strftime("%H:%M:00")
        end_time_str = end_time.strftime("%H:%M:00")
    else:
        start_time_str = st.session_state.start_time_input.strftime("%H:%M:00")
        end_time_str = st.session_state.end_time_input.strftime("%H:%M:00")

    # ── DEPTH row ─────────────────────────────────────────────────────────────
    st.caption("📏 Depth (meters)")

    col_d1, col_d2, col_d3 = st.columns([5, 5, 1])
    with col_d1:
        start_d = st.number_input(
            "Start Depth (m)",
            min_value=0.0,
            max_value=200.0,
            step=0.5,
            format="%.1f",
            key="start_depth_input",
        )
    with col_d2:
        end_d = st.number_input(
            "End Depth (m)",
            min_value=0.0,
            max_value=200.0,
            step=0.5,
            format="%.1f",
            key="end_depth_input",
        )
    with col_d3:
        st.write("")
        if st.button("⬆️", help="Copy End → Start", key="copy_depth_btn"):
            st.session_state.copy_depth_pending = True
            st.session_state.pending_start_depth = end_d
            st.rerun()

    # Depth: any order is allowed (drilling up or down)

    # ── Time window config ────────────────────────────────────────────────────
    with st.expander("⚙️ Time Window Settings"):
        tw_col1, tw_col2 = st.columns(2)
        with tw_col1:
            tw_s_new = st.number_input(
                "Window Start Hr",
                min_value=0, max_value=22, value=tw_s,
                key="tw_s",
            )
        with tw_col2:
            tw_e_new = st.number_input(
                "Window End Hr",
                min_value=1, max_value=23, value=tw_e,
                key="tw_e",
            )
        if tw_s_new >= tw_e_new:
            st.warning("Window end must be after start.")
        st.session_state.time_window_start = tw_s_new
        st.session_state.time_window_end = tw_e_new

    # ── Add / Update entry ───────────────────────────────────────────────────
    if st.session_state.edit_mode:
        button_label = "💾 Update Entry"
    else:
        button_label = "➕ Add Entry to Chart"

    if st.button(button_label, use_container_width=True, type="primary"):
        if not activity.strip():
            st.warning("Please enter an activity name.")
        elif not time_valid:
            st.warning("⚠️ Please fix time errors before saving.")
        else:
            entry_data = {
                "Date": activity_date.strftime("%d-%m-%Y"),
                "Project": project.strip() if project else "",
                "JGP/Grout Hole": jgp_hole,
                "Team/Rig": team_rig,
                "Activity": activity.strip(),
                "Start Time": start_time_str,
                "End Time": end_time_str,
                "Start Depth (m)": start_d,
                "End Depth (m)": end_d,
            }

            if st.session_state.edit_mode:
                # UPDATE existing row
                idx = st.session_state.editing_index
                # Snapshot old values for undo
                st.session_state.undo_snapshot = {
                    "type": "edit",
                    "idx": idx,
                    "data": st.session_state.log.loc[idx].to_dict(),
                }
                for col, val in entry_data.items():
                    st.session_state.log.at[idx, col] = val
                save_data(st.session_state.log)

                # Save completed — keep edit_mode active until user unchecks the box
                st.session_state.edit_save_pending = True
                st.success(f"✅ Entry {idx} updated!")
                st.rerun()
            else:
                # INSERT new row
                st.session_state.log = pd.concat(
                    [st.session_state.log, pd.DataFrame([entry_data])],
                    ignore_index=True,
                )
                save_data(st.session_state.log)
                st.success(f"'{activity}' logged!")
                st.rerun()

    # ── Undo Last Action (edit or delete) ─────────────────────────────
    if st.session_state.get("undo_snapshot"):
        snap_type = st.session_state.undo_snapshot["type"]
        if snap_type == "edit":
            undo_label = "↩️ Undo Last Edit"
            undo_help = "Restore the row to its state before the last save"
        else:
            undo_label = "↩️ Undo Last Delete"
            undo_help = "Restore the deleted row"
        if st.button(undo_label, use_container_width=True,
                     help=undo_help):
            snap = st.session_state.undo_snapshot
            idx = snap["idx"]
            data = snap["data"]
            if snap_type == "edit":
                for col, val in data.items():
                    st.session_state.log.at[idx, col] = val
            else:  # delete — re-insert the row at original position
                row_df = pd.DataFrame([data])
                log = st.session_state.log
                if idx >= len(log):
                    log = pd.concat([log, row_df], ignore_index=True)
                else:
                    top = log.iloc[:idx]
                    bottom = log.iloc[idx:]
                    log = pd.concat([top, row_df, bottom], ignore_index=True)
                st.session_state.log = log
            save_data(st.session_state.log)
            st.session_state.undo_snapshot = None
            st.success("✅ Undo complete — row restored!")
            st.rerun()

    st.divider()

    # ── Export ───────────────────────────────────────────────────────────────
    st.header("💾 Export")
    if not st.session_state.log.empty:
        csv = st.session_state.log.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            data=csv,
            file_name=f"time_motion_{datetime.date.today().isoformat()}.csv",
            mime="text/csv",
            width="stretch",
        )

        # ── Google Sheets append export ──────────────────────────────────────
        if st.button("📊 Submit to Google Sheets", width="stretch"):
            try:
                exporter = GoogleSheetsExporter(
                    spreadsheet_id="1lfKgH1KaREKqMYxcwf2AAk4Qz1ldE-P44Oj-_vVgeo0",
                    credentials_dict=st.secrets["gcp_service_account"],
                )
                sheet_url = exporter.append_user_data(
                    st.session_state.username,
                    st.session_state.log,
                )
                row_count = len(st.session_state.log)
                st.success(
                    f"✅ Appended {row_count} rows to Google Sheets"
                )
                st.markdown(f"[📂 Open Sheet]({sheet_url})")
            except Exception as e:
                st.error(f"Export failed: {e}")


# ── Main area ────────────────────────────────────────────────────────────────
df = st.session_state.log

if not df.empty:
    sort_cols = [c for c in ["Date", "JGP/Grout Hole", "Start Time"] if c in df.columns]
    df = df.sort_values(by=sort_cols)
    # Preserve original log index → positional mapping before resetting
    idx_map = df.index.tolist()  # e.g. [3, 0, 2, 1] → original log row for each display position
    df = df.reset_index(drop=True)  # clean 0,1,2... for st.dataframe display

    # ── Filters ──────────────────────────────────────────────────────────────
    # Sort rigs to match sidebar rig_list order; unknowns go last (alphabetical)
    rig_order = {r: i for i, r in enumerate(st.session_state.rig_list)}
    rigs_from_df = df["Team/Rig"].unique().tolist()
    rigs = sorted(
        rigs_from_df,
        key=lambda r: (rig_order.get(r, len(st.session_state.rig_list)), r),
    )
    # After delete, the previously selected rig may no longer exist — reset it
    if "chart_rig_filter" in st.session_state:
        if st.session_state.chart_rig_filter not in rigs:
            if rigs:
                st.session_state.chart_rig_filter = rigs[0]
            else:
                del st.session_state["chart_rig_filter"]
    if "Date" in df.columns:
        chart_dates = sorted(df["Date"].dropna().unique().tolist())
    else:
        chart_dates = []

    # ── Daily navigation ─────────────────────────────────────────────────────
    if "chart_day_index" not in st.session_state:
        st.session_state.chart_day_index = 0

    # Keep index in bounds when data changes
    if chart_dates and st.session_state.chart_day_index >= len(chart_dates):
        st.session_state.chart_day_index = len(chart_dates) - 1
    if not chart_dates:
        st.session_state.chart_day_index = 0

    nav_col1, nav_col2, nav_col3 = st.columns([1, 4, 1])
    with nav_col1:
        if st.button("◀️", help="Previous day", key="prev_day",
                     disabled=st.session_state.chart_day_index <= 0 or st.session_state.edit_mode):
            st.session_state.chart_day_index -= 1
            # Sync sidebar activity date to new chart date (via pending flag)
            new_date_str = chart_dates[st.session_state.chart_day_index]
            st.session_state.sync_date_value = datetime.datetime.strptime(new_date_str, "%d-%m-%Y").date()
            st.session_state.sync_date_pending = True
            st.rerun()
    with nav_col2:
        if chart_dates:
            selected_date = chart_dates[st.session_state.chart_day_index]
            st.markdown(
                f"<h3 style='text-align:center;margin:0;'>📅 {selected_date}</h3>",
                unsafe_allow_html=True,
            )
        else:
            selected_date = None
            st.markdown("<h3 style='text-align:center;margin:0;'>📅 No data</h3>", unsafe_allow_html=True)
        # Filter selectbox — constrained via nested columns
        _, filt_c, _ = st.columns([2.75, 3.0, 2.75])
        with filt_c:
            selected_rig = st.selectbox(
                "Filter by Team/Rig",
                options=rigs,
                key="chart_rig_filter",
                disabled=st.session_state.edit_mode,
            )
            if st.session_state.edit_mode:
                st.caption("🔒 Locked while a row is being edited")
    with nav_col3:
        max_idx = len(chart_dates) - 1 if chart_dates else 0
        if st.button("▶️", help="Next day", key="next_day",
                     disabled=st.session_state.chart_day_index >= max_idx or st.session_state.edit_mode):
            st.session_state.chart_day_index += 1
            # Sync sidebar activity date to new chart date (via pending flag)
            new_date_str = chart_dates[st.session_state.chart_day_index]
            st.session_state.sync_date_value = datetime.datetime.strptime(new_date_str, "%d-%m-%Y").date()
            st.session_state.sync_date_pending = True
            st.rerun()

    label_offset = 0
    label_angle = 60

    chart_df = df.copy()
    if selected_date is not None:
        chart_df = chart_df[chart_df["Date"] == selected_date]
    chart_df = chart_df[chart_df["Team/Rig"] == selected_rig]

    # Derive project name for chart title
    chart_project = ""
    if not chart_df.empty and "Project" in chart_df.columns:
        proj_vals = chart_df["Project"].dropna().unique()
        if len(proj_vals) > 0:
            chart_project = str(proj_vals[0])

    # ── Build chart data with None separators per row segment ───────────────
    # Each log row → one isolated line segment: (t_start, start_depth) ─ (t_end, end_depth)
    # None separator prevents Plotly connecting segments of the same activity across rows
    act_segments = {}  # activity → {"x": [...], "y": [...], "hover": [...]}
    annotations = []
    hole_times = {}  # hole_id → {"t_start": min_datetime, "t_end": max_datetime}

    for _, row in chart_df.iterrows():
        row_date = datetime.date.today()
        if "Date" in row and pd.notna(row["Date"]):
            try:
                row_date = datetime.datetime.strptime(str(row["Date"]), "%d-%m-%Y").date()
            except ValueError:
                pass
        t_start = datetime.datetime.combine(
            row_date,
            datetime.datetime.strptime(row["Start Time"], "%H:%M:%S").time(),
        )
        t_end = datetime.datetime.combine(
            row_date,
            datetime.datetime.strptime(row["End Time"], "%H:%M:%S").time(),
        )
        # Collect per-hole time ranges for alternating vertical bands
        hole_id = str(row.get("JGP/Grout Hole", ""))
        if hole_id:
            if hole_id not in hole_times:
                hole_times[hole_id] = {"t_start": t_start, "t_end": t_end}
            else:
                if t_start < hole_times[hole_id]["t_start"]:
                    hole_times[hole_id]["t_start"] = t_start
                if t_end > hole_times[hole_id]["t_end"]:
                    hole_times[hole_id]["t_end"] = t_end
        activity_label = row["Activity"]

        # Append this row's segment + None break to its activity group
        if activity_label not in act_segments:
            act_segments[activity_label] = {"x": [], "y": [], "hover": []}
        seg = act_segments[activity_label]
        start_str = t_start.strftime("%H:%M:%S")
        end_str = t_end.strftime("%H:%M:%S")
        date_str = t_start.strftime("%d-%m-%Y")
        s_depth = row["Start Depth (m)"]
        e_depth = row["End Depth (m)"]
        seg["x"] += [t_start, t_end, None]
        seg["y"] += [s_depth, e_depth, None]
        seg["hover"] += [
            f"<b>{activity_label}</b><br>Date: {date_str}<br>Time: {start_str}<br>Depth: {s_depth:.1f} m",
            f"<b>{activity_label}</b><br>Date: {date_str}<br>Time: {end_str}<br>Depth: {e_depth:.1f} m",
            None,
        ]

        # Midpoint label placed above the midpoint depth of the line
        t_mid = t_start + (t_end - t_start) / 2
        d_mid = (row["Start Depth (m)"] + row["End Depth (m)"]) / 2
        label_y = d_mid + label_offset

        annotations.append(dict(
            x=t_mid,
            y=label_y,
            text=f"<b>{activity_label}</b>",
            showarrow=False,
            xanchor="center",
            yanchor="bottom",
            font=dict(size=11, color="white"),
            bgcolor="rgba(0,0,0,0)",
            borderpad=2,
            textangle=-60,
        ))

    # ── Build chart ──────────────────────────────────────────────────────────
    if not act_segments:
        st.info("No entries match the current filters.")
    else:
        fig = go.Figure()

        for act, seg in act_segments.items():
            fig.add_trace(go.Scatter(
                x=seg["x"],
                y=seg["y"],
                mode="lines+markers",
                name=act,
                hoverinfo="text",
                hovertext=seg["hover"],
                line=dict(width=3),
                marker=dict(size=8),
            ))

        # ── Alternating vertical bands per Point ID ───────────────────────────
        band_annotations = []
        if hole_times:
            sorted_holes = sorted(hole_times.items(), key=lambda kv: kv[1]["t_start"])
            for i, (hole_id, times) in enumerate(sorted_holes):
                # Alternating fill: even-indexed = light grey, odd-indexed = transparent
                fill_color = "rgba(200,200,200,0.12)" if i % 2 == 0 else "rgba(0,0,0,0)"
                fig.add_vrect(
                    x0=times["t_start"],
                    x1=times["t_end"],
                    fillcolor=fill_color,
                    layer="below",
                    line_width=0,
                )
                # Point ID label at top of band, centred on time midpoint
                t_mid = times["t_start"] + (times["t_end"] - times["t_start"]) / 2
                band_annotations.append(dict(
                    x=t_mid,
                    y=0.97,
                    yref="paper",
                    text=f"<b>{hole_id}</b>",
                    showarrow=False,
                    xanchor="center",
                    yanchor="top",
                    font=dict(size=11, color="rgba(255,255,255,0.8)"),
                    bgcolor="rgba(0,0,0,0)",
                    borderpad=2,
                ))

        fig.update_layout(annotations=annotations + band_annotations)
        fig.update_yaxes(autorange="reversed", title="Depth Below Ground (m)")
        fig.update_xaxes(
            dtick=3600000,
            tickformat="%H:%M",
            title="Time of Day",
            autorange=True,
            showgrid=True,
            gridwidth=2,
            gridcolor="rgba(255,255,255,0.3)",
            minor=dict(
                dtick=900000,
                showgrid=True,
                gridcolor="rgba(255,255,255,0.15)",
                griddash="dot",
            ),
        )

        fig.update_layout(
            legend_title_text="Activity",
            hovermode="closest",
            height=550,
            margin=dict(t=30, b=40),
        )

        title_text = "📊 Time & Motion Chart"
        if chart_project:
            title_text += f" — {chart_project}"
        st.markdown(
            f"<h3 style='text-align: center;'>{title_text}</h3>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": True})

    # ── Build filtered table_df matching chart date + rig filters ──────────
    table_df = df.copy()
    if selected_date is not None:
        table_df = table_df[table_df["Date"] == selected_date]
    if selected_rig is not None:
        table_df = table_df[table_df["Team/Rig"] == selected_rig]
    # table_idx_map[i] = df index for table_df display row i
    table_idx_map = table_df.index.tolist()
    table_df = table_df.reset_index(drop=True)

    # ── Restore checkbox selection after save (must run BEFORE dataframe widget) ─
    if st.session_state.get("restore_selection_pending", False):
        # editing_index holds the original log index; find its
        # positional row in the filtered table_df via two-level lookup
        target_idx = st.session_state.editing_index
        try:
            df_pos = idx_map.index(target_idx)
            table_pos = table_idx_map.index(df_pos)
            st.session_state.row_selector = {"selection": {"rows": [table_pos]}}
        except ValueError:
            pass  # row deleted or not visible in current filter
        st.session_state.restore_selection_pending = False
        st.rerun()

    # ── Clear selection after delete (must run BEFORE dataframe widget) ─
    if st.session_state.get("clear_selection_pending", False):
        if "row_selector" in st.session_state:
            del st.session_state["row_selector"]
        st.session_state.clear_selection_pending = False

    # ── Activity Log table with row selection ─────────────────────────────────
    st.subheader("📋 Activity Log")
    st.caption("💡 Click any row to load it into the sidebar for editing")

    st.dataframe(
        table_df,
        selection_mode="single-row",
        on_select="rerun",
        key="row_selector",
        hide_index=False,
        use_container_width=True,
        column_config={
            "Date": st.column_config.TextColumn("Date"),
            "Project": st.column_config.TextColumn("Project"),
            "JGP/Grout Hole": st.column_config.TextColumn("JGP/Grout Hole"),
            "Team/Rig": st.column_config.TextColumn("Team/Rig"),
            "Activity": st.column_config.TextColumn("Activity"),
            "Start Time": st.column_config.TextColumn("Start Time"),
            "End Time": st.column_config.TextColumn("End Time"),
            "Start Depth (m)": st.column_config.NumberColumn("Start Depth (m)", format="%.1f"),
            "End Depth (m)": st.column_config.NumberColumn("End Depth (m)", format="%.1f"),
        },
    )

    # Handle row selection
    if "row_selector" in st.session_state:
        selection = st.session_state.row_selector.get("selection", {})
        selected_rows = selection.get("rows", [])

        if selected_rows:
            selected_idx = selected_rows[0]

            # Guard against stale selection index when table_df shrank
            # (e.g. user navigated to a date with fewer rows mid-edit)
            if selected_idx >= len(table_df):
                if "row_selector" in st.session_state:
                    del st.session_state["row_selector"]
                if st.session_state.edit_mode:
                    st.session_state.edit_mode = False
                    st.session_state.editing_index = None
                st.rerun()

            if not st.session_state.edit_mode:
                # Enter edit mode for the first time
                st.session_state.undo_snapshot = None  # clear stale undo
                st.session_state.row_load_pending = True
                st.session_state.pending_row_data = table_df.iloc[selected_idx].to_dict()
                df_pos = table_idx_map[selected_idx]
                st.session_state.pending_row_index = int(idx_map[df_pos])
                st.rerun()
            elif st.session_state.editing_index != int(idx_map[table_idx_map[selected_idx]]):
                # User clicked a different row while editing — switch to new row
                st.session_state.undo_snapshot = None  # clear stale undo
                st.session_state.row_load_pending = True
                st.session_state.pending_row_data = table_df.iloc[selected_idx].to_dict()
                df_pos = table_idx_map[selected_idx]
                st.session_state.pending_row_index = int(idx_map[df_pos])
                st.rerun()

        elif not selected_rows and st.session_state.edit_mode:
            if st.session_state.get("edit_save_pending", False):
                # Post-save render — schedule restore via pending flag (before widget)
                st.session_state.edit_save_pending = False
                st.session_state.restore_selection_pending = True
                st.rerun()
            else:
                # User manually unchecked the checkbox — exit edit mode
                st.session_state.edit_mode = False
                st.session_state.editing_index = None
                st.rerun()

    # ── Bottom toolbar: Delete Row + Admin Only (below the table) ──────────
    delete_visible = (
        st.session_state.get("edit_mode", False)
        or bool(st.session_state.get("row_selector", {}).get("selection", {}).get("rows", []))
    )
    is_admin = st.session_state.get("username", "") == "admin"

    if "show_admin_panel" not in st.session_state:
        st.session_state.show_admin_panel = False
    if "admin_select_all" not in st.session_state:
        st.session_state.admin_select_all = False

    # ── Shared row: Delete Row (left) ····· Admin (aligned to Project col) ─
    if delete_visible or is_admin:
        col_del, col_admin = st.columns([5, 1])

        if delete_visible:
            with col_del:
                if st.button("🗑️ Delete Row", key="toolbar_delete",
                             help="Delete the currently selected row"):
                    if st.session_state.get("edit_mode", False):
                        idx = idx_map.index(st.session_state.editing_index)
                    else:
                        sel_row = st.session_state.row_selector["selection"]["rows"][0]
                        idx = int(table_idx_map[sel_row])
                    # Snapshot the deleted row for undo
                    st.session_state.undo_snapshot = {
                        "type": "delete",
                        "idx": idx,
                        "data": df.iloc[idx].to_dict(),
                    }
                    st.session_state.log = df.drop(index=idx).reset_index(drop=True)
                    save_data(st.session_state.log)
                    st.session_state.edit_mode = False
                    st.session_state.editing_index = None
                    st.session_state.clear_selection_pending = True
                    st.success("✅ Deleted entry")
                    st.rerun()

        if is_admin:
            with col_admin:
                if st.button("🛡️ Admin Only", key="admin_panel",
                             help="Show admin controls"):
                    st.session_state.show_admin_panel = not st.session_state.show_admin_panel
                    st.session_state.admin_select_all = False
                    st.rerun()

    # ── Admin panel stacks below the button row, aligned to Project col ──
    if is_admin and st.session_state.show_admin_panel:
        _, admin_panel_col = st.columns([5, 1])
        with admin_panel_col:
            st.session_state.admin_select_all = st.checkbox(
                "Select All Activity Log",
                value=st.session_state.admin_select_all,
                key="admin_select_all_cb",
            )
            if st.session_state.admin_select_all:
                if st.button("🗑️ Delete All Logs", type="primary",
                             key="admin_delete_all",
                             help="⚠️ This permanently removes every entry"):
                    st.session_state.log = st.session_state.log.iloc[0:0]
                    save_data(st.session_state.log)
                    st.session_state.show_admin_panel = False
                    st.session_state.admin_select_all = False
                    st.success("✅ All log entries deleted")
                    st.rerun()

else:
    st.info(
        "No activity entries yet.\n\n"
        "Use the **sidebar** to log each activity:\n"
        "1. Enter the **JGP/Grout Hole** and **Team/Rig**\n"
        "2. Pick an **Activity** from the dropdown (or choose ✏️ Custom... to type one)\n"
        "3. Set **Start** and **End** hour/minute boxes (within 7 AM – 12 PM)\n"
        "4. Set **Start Depth** and **End Depth** below ground\n"
        "5. Click **➕ Add Entry to Chart**\n\n"
        "Customize the activity dropdown via the **⚙️ Edit Activity List** expander."
    )
