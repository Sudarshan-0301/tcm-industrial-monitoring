import streamlit as st
from supabase import create_client

def get_client():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None

def db_ready(client): return client is not None

def get_tools(client):
    if client is None: return []
    return client.table("tools").select("*").eq("status","active").order("created_at", desc=True).execute().data

def create_tool(client, tool_id, tool_type, diameter, installed, condition):
    existing = client.table("tools").select("id").eq("tool_id", tool_id).execute().data
    if existing: raise ValueError("That Tool ID already exists.")
    client.table("tools").insert({"tool_id":tool_id,"tool_type":tool_type,"diameter_mm":diameter,
        "installed_on":installed,"initial_condition":condition,"status":"active"}).execute()

def get_active_session(client):
    rows = client.table("machining_sessions").select("*,tools(tool_id)").in_("status",["running","paused"]).limit(1).execute().data
    if not rows: return None
    row=rows[0]
    row["tool_label"]=(row.get("tools") or {}).get("tool_id")
    return row

def _ensure_no_active(client):
    if get_active_session(client): raise ValueError("Another tool session is active. Stop it before starting a new one.")

def start_session(client, tool_id):
    _ensure_no_active(client)
    client.table("machining_sessions").insert({"tool_id":tool_id,"status":"running"}).execute()

def pause_session(client, session_id):
    client.rpc("pause_machining_session", {"p_session_id":session_id}).execute()

def resume_session(client, session_id):
    client.rpc("resume_machining_session", {"p_session_id":session_id}).execute()

def stop_session(client, session_id):
    # Exact elapsed-time accounting is implemented in SQL RPC to avoid browser clock dependence.
    client.rpc("stop_machining_session", {"session_id":session_id}).execute()

def get_sessions(client, tool_id):
    return client.table("machining_sessions").select("*").eq("tool_id",tool_id).order("created_at",desc=True).execute().data

def replace_tool(client, tool_id):
    client.rpc("replace_tool_lifecycle", {"p_tool_id":tool_id}).execute()

def save_recording(client, filename, file_hash, rows, columns):
    client.table("sensor_recordings").insert({"filename":filename,"sha256":file_hash,"row_count":rows,"columns":columns}).execute()
