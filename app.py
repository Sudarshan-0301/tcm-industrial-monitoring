import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import hashlib
import joblib
from datetime import datetime, timezone
from database import get_client, db_ready, save_recording, get_tools, create_tool, get_active_session, start_session, pause_session, resume_session, stop_session, replace_tool, get_sessions

st.set_page_config(page_title="TCM | Industrial Monitoring", page_icon="⚙️", layout="wide")
st.markdown("""
<style>
.stApp {background:#081426;color:#e8eef8}
[data-testid="stSidebar"] {background:#0d1c32}
.block-container {padding-top:1.5rem;max-width:1500px}
div[data-testid="stMetric"] {background:#11243d;border:1px solid #203c5d;padding:16px;border-radius:12px}
h1,h2,h3 {color:#f4f7fc}
</style>
""", unsafe_allow_html=True)

SENSORS = ["spindle_vib","platform_vib","spindle_temp","platform_temp","spindle_force",
           "acoustic_level","x_current","y_current","z_current","spindle_current"]
MODEL_PATH = Path("TCM_Model.joblib")

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def load_data(upload):
    raw = upload.getvalue()
    name = upload.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(upload)
    elif name.endswith(".xlsx"):
        df = pd.read_excel(upload, engine="openpyxl")
    elif name.endswith(".xls"):
        df = pd.read_excel(upload)
    else:
        raise ValueError("Upload a CSV, XLSX or XLS file.")
    df.columns = [str(c).strip() for c in df.columns]
    return df, raw

def metric_card(label, value, help_text=None):
    st.metric(label, value, help=help_text)

def sidebar():
    st.sidebar.title("⚙ TCM MONITOR")
    st.sidebar.caption("MEcon MD-3030-EN · Uploaded-data analysis")
    return st.sidebar.radio("Navigation", ["Main Dashboard","Multi-Sensor Analysis","AI Tool Classification",
                                           "Tool Life Management","Dataset Management","Model Management"])

page = sidebar()
st.title("Retrofit Multi-Sensor Tool Condition Monitoring")
st.caption("Offline analysis of uploaded CNC recordings · No live machine connection is assumed")

client = get_client()
ready = client is not None

if page == "Main Dashboard":
    st.subheader("Machine overview")
    c1,c2,c3,c4 = st.columns(4)
    with c1: metric_card("Machine","MEcon MD-3030-EN")
    with c2: metric_card("Analysis mode","Uploaded files")
    with c3: metric_card("Database","Connected" if ready else "Not configured")
    with c4: metric_card("AI model","Available" if MODEL_PATH.exists() else "Not installed")
    st.info("Upload a sensor recording from Multi-Sensor Analysis to begin. Values and graphs are only shown when source data is provided.")
    st.markdown("### System modules")
    st.write("Sensor analysis · New/Old-Worn classification · Manual tool-life tracking · Verified dataset management")

elif page == "Multi-Sensor Analysis":
    st.subheader("Upload and inspect sensor recording")
    upload = st.file_uploader("Upload CNC recording", type=["csv","xlsx","xls"])
    if upload:
        try:
            df, raw = load_data(upload)
            present = [c for c in SENSORS if c in df.columns]
            missing = [c for c in SENSORS if c not in df.columns]
            st.success(f"Loaded {len(df):,} rows and {len(df.columns)} columns.")
            st.write("Detected sensor channels:", ", ".join(present) if present else "None")
            if missing: st.warning("Missing channels: " + ", ".join(missing))
            xcol = "time" if "time" in df.columns else None
            x = df[xcol] if xcol else np.arange(len(df))
            if present:
                selected = st.multiselect("Channels to display", present, default=present)
                for channel in selected:
                    plot_df = pd.DataFrame({"Sample/time": x, "Value": pd.to_numeric(df[channel], errors="coerce")})
                    plot_df = plot_df.dropna()
                    fig = px.line(plot_df, x="Sample/time", y="Value", title=channel)
                    fig.update_layout(template="plotly_dark", paper_bgcolor="#081426", plot_bgcolor="#0d1c32")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("No recognized sensor columns were found. Check the uploaded column names.")
            st.markdown("#### Recording metadata")
            st.write({"Filename": upload.name, "SHA-256": sha256(raw), "Rows": len(df), "Columns": list(df.columns)})
            if ready and st.button("Save recording metadata to database"):
                save_recording(client, upload.name, sha256(raw), len(df), list(df.columns))
                st.success("Recording metadata saved.")
            elif not ready:
                st.caption("Configure Supabase to persist recording metadata.")
            st.dataframe(df.head(20), use_container_width=True)
            st.session_state["current_df"] = df
            st.session_state["current_filename"] = upload.name
            st.session_state["current_hash"] = sha256(raw)
        except Exception as e:
            st.error(f"Could not read this file: {e}")

