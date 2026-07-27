import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import json
from pathlib import Path

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
    """Log successful authentication with username and timestamp."""
    logs = []
    if ACCESS_LOG_FILE.exists():
        with open(ACCESS_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)

    log_entry = {
        "username": username,
        "timestamp": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        ).isoformat(),
        "session_id": st.runtime.scriptrunner.get_script_run_ctx().session_id,
    }
    logs.append(log_entry)

    DATA_DIR.mkdir(exist_ok=True)
    with open(ACCESS_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)


def check_authentication() -> bool:
    """Show login page if not authenticated. Returns True if authenticated."""
    if st.session_state.get("authenticated", False):
        return True

    # ── Login page UI ─────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='text-align: center;'>🔐 Time & Motion Study</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #888;'>Please enter the password to access the application.</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input(
            "Username",
            placeholder="Enter your username...",
            key="login_username",
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password...",
            key="login_password",
        )
        if st.button("🔓 Login", width="stretch", type="primary"):
            if not username.strip():
                st.error("❌ Please enter your username.")
            elif password == st.secrets["passwords"]["app_password"]:
                st.session_state.authenticated = True
                st.session_state.username = username.strip()
                st.session_state.login_timestamp = datetime.datetime.now(
                    datetime.timezone(datetime.timedelta(hours=8))
                ).isoformat()
                log_access(username.strip())
                st.rerun()
            else:
                st.error("❌ Incorrect password. Please try again.")

    # ── Show last 5 logins on login page ────────────────────────────────────
    if ACCESS_LOG_FILE.exists():
        with open(ACCESS_LOG_FILE, "r", encoding="utf-8") as f:
            all_logs = json.load(f)

        if all_logs:
            st.divider()
            st.markdown(
                "<p style='text-align: center; font-size: 0.9em; color: #888;'>Recent Activity</p>",
                unsafe_allow_html=True,
            )

            # Take last 5 entries, reverse for newest-first
            recent = all_logs[-5:][::-1]
            rows = []
            for entry in recent:
                ts_raw = entry.get("timestamp", "")
                try:
                    ts = datetime.datetime.fromisoformat(ts_raw)
                    date_str = ts.strftime("%d-%m-%Y")
                    time_str = ts.strftime("%H:%M:%S")
                except (ValueError, TypeError):
                    date_str = "-"
                    time_str = "-"

                rows.append({
                    "Username": entry.get("username", "-"),
                    "Date": date_str,
                    "Time": time_str,
                })

            df_logins = pd.DataFrame(rows)
            # Hide the index by converting to dict records and using columns
            col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
            with col_t2:
                st.dataframe(
                    df_logins,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Username": st.column_config.TextColumn("Username", width="small"),
                        "Date": st.column_config.TextColumn("Date", width="small"),
                        "Time": st.column_config.TextColumn("Time", width="small"),
                    },
                )

    return False


# ── Authentication Gate ───────────────────────────────────────────────────────
if not check_authentication():
    st.stop()

# ── Logout button (top-right) ─────────────────────────────────────────────────
col_main, col_logout = st.columns([6, 1])
with col_main:
    st.title("⏱️ Time & Motion Study Tracker")
with col_logout:
    st.write("")
    if st.button("🚪 Logout", key="logout_btn"):
        st.session_state.authenticated = False
        st.session_state.pop("login_timestamp", None)
        st.rerun()


COLUMNS = [
    "Date", "Project", "JGP/Grout Hole", "Team/Rig", "Activity",
    "Start Time", "End Time",
    "Start Depth (m)", "End Depth (m)",
]


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


# ── Initialize session state ─────────────────────────────────────────────────
if "log" not in st.session_state:
    st.session_state.log = load_data()
if "activity_list" not in st.session_state:
    st.session_state.activity_list = load_activities()
if "rig_list" not in st.session_state:
    st.session_state.rig_list = load_rigs()
if "project_list" not in st.session_state:
    st.session_state.project_list = load_projects()

