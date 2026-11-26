"""Local development data layer: SQLite + filesystem storage, no Supabase required.

Enable with ``LOCAL_MODE=1``. It implements the **exact same interface** as
``SupabaseGateway`` (PostgREST-ish ``select/insert/update/delete`` plus upload /
sign_urls / remove), so every service, endpoint and RLS-scoped query keeps working
unchanged. Every row and object is scoped to a ``user_id`` exactly like RLS would.

This module must never be used in production: it has no real authentication
provider (see ``app.utils.local_auth``) and stores tokens in plain SQLite.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .supabase_client import SupabaseError

TABLES = ("profiles", "predictions", "feedback", "model_metrics")


class LocalStore:
    def __init__(self, db_path: str, storage_dir: str, public_base_url: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage = Path(storage_dir)
        self.storage.mkdir(parents=True, exist_ok=True)
        self.base_url = public_base_url.rstrip("/")
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------ plumbing
    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    confirmed INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    email TEXT, full_name TEXT, avatar_url TEXT,
                    preferred_language TEXT NOT NULL DEFAULT 'en',
                    theme TEXT NOT NULL DEFAULT 'system',
                    save_images INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS predictions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    image_path TEXT,
                    predicted_category TEXT NOT NULL,
                    predicted_class TEXT,
                    confidence_score REAL NOT NULL,
                    is_confident INTEGER NOT NULL,
                    top_predictions TEXT NOT NULL,
                    uncertainty_reasons TEXT NOT NULL DEFAULT '[]',
                    disposal_instructions TEXT NOT NULL DEFAULT '{}',
                    safety_precautions TEXT NOT NULL DEFAULT '{}',
                    recyclable INTEGER,
                    quality_warnings TEXT NOT NULL DEFAULT '[]',
                    model_name TEXT NOT NULL, model_version TEXT NOT NULL,
                    inference_time_ms REAL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS pred_user_created ON predictions (user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    prediction_id TEXT NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
                    user_correctness_feedback INTEGER NOT NULL,
                    corrected_category TEXT, comments TEXT,
                    verified_label INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE (user_id, prediction_id)
                );
                CREATE TABLE IF NOT EXISTS used_link_tokens (
                    nonce TEXT PRIMARY KEY,
                    used_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id TEXT PRIMARY KEY, model_name TEXT NOT NULL, model_version TEXT NOT NULL,
                    accuracy REAL, precision_macro REAL, recall_macro REAL, f1_macro REAL,
                    test_dataset TEXT, details TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
                    UNIQUE (model_name, model_version, test_dataset)
                );
                """
            )

    def use_link_token(self, nonce: str) -> bool:
        """Single-use guard: returns False if this link token was already consumed."""
        with self._lock, self._conn() as c:
            try:
                c.execute("INSERT INTO used_link_tokens (nonce, used_at) VALUES (?,?)",
                          (nonce, datetime.now(timezone.utc).isoformat()))
                return True
            except sqlite3.IntegrityError:
                return False

    # ------------------------------------------------------------------ auth store
    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
        return f"{salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, stored: str) -> bool:
        try:
            salt_hex, digest_hex = stored.split("$", 1)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
        return hmac.compare_digest(digest.hex(), digest_hex)

    def create_user(self, email: str, password: str, full_name: str | None, confirmed: bool = True) -> dict:
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as c:
            try:
                c.execute("INSERT INTO users (id,email,password_hash,full_name,confirmed,created_at) VALUES (?,?,?,?,?,?)",
                          (user_id, email.lower().strip(), self.hash_password(password), full_name, int(confirmed), now))
            except sqlite3.IntegrityError:
                raise SupabaseError(409, "An account with this email already exists.")
            c.execute("INSERT INTO profiles (id,email,full_name,created_at,updated_at) VALUES (?,?,?,?,?)",
                      (user_id, email.lower().strip(), full_name, now, now))
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(r) if r else None

    def get_user_by_email(self, email: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
            return dict(r) if r else None

    def confirm_user(self, email: str) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE users SET confirmed=1 WHERE email=?", (email.lower().strip(),))
            return cur.rowcount > 0

    def update_password(self, user_id: str, password: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (self.hash_password(password), user_id))

    def delete_user(self, user_id: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM users WHERE id=?", (user_id,))

    # ------------------------------------------------------------------ json helpers
    @staticmethod
    def _decode(table: str, row: dict) -> dict:
        out = dict(row)
        for key in ("top_predictions", "disposal_instructions", "safety_precautions", "quality_warnings",
                    "uncertainty_reasons", "details"):
            if key in out and isinstance(out[key], str):
                try:
                    out[key] = json.loads(out[key])
                except json.JSONDecodeError:
                    pass
        for key in ("is_confident", "recyclable", "save_images", "user_correctness_feedback", "verified_label",
                    "confirmed"):
            if key in out and out[key] is not None:
                out[key] = bool(out[key])
        return out

    @staticmethod
    def _encode(row: dict) -> dict:
        out = {}
        for k, v in row.items():
            out[k] = json.dumps(v) if isinstance(v, (dict, list)) else (int(v) if isinstance(v, bool) else v)
        return out

    # ------------------------------------------------------------------ query filter
    @staticmethod
    def _split_and(params: dict[str, str]) -> list[tuple[str, str, str]]:
        """Translate PostgREST-ish params into [(column, op, value)] filters."""
        out: list[tuple[str, str, str]] = []
        for key, raw in params.items():
            if key in ("select", "order", "limit", "offset", "and"):
                continue
            value = str(raw)
            if value.startswith("eq."):
                out.append((key, "eq", value[3:]))
            elif value.startswith("not.is.null"):
                out.append((key, "notnull", ""))
            elif value.startswith("gte."):
                out.append((key, "gte", value[4:]))
            elif value.startswith("lte."):
                out.append((key, "lte", value[4:]))
            elif value.startswith("lt."):
                out.append((key, "lt", value[3:]))
            elif value.startswith("gt."):
                out.append((key, "gt", value[3:]))
            elif value == "is.null":
                out.append((key, "isnull", ""))
        # `and=(created_at.gte.X,created_at.lt.Y)` -> individual filters
        and_raw = params.get("and")
        if and_raw:
            inner = and_raw.strip()
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1]
            for part in inner.split(","):
                part = part.strip()
                for op, prefix in (("gte", "gte."), ("lte", "lte."), ("lt", "lt."), ("gt", "gt."), ("eq", "eq.")):
                    if prefix in part:
                        col, _, val = part.partition(prefix)
                        out.append((col, op, val))
                        break
        return out

    @staticmethod
    def _where(filters: list[tuple[str, str, str]]) -> tuple[str, list[Any]]:
        clauses, args = [], []
        for col, op, val in filters:
            if op == "eq":
                clauses.append(f"{col} = ?")
                args.append(val)
            elif op == "notnull":
                clauses.append(f"{col} IS NOT NULL")
            elif op == "isnull":
                clauses.append(f"{col} IS NULL")
            else:
                clauses.append(f"{col} {op.upper()} ?")
                args.append(val)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), args

    def _order(self, params: dict[str, str], default: str) -> str:
        raw = params.get("order", default)
        parts = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            col, _, direction = chunk.partition(".")
            if not col.replace("_", "").isalnum():
                continue
            parts.append(f"{col} {'DESC' if direction.lower() == 'desc' else 'ASC'}")
        return ", ".join(parts) or default

    def _select(self, table: str, params: dict[str, str], *, count: bool = False,
                range_: tuple[int, int] | None = None) -> tuple[list[dict], int | None]:
        if table not in TABLES:
            raise SupabaseError(400, f"unknown table {table}")
        where, args = self._where(self._split_and(params))
        order = self._order(params, "created_at DESC" if table != "profiles" else "created_at DESC")
        sql = f"SELECT * FROM {table}{where} ORDER BY {order}"
        if range_:
            sql += f" LIMIT {max(0, range_[1] - range_[0] + 1)} OFFSET {max(0, range_[0])}"
        with self._conn() as c:
            rows = [self._decode(table, dict(r)) for r in c.execute(sql, args).fetchall()]
            total = None
            if count:
                total = c.execute(f"SELECT COUNT(*) FROM {table}{where}", args).fetchone()[0]
        return rows, total

    # ------------------------------------------------------------------ public API (same as SupabaseGateway)
    async def select(self, token: str, table: str, params: dict[str, str], *, count: bool = False,
                     range_: tuple[int, int] | None = None) -> tuple[list[dict], int | None]:
        return self._select(table, params, count=count, range_=range_)

    async def count(self, token: str, table: str, params: dict[str, str]) -> int:
        return self._select(table, params, count=True)[1] or 0

    async def insert(self, token: str, table: str, row: dict) -> dict:
        if table not in TABLES:
            raise SupabaseError(400, f"unknown table {table}")
        data = dict(row)
        data.setdefault("id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if table == "predictions":
            data.setdefault("uncertainty_reasons", [])
        if table == "model_metrics":
            data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        enc = self._encode(data)
        cols = ", ".join(enc)
        marks = ", ".join("?" for _ in enc)
        try:
            with self._lock, self._conn() as c:
                c.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(enc.values()))
                stored = c.execute(f"SELECT * FROM {table} WHERE id=?", (data["id"],)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise SupabaseError(409, f"conflict: {exc}")
        return self._decode(table, dict(stored))

    async def update(self, token: str, table: str, params: dict[str, str], patch: dict) -> list[dict]:
        if table not in TABLES:
            raise SupabaseError(400, f"unknown table {table}")
        where, args = self._where(self._split_and(params))
        if not where:
            raise SupabaseError(400, "refusing to update without a filter")
        enc = self._encode(patch)
        sets = ", ".join(f"{k}=?" for k in enc)
        with self._lock, self._conn() as c:
            ids = [r["id"] for r in c.execute(f"SELECT id FROM {table}{where}", args).fetchall()]
            if not ids:
                return []
            c.execute(f"UPDATE {table} SET {sets}{where}", [*enc.values(), *args])
            rows = [self._decode(table, dict(r)) for r in
                    c.execute(f"SELECT * FROM {table} WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchall()]
        return rows

    async def delete(self, token: str, table: str, params: dict[str, str]) -> list[dict]:
        if table not in TABLES:
            raise SupabaseError(400, f"unknown table {table}")
        where, args = self._where(self._split_and(params))
        if not where:
            raise SupabaseError(400, "refusing to delete without a filter")
        with self._lock, self._conn() as c:
            rows = [self._decode(table, dict(r)) for r in c.execute(f"SELECT * FROM {table}{where}", args).fetchall()]
            if table == "predictions" and params.get("id", "").startswith("eq."):
                pid = params["id"][3:]
                c.execute("DELETE FROM feedback WHERE prediction_id=?", (pid,))
            c.execute(f"DELETE FROM {table}{where}", args)
        return rows

    # ------------------------------------------------------------------ storage
    def _object_path(self, bucket: str, path: str) -> Path:
        safe = Path(path)
        if safe.is_absolute() or ".." in safe.parts:
            raise SupabaseError(400, "invalid storage path")
        return self.storage / bucket / safe

    async def upload(self, token: str, bucket: str, path: str, data: bytes, content_type: str,
                     upsert: bool = False) -> None:
        target = self._object_path(bucket, path)
        if target.exists() and not upsert:
            raise SupabaseError(409, "object already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def download(self, token: str, bucket: str, path: str) -> bytes:
        target = self._object_path(bucket, path)
        if not target.exists():
            raise SupabaseError(404, "object not found")
        return target.read_bytes()

    async def remove(self, token: str, bucket: str, paths: list[str]) -> None:
        for path in paths:
            try:
                target = self._object_path(bucket, path)
            except SupabaseError:
                continue
            target.unlink(missing_ok=True)

    async def sign_urls(self, token: str, bucket: str, paths: list[str], expires_in: int) -> dict[str, str]:
        out: dict[str, str] = {}
        for path in [p for p in paths if p]:
            if not self._object_path(bucket, path).exists():
                continue
            out[path] = f"{self.base_url}/files/{bucket}/{path}"
        return out

    async def list_objects(self, token: str, bucket: str, prefix: str, limit: int = 1000) -> list[dict]:
        root = self.storage / bucket / prefix
        if not root.exists():
            return []
        return [{"name": p.name} for p in sorted(root.rglob("*")) if p.is_file()][:limit]

    # ------------------------------------------------------------------ auth admin
    async def delete_auth_user(self, user_id: str) -> None:
        self.delete_user(user_id)

    async def ping(self) -> bool:
        return True

    # ------------------------------------------------------------------ extras used by local auth endpoints
    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def ts() -> float:
        return time.time()