elif page == "AI Tool Classification":
    st.subheader("New vs Old/Worn tool classification")
    if not MODEL_PATH.exists():
        st.warning("TCM_Model.joblib is not present. Upload the verified model artifact into the project root to enable classification.")
    else:
        up = st.file_uploader("Upload sensor recording for classification", type=["csv","xlsx","xls"], key="classify")
        if up:
            try:
                df,_ = load_data(up)
                artifact = joblib.load(MODEL_PATH)
                if not isinstance(artifact, dict) or not all(k in artifact for k in ("pipeline","feature_columns","window_size","sensor_columns")):
                    st.error("Unsupported model artifact. Expected pipeline, feature_columns, window_size and sensor_columns.")
                else:
                    pipeline = artifact["pipeline"]
                    feature_columns = artifact["feature_columns"]
                    window_size = int(artifact["window_size"])
                    sensor_columns = artifact["sensor_columns"]
                    missing = [c for c in sensor_columns if c not in df.columns]
                    st.write({"Window size": window_size, "Sensor channels": len(sensor_columns),
                              "Features per window": len(feature_columns), "Model classes": list(pipeline.classes_)})
                    if missing:
                        st.error("Required model columns are missing: " + ", ".join(missing))
                    else:
                        numeric = df[sensor_columns].apply(pd.to_numeric, errors="coerce").replace([np.inf,-np.inf], np.nan)
                        numeric = numeric.dropna()
                        n_windows = len(numeric) // window_size
                        if n_windows < 1:
                            st.error(f"At least {window_size} complete valid rows are required. Found {len(numeric)}.")
                        else:
                            rows = []
                            stats = [("mean",np.mean),("std",lambda a: np.std(a,ddof=1) if len(a)>1 else 0.0),
                                     ("rms",lambda a: np.sqrt(np.mean(np.square(a)))),("ptp",np.ptp),
                                     ("median",np.median),("range90",lambda a: np.percentile(a,90)-np.percentile(a,10))]
                            for start in range(0, n_windows*window_size, window_size):
                                chunk = numeric.iloc[start:start+window_size]
                                values = {}
                                for sensor in sensor_columns:
                                    arr = chunk[sensor].to_numpy(dtype=float)
                                    for suffix, fn in stats:
                                        values[f"{sensor}_{suffix}"] = float(fn(arr))
                                rows.append(values)
                            features = pd.DataFrame(rows).reindex(columns=feature_columns)
                            predictions = pipeline.predict(features)
                            labels = {0:"New", 1:"Old/Worn"}
                            names = [labels.get(int(v), f"Class {v}") for v in predictions]
                            counts = pd.Series(names).value_counts()
                            majority = counts.index[0]
                            agreement = float(counts.iloc[0] / len(names) * 100)
                            st.success(f"Overall classification: {majority}")
                            a,b,c = st.columns(3)
                            a.metric("Windows analysed", len(names))
                            b.metric("Majority agreement", f"{agreement:.1f}%")
                            c.metric("Valid rows used", f"{n_windows*window_size:,}")
                            st.caption("Agreement is the share of windows voting for the majority class. It is not model probability, confidence calibration, or accuracy.")
                            st.dataframe(pd.DataFrame({"Window":range(1,len(names)+1),"Prediction":names}),use_container_width=True)
                            st.bar_chart(counts)
                            st.warning("Predictions are not physical inspection labels. Confirm tool condition physically before admitting this recording to the verified training dataset.")
            except Exception as e:
                st.error(f"Model or recording could not be loaded: {e}")

