"""
Turso Database Client for AnimeVist Telegram Bot (libSQL over HTTP).
Standard library Python (0 dependencies).
Provides high-performance, serverless SQLite storage with 9 GB free tier.
"""

import os
import sys
import json
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Optional, Any, Tuple

def get_turso_credentials() -> Tuple[str, str]:
    """Retrieve Turso URL and Auth Token from config or environment"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    turso_url = os.environ.get("TURSO_DATABASE_URL") or os.environ.get("TURSO_URL", "")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("TURSO_TOKEN", "")

    if not turso_url or not turso_token:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    cloud = cfg.get('cloud_storage', {})
                    if not turso_url:
                        turso_url = cloud.get('turso_url', '')
                    if not turso_token:
                        turso_token = cloud.get('turso_token', '')
            except Exception:
                pass

    # Normalize url: libsql:// -> https://
    if turso_url.startswith("libsql://"):
        turso_url = "https://" + turso_url[len("libsql://"):]
    turso_url = turso_url.rstrip('/')

    return turso_url, turso_token

def _to_hrana_val(val: Any) -> Dict[str, Any]:
    """Convert Python value to Hrana value object"""
    if val is None:
        return {"type": "null"}
    elif isinstance(val, bool):
        return {"type": "integer", "value": "1" if val else "0"}
    elif isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    elif isinstance(val, float):
        return {"type": "float", "value": val}
    elif isinstance(val, bytes):
        return {"type": "blob", "base64": base64.b64encode(val).decode('ascii')}
    elif isinstance(val, (dict, list)):
        return {"type": "text", "value": json.dumps(val, ensure_ascii=False)}
    else:
        return {"type": "text", "value": str(val)}

def _from_hrana_row(cols: List[Dict], row: List[Dict]) -> Dict[str, Any]:
    """Convert Hrana result row to Python dict"""
    out = {}
    for col, cell in zip(cols, row):
        name = col.get("name")
        c_type = cell.get("type")
        if c_type == "null":
            out[name] = None
        elif c_type == "integer":
            try:
                out[name] = int(cell.get("value", 0))
            except Exception:
                out[name] = cell.get("value")
        elif c_type == "float":
            try:
                out[name] = float(cell.get("value", 0.0))
            except Exception:
                out[name] = cell.get("value")
        elif c_type == "blob":
            out[name] = base64.b64decode(cell.get("base64", ""))
        else:
            out[name] = cell.get("value")
    return out

class TursoClient:
    def __init__(self, db_url: Optional[str] = None, auth_token: Optional[str] = None):
        u, t = get_turso_credentials()
        self.url = db_url or u
        if self.url.startswith("libsql://"):
            self.url = "https://" + self.url[len("libsql://"):]
        self.url = self.url.rstrip('/')
        self.token = auth_token or t

    def is_configured(self) -> bool:
        return bool(self.url and self.token)

    def execute(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a single SQL statement on Turso and return rows as dicts"""
        if not self.is_configured():
            raise ValueError("Turso URL or Auth Token not configured")

        args = [_to_hrana_val(p) for p in (params or [])]
        payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": sql,
                        "args": args
                    }
                },
                {"type": "close"}
            ]
        }

        endpoint = f"{self.url}/v2/pipeline"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "AnimeVistBot-Turso/1.0"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        results = data.get("results", [])
        if not results:
            return []

        first = results[0]
        if first.get("type") == "error":
            err = first.get("error", {})
            raise RuntimeError(f"Turso Error: {err.get('message') or err}")

        resp_obj = first.get("response", {}).get("result", {})
        cols = resp_obj.get("cols", [])
        rows = resp_obj.get("rows", [])
        return [_from_hrana_row(cols, r) for r in rows]

    def execute_batch(self, stmts: List[Tuple[str, List[Any]]]) -> bool:
        """Execute multiple SQL statements in a single atomic transaction"""
        if not self.is_configured() or not stmts:
            return False

        requests = [{"type": "execute", "stmt": {"sql": "BEGIN;"}}]
        for sql, params in stmts:
            args = [_to_hrana_val(p) for p in (params or [])]
            requests.append({
                "type": "execute",
                "stmt": {"sql": sql, "args": args}
            })
        requests.append({"type": "execute", "stmt": {"sql": "COMMIT;"}})
        requests.append({"type": "close"})

        endpoint = f"{self.url}/v2/pipeline"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"requests": requests}).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "AnimeVistBot-Turso/1.0"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        for r in data.get("results", []):
            if r.get("type") == "error":
                raise RuntimeError(f"Turso Batch Error: {r.get('error')}")
        return True

    def init_schema(self) -> bool:
        """Create all required tables and indexes in Turso"""
        schema_sql = [
            """
            CREATE TABLE IF NOT EXISTS bot_config (
                id TEXT PRIMARY KEY,
                config TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS bot_seen_items (
                item_id TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (item_id, category)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                animevist_user_id TEXT,
                anime_id TEXT NOT NULL,
                anime_title TEXT,
                anime_poster TEXT,
                last_notified_episode INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(telegram_user_id, anime_id)
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_subs_tg_user 
            ON user_subscriptions(telegram_user_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_subs_active_anime 
            ON user_subscriptions(anime_id, active);
            """
        ]
        for sql in schema_sql:
            self.execute(sql.strip())
        return True

# High-Level Helper Functions for AnimeVist Bot