# ── Sidebar: Data Entry ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("📝 Log New Activity")

    # ── Project dropdown + custom ──────────────────────────────────────────
    proj_options = st.session_state.project_list + ["✏️ Custom..."]
    proj_choice = st.selectbox("Project Title", options=proj_options)

    if proj_choice == "✏️ Custom...":
        project = st.text_input(
            "Enter custom project",
            value="",
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
    ref_col, hole_col = st.columns([3, 2])
    with ref_col:
        hole_ref = st.text_input("Ref. No.", value="01", placeholder="e.g., 01, 02A")
    with hole_col:
        hole_type = st.radio("Hole Type", options=["JGP", "Grout Hole"], horizontal=True, label_visibility="collapsed")
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
    rig_choice = st.selectbox("Team / Rig", options=rig_options)

    if rig_choice == "✏️ Custom...":
        team_rig = st.text_input(
            "Enter custom team/rig",
            value="",
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
    act_choice = st.selectbox("Activity", options=act_options)

    if act_choice == "✏️ Custom...":
        activity = st.text_input(
            "Enter custom activity",
            value="",
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

    # Time window defaults (read early so hour dropdowns can use them)
    if "time_window_start" not in st.session_state:
        st.session_state.time_window_start = 7
    if "time_window_end" not in st.session_state:
        st.session_state.time_window_end = 12
    tw_s = st.session_state.time_window_start
    tw_e = st.session_state.time_window_end

    # ── Hour + Minute boxes ──────────────────────────────────────────────────
    st.caption(f"Time ({tw_s}:00 – {tw_e}:00 window)")
    hours = list(range(tw_s, tw_e + 1))
    minutes = [0, 15, 30, 45]

    col_h1, col_m1 = st.columns(2)
    with col_h1:
        sh = st.selectbox("Start Hr", hours, index=1, key="sh")  # default 8
    with col_m1:
        sm = st.selectbox("Start Min", minutes, index=0, key="sm")

    col_h2, col_m2 = st.columns(2)
    with col_h2:
        eh = st.selectbox("End Hr", hours, index=2, key="eh")  # default 9
    with col_m2:
        em = st.selectbox("End Min", minutes, index=0, key="em")

    start_time_str = f"{sh:02d}:{sm:02d}:00"
    end_time_str = f"{eh:02d}:{em:02d}:00"

    # ── Time window config (placed below hour boxes) ─────────────────────────
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

    # ── Depth ────────────────────────────────────────────────────────────────
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_d = st.number_input("Start Depth (m)", min_value=0.0, step=0.5, value=0.0, key="sd")
    with col_d2:
        end_d = st.number_input("End Depth (m)", min_value=0.0, step=0.5, value=0.0, key="ed")

    # ── Add entry ────────────────────────────────────────────────────────────
    if st.button("➕ Add Entry to Chart", width="stretch", type="primary"):
        if not activity.strip():
            st.warning("Please enter an activity name.")
        elif sh > eh or (sh == eh and sm >= em):
            st.warning("End time must be after start time.")
        else:
            new_entry = {
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
            st.session_state.log = pd.concat(
                [st.session_state.log, pd.DataFrame([new_entry])],
                ignore_index=True,
            )
            save_data(st.session_state.log)
            st.success(f"'{activity}' logged!")
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


# ── Main area ────────────────────────────────────────────────────────────────
df = st.session_state.log

if not df.empty:
    sort_cols = [c for c in ["Date", "JGP/Grout Hole", "Start Time"] if c in df.columns]
    df = df.sort_values(by=sort_cols).reset_index(drop=True)

    # ── Filters ──────────────────────────────────────────────────────────────
    holes = df["JGP/Grout Hole"].unique().tolist()
    rigs = df["Team/Rig"].unique().tolist()
    if "Date" in df.columns:
        dates = sorted(df["Date"].dropna().unique().tolist())
    else:
        dates = []

    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        if dates:
            selected_date = st.selectbox("Filter by Date", ["All"] + dates)
        else:
            selected_date = "All"
    with cf2:
        selected_hole = st.selectbox("Filter by JGP/Grout Hole", ["All"] + holes)
    with cf3:
        selected_rig = st.selectbox("Filter by Team/Rig", ["All"] + rigs)

    label_offset = 0
    label_angle = 60

    chart_df = df.copy()
    if selected_date != "All":
        chart_df = chart_df[chart_df["Date"] == selected_date]
    if selected_hole != "All":
        chart_df = chart_df[chart_df["JGP/Grout Hole"] == selected_hole]
    if selected_rig != "All":
        chart_df = chart_df[chart_df["Team/Rig"] == selected_rig]

    # ── Build chart data ─────────────────────────────────────────────────────
    chart_data = []
    annotations = []

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
        activity_label = row["Activity"]

        chart_data.append({
            "Time": t_start,
            "Depth (m)": row["Start Depth (m)"],
            "Activity": activity_label,
        })
        chart_data.append({
            "Time": t_end,
            "Depth (m)": row["End Depth (m)"],
            "Activity": activity_label,
        })

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
    plot_df = pd.DataFrame(chart_data)
    fig = go.Figure()

    for act in plot_df["Activity"].unique():
        act_df = plot_df[plot_df["Activity"] == act]
        fig.add_trace(go.Scatter(
            x=act_df["Time"],
            y=act_df["Depth (m)"],
            mode="lines+markers",
            name=act,
            hoverinfo="text",
            hovertext=[
                f"<b>{act}</b><br>Date: {t.strftime('%d-%m-%Y')}<br>Time: {t.strftime('%H:%M:%S')}<br>Depth: {d:.1f} m"
                for t, d in zip(act_df["Time"], act_df["Depth (m)"])
            ],
            line=dict(width=3),
            marker=dict(size=8),
        ))

    fig.update_layout(annotations=annotations)

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

    title_parts = []
    if selected_date != "All":
        title_parts.append(str(selected_date))
    if selected_hole != "All":
        title_parts.append(selected_hole)
    if selected_rig != "All":
        title_parts.append(selected_rig)
    title = "Time & Motion Chart — " + (" / ".join(title_parts) if title_parts else "All")

    fig.update_layout(
        title=title,
        legend_title_text="Activity",
        hovermode="closest",
        height=550,
        margin=dict(t=60, b=40),
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": True})

    # ── Editable data table ──────────────────────────────────────────────────
    st.subheader("📋 Activity Log")

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Date": st.column_config.TextColumn("Date", required=False),
            "Project": st.column_config.TextColumn("Project", required=False),
            "JGP/Grout Hole": st.column_config.TextColumn("JGP/Grout Hole", required=True),
            "Team/Rig": st.column_config.TextColumn("Team/Rig", required=True),
            "Activity": st.column_config.TextColumn("Activity", required=True),
            "Start Time": st.column_config.TextColumn("Start Time", required=True),
            "End Time": st.column_config.TextColumn("End Time", required=True),
            "Start Depth (m)": st.column_config.NumberColumn("Start Depth (m)", format="%.1f"),
            "End Depth (m)": st.column_config.NumberColumn("End Depth (m)", format="%.1f"),
        },
        key="data_editor",
    )

    if not edited_df.equals(df):
        st.session_state.log = edited_df
        save_data(st.session_state.log)
        st.rerun()

    # ── Delete rows ──────────────────────────────────────────────────────────
    st.subheader("🗑️ Delete Rows")
    rows_to_delete = st.multiselect(
        "Select rows to delete",
        options=df.index.tolist(),
        format_func=lambda i: (
            f"[{i}] {df.loc[i, 'Date'] if 'Date' in df.columns else ''} | {df.loc[i, 'JGP/Grout Hole']} | {df.loc[i, 'Team/Rig']} | "
            f"{df.loc[i, 'Activity']} ({df.loc[i, 'Start Time']} → {df.loc[i, 'End Time']})"
        ),
    )
    if rows_to_delete and st.button("Delete Selected Rows", type="secondary"):
        st.session_state.log = df.drop(index=rows_to_delete).reset_index(drop=True)
        save_data(st.session_state.log)
        st.success(f"Deleted {len(rows_to_delete)} row(s).")
        st.rerun()

    with st.expander("⚠️ Danger Zone"):
        if st.button("🗑️ Clear All Data", type="primary"):
            st.session_state.log = pd.DataFrame(columns=COLUMNS)
            save_data(st.session_state.log)
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
