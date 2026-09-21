"""
Supabase REST Client for AOV Studio Cloud Persistence
Provides persistent cloud storage across all deploys, commits, and server restarts.
"""
import os
import json
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://rrugdxdhfdtoypmcabej.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_OKPExiUrEIhNd58pPhQ_og_VLgraK0O")

def _get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def is_supabase_enabled():
    return bool(SUPABASE_URL and SUPABASE_KEY and "supabase.co" in SUPABASE_URL)

def supabase_get(table: str, query_params: str = ""):
    """GET query from Supabase table"""
    if not is_supabase_enabled():
        return None
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if query_params:
        url += f"?{query_params}"
    req = urllib.request.Request(url, headers=_get_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else []
    except Exception as e:
        print(f"[Supabase GET Error] {table}: {e}", flush=True)
        return None

def supabase_insert(table: str, payload: dict or list):
    """INSERT row(s) into Supabase table"""
    if not is_supabase_enabled():
        return None
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=_get_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else []
    except Exception as e:
        print(f"[Supabase INSERT Error] {table}: {e}", flush=True)
        return None

def supabase_update(table: str, match_params: str, payload: dict):
    """UPDATE row(s) in Supabase table matching query"""
    if not is_supabase_enabled():
        return None
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_params}"
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=_get_headers(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else []
    except Exception as e:
        print(f"[Supabase UPDATE Error] {table}: {e}", flush=True)
        return None

def supabase_delete(table: str, match_params: str):
    """DELETE row(s) in Supabase table matching query"""
    if not is_supabase_enabled():
        return None
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_params}"
    req = urllib.request.Request(url, headers=_get_headers(), method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            return True
    except Exception as e:
        print(f"[Supabase DELETE Error] {table}: {e}", flush=True)
        return False