def sync_config_to_turso(conf: Dict[str, Any]) -> Dict[str, Any]:
    client = TursoClient()
    if not client.is_configured():
        return {"ok": False, "error": "Turso не настроен"}
    try:
        sql = """
        INSERT INTO bot_config (id, config, updated_at) 
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET config = excluded.config, updated_at = datetime('now');
        """
        client.execute(sql, ["animevist_main", json.dumps(conf, ensure_ascii=False)])
        return {"ok": True, "message": "Конфиг сохранен в Turso"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch_config_from_turso() -> Dict[str, Any]:
    client = TursoClient()
    if not client.is_configured():
        return {"ok": False, "error": "Turso не настроен"}
    try:
        rows = client.execute("SELECT config FROM bot_config WHERE id = ? LIMIT 1;", ["animevist_main"])
        if rows:
            cfg_str = rows[0].get("config")
            return {"ok": True, "config": json.loads(cfg_str)}
        return {"ok": False, "error": "Конфиг animevist_main не найден в Turso"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def load_seen_from_turso(category: str = 'series', days: int = 30) -> List[str]:
    client = TursoClient()
    if not client.is_configured():
        return []
    try:
        sql = """
        SELECT item_id FROM bot_seen_items 
        WHERE category = ? AND created_at >= datetime('now', ?);
        """
        rows = client.execute(sql, [category, f"-{days} days"])
        return [r["item_id"] for r in rows if "item_id" in r]
    except Exception as e:
        print(f"[Turso] Error loading seen items: {e}")
        return []

def save_seen_to_turso(item_ids: List[str], category: str = 'series') -> bool:
    client = TursoClient()
    if not client.is_configured() or not item_ids:
        return False
    try:
        stmts = []
        sql = """
        INSERT INTO bot_seen_items (item_id, category, created_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(item_id, category) DO NOTHING;
        """
        for i_id in item_ids:
            stmts.append((sql, [str(i_id), category]))
        return client.execute_batch(stmts)
    except Exception as e:
        print(f"[Turso] Error saving seen items: {e}")
        return False

def turso_upsert_user_subscription(
    telegram_user_id: int,
    animevist_user_id: Optional[str],
    anime_id: str,
    anime_title: Optional[str] = None,
    anime_poster: Optional[str] = None,
    last_notified_episode: int = 0,
    active: bool = True
) -> bool:
    client = TursoClient()
    if not client.is_configured():
        return False
    try:
        sql = """
        INSERT INTO user_subscriptions (
            telegram_user_id, animevist_user_id, anime_id, 
            anime_title, anime_poster, last_notified_episode, active, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(telegram_user_id, anime_id) DO UPDATE SET
            last_notified_episode = max(user_subscriptions.last_notified_episode, excluded.last_notified_episode),
            active = excluded.active,
            updated_at = datetime('now'),
            anime_title = coalesce(excluded.anime_title, user_subscriptions.anime_title),
            anime_poster = coalesce(excluded.anime_poster, user_subscriptions.anime_poster),
            animevist_user_id = coalesce(excluded.animevist_user_id, user_subscriptions.animevist_user_id);
        """
        client.execute(sql, [
            int(telegram_user_id),
            animevist_user_id,
            str(anime_id),
            anime_title,
            anime_poster,
            int(last_notified_episode),
            1 if active else 0
        ])
        return True
    except Exception as e:
        print(f"[Turso] Error upserting subscription: {e}")
        return False

def turso_get_user_subscriptions(
    telegram_user_id: Optional[int] = None,
    animevist_user_id: Optional[str] = None,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    client = TursoClient()
    if not client.is_configured():
        return []
    try:
        clauses = []
        params = []
        if telegram_user_id is not None:
            clauses.append("telegram_user_id = ?")
            params.append(int(telegram_user_id))
        if animevist_user_id is not None:
            clauses.append("animevist_user_id = ?")
            params.append(str(animevist_user_id))
        if active_only:
            clauses.append("active = 1")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM user_subscriptions {where} ORDER BY updated_at DESC;"
        rows = client.execute(sql, params)
        for r in rows:
            r["active"] = bool(r.get("active"))
        return rows
    except Exception as e:
        print(f"[Turso] Error getting user subscriptions: {e}")
        return []

def turso_toggle_user_subscription(telegram_user_id: int, anime_id: str, active: bool = False) -> bool:
    client = TursoClient()
    if not client.is_configured():
        return False
    try:
        sql = """
        UPDATE user_subscriptions 
        SET active = ?, updated_at = datetime('now')
        WHERE telegram_user_id = ? AND anime_id = ?;
        """
        client.execute(sql, [1 if active else 0, int(telegram_user_id), str(anime_id)])
        return True
    except Exception as e:
        print(f"[Turso] Error toggling subscription: {e}")
        return False

def turso_get_users_summary() -> Dict[str, int]:
    client = TursoClient()
    if not client.is_configured():
        return {"total_users": 0, "active_subscriptions": 0}
    try:
        u_rows = client.execute("SELECT count(DISTINCT telegram_user_id) as cnt FROM user_subscriptions;")
        s_rows = client.execute("SELECT count(*) as cnt FROM user_subscriptions WHERE active = 1;")
        total_users = u_rows[0].get("cnt", 0) if u_rows else 0
        active_subs = s_rows[0].get("cnt", 0) if s_rows else 0
        return {"total_users": total_users, "active_subscriptions": active_subs}
    except Exception:
        return {"total_users": 0, "active_subscriptions": 0}