elif page == "Tool Life Management":
    st.subheader("Manual tool-life tracking")
    if not ready:
        st.warning("Timer persistence requires Supabase configuration. Configure the environment variables in .streamlit/secrets.toml.")
    tools = get_tools(client) if ready else []
    with st.expander("Register a tool", expanded=not bool(tools)):
        with st.form("register_tool"):
            tid = st.text_input("Unique Tool ID")
            ttype = st.text_input("Tool type / description")
            dia = st.number_input("Diameter (mm)", min_value=0.0, step=0.1)
            installed = st.date_input("Installation date")
            condition = st.selectbox("Initial physical condition", ["New","Previously used"])
            submitted = st.form_submit_button("Register tool")
            if submitted:
                if not tid.strip(): st.error("Tool ID is required.")
                elif not ready: st.error("Database is not configured.")
                else:
                    try:
                        create_tool(client, tid.strip(), ttype, dia, str(installed), condition)
                        st.success("Tool registered.")
                        st.rerun()
                    except Exception as e: st.error(str(e))
    if ready:
        tools = get_tools(client)
        if tools:
            labels = {f'{t["tool_id"]} — {t.get("tool_type","")}' : t for t in tools}
            choice = st.selectbox("Select tool", list(labels))
            tool = labels[choice]
            active = get_active_session(client)
            st.markdown(f"### {tool['tool_id']}")
            st.caption(f"{tool.get('tool_type','')} · Ø {tool.get('diameter_mm','Not specified')} mm")
            sessions = get_sessions(client, tool["id"])
            elapsed = sum(max(0, int(s.get("elapsed_seconds") or 0)) for s in sessions)
            if active and active.get("tool_id") == tool["id"] and active.get("status") in ("running","paused"):
                elapsed += max(0, int((datetime.now(timezone.utc)-datetime.fromisoformat(active["started_at"].replace("Z","+00:00"))).total_seconds())) if active["status"]=="running" else 0
            st.metric("Recorded cutting time", f"{elapsed//3600:02d}:{(elapsed%3600)//60:02d}:{elapsed%60:02d}")
            if active:
                st.info(f"Active session: {active['status']} · Tool: {active.get('tool_id')}")
            col1,col2,col3 = st.columns(3)
            with col1:
                if st.button("START", disabled=bool(active)):
                    start_session(client, tool["id"]); st.rerun()
            with col2:
                if st.button("PAUSE", disabled=not (active and active.get("status")=="running")):
                    pause_session(client, active["id"]); st.rerun()
            with col3:
                if st.button("RESUME", disabled=not (active and active.get("status")=="paused")):
                    resume_session(client, active["id"]); st.rerun()
            if st.button("STOP AND SAVE SESSION", disabled=not bool(active)):
                stop_session(client, active["id"]); st.success("Session saved."); st.rerun()
            st.markdown("#### Tool history")
            st.dataframe(pd.DataFrame(sessions), use_container_width=True)
            st.markdown("#### Tool replacement")
            if st.button("Replace this tool"):
                if active and active.get("tool_id")==tool["id"]:
                    st.error("Stop the active session before replacing the tool.")
                else:
                    replace_tool(client, tool["id"]); st.success("Tool lifecycle closed."); st.rerun()
        else:
            st.info("Register a tool to begin tracking.")
    else:
        st.caption("Timer controls become active after the database is connected.")

elif page == "Dataset Management":
    st.subheader("Verified dataset management")
    st.info("Only physically inspected New or Old/Worn labels should be admitted to training. AI predictions must never become training labels automatically.")
    st.write("Exact-file SHA-256 and normalized-data duplicate checks are part of the database workflow. Dataset admission and model retraining controls will be enabled after schema setup.")

elif page == "Model Management":
    st.subheader("Model management")
    if MODEL_PATH.exists():
        st.success("Model artifact file found in project root.")
        st.write(f"File size: {MODEL_PATH.stat().st_size:,} bytes")
    else:
        st.warning("Model artifact not installed.")
    st.info("A candidate model should replace the active model only after grouped, leakage-safe evaluation against verified experiments.")
