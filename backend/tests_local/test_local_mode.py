"""End-to-end tests for LOCAL_MODE (SQLite + built-in auth), no Supabase needed.

These cover the flows that were broken or untested before:

* the e-mail confirmation link (`token_hash` → session) and the old `?code=` fallback
* link expiry, single use, and a resend path for a dead link
* the avatar path shape that account deletion relies on
* uncertainty reasons surviving a history round-trip
* per-user isolation (the local equivalent of RLS)
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

TMP = Path(tempfile.mkdtemp(prefix="ww_local_"))
os.environ.update({
    "LOCAL_MODE": "1",
    "LOCAL_DB_PATH": str(TMP / "test.db"),
    "LOCAL_STORAGE_DIR": str(TMP / "storage"),
    "PUBLIC_BASE_URL": "http://localhost:8000",
    "LOCAL_AUTO_CONFIRM": "1",
    "ENVIRONMENT": "test",
    "MODEL_DIR": str(BACKEND / "model_artifacts"),
    "SUPABASE_URL": "",
    "SUPABASE_ANON_KEY": "",
    # the suite creates many accounts from one IP; keep the limits out of the way
    "LOCAL_SIGNUP_PER_HOUR": "1000",
    "LOCAL_LOGIN_PER_5MIN": "1000",
    "LOCAL_RESEND_PER_5MIN": "1000",
    "LOCAL_RECOVER_PER_HOUR": "1000",
    "LOCAL_ACCOUNT_DELETE_PER_HOUR": "1000",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database.local_store import LocalStore  # noqa: E402
from app.main import app  # noqa: E402

SAMPLE = BACKEND.parent / "ml" / "reports" / "samples" / "user_photo_input.jpg"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def store():
    s = get_settings()
    return LocalStore(s.local_db_path, s.local_storage_dir, s.public_base_url)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------- basics
def test_health_is_ok_in_local_mode(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["model_loaded"] and h["local_mode"] is True


def test_local_info_advertises_mode(client):
    assert client.get("/api/v1/local-info").json()["mode"] == "local"


def test_data_endpoints_require_a_token(client):
    assert client.get("/api/v1/history").status_code == 401
    assert client.get("/api/v1/analytics").status_code == 401


# --------------------------------------------------------------------- signup / login
def test_signup_returns_session_when_auto_confirm_is_on(client):
    r = client.post("/api/v1/auth/signup", json={"email": "auto@example.com", "password": "passw0rd", "full_name": "Auto"})
    assert r.status_code == 201
    body = r.json()
    assert body["needs_confirmation"] is False and body["access_token"]
    me = client.get("/api/v1/profile", headers=_auth(body["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == "auto@example.com"


def test_duplicate_signup_is_rejected(client):
    client.post("/api/v1/auth/signup", json={"email": "dup@example.com", "password": "passw0rd"})
    r = client.post("/api/v1/auth/signup", json={"email": "dup@example.com", "password": "passw0rd"})
    assert r.status_code == 409


def test_weak_password_is_rejected(client):
    r = client.post("/api/v1/auth/signup", json={"email": "weak@example.com", "password": "password"})
    assert r.status_code == 422


def test_unconfirmed_user_cannot_log_in(client, store, monkeypatch):
    monkeypatch.setattr(get_settings(), "local_auto_confirm", False, raising=False)
    store.create_user("pending@example.com", "passw0rd", "Pending", confirmed=False)
    r = client.post("/api/v1/auth/login", json={"email": "pending@example.com", "password": "passw0rd"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "email_not_confirmed"


def test_wrong_password_is_a_clean_401(client):
    r = client.post("/api/v1/auth/login", json={"email": "auto@example.com", "password": "nope1234"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"


# --------------------------------------------------------------------- the email link
def test_confirmation_link_is_single_use(client, store):
    """The bug the user reported: clicking a link must sign in, exactly once."""
    store.create_user("link@example.com", "passw0rd", "Link", confirmed=False)
    sent = client.post("/api/v1/auth/resend", json={"email": "link@example.com", "redirect_to": "http://localhost:3000"})
    assert sent.status_code == 200
    link = sent.json()["email_link"]
    assert link and "token_hash=" in link and "type=" in link
    token = link.split("token_hash=")[1].split("&")[0]

    first = client.post("/api/v1/auth/confirm", json={"token": token})
    assert first.status_code == 200 and first.json()["access_token"]
    assert client.get("/api/v1/history", headers=_auth(first.json()["access_token"])).status_code == 200

    second = client.post("/api/v1/auth/confirm", json={"token": token})
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "link_used"


def test_expired_and_tampered_links_are_rejected(client):
    bad = client.post("/api/v1/auth/confirm", json={"token": "a@b.com|email|1000000000|deadbeef|bad"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "invalid_link"


def test_resend_refuses_when_already_confirmed(client, store):
    store.create_user("done@example.com", "passw0rd", "Done", confirmed=True)
    r = client.post("/api/v1/auth/resend", json={"email": "done@example.com"})
    assert r.status_code == 200 and r.json()["already_confirmed"] is True


def test_password_reset_flow(client, store):
    store.create_user("reset@example.com", "passw0rd", "Reset", confirmed=True)
    r = client.post("/api/v1/auth/recover", json={"email": "reset@example.com", "redirect_to": "http://localhost:3000"})
    token = r.json()["email_link"].split("token_hash=")[1].split("&")[0]
    session = client.post("/api/v1/auth/reset", json={"token": token})
    assert session.status_code == 200
    changed = client.post("/api/v1/auth/password", json={"password": "newpass123"},
                          headers=_auth(session.json()["access_token"]))
    assert changed.status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "newpass123"}).status_code == 200


# --------------------------------------------------------------------- predict / history
def test_predict_history_and_reasons_round_trip(client):
    token = client.post("/api/v1/auth/signup", json={"email": "scan@example.com", "password": "passw0rd"}).json()["access_token"]
    with open(SAMPLE, "rb") as fh:
        r = client.post("/api/v1/predict", headers=_auth(token), files={"file": ("photo.jpg", fh, "image/jpeg")})
    assert r.status_code == 201
    pred = r.json()
    assert pred["predicted_category"] == "plastic"          # real model, real photo
    assert pred["is_confident"] is True and pred["image_saved"] is True
    assert pred["gradcam_image"].startswith("data:image/jpeg;base64,")

    detail = client.get(f"/api/v1/history/{pred['id']}", headers=_auth(token)).json()
    assert detail["uncertainty_reasons"] == []              # B7: field exists, does not KeyError
    assert detail["guidance"]["bin"] == "blue"
    assert client.get("/api/v1/analytics", headers=_auth(token)).json()["total_scans"] == 1

    # stored image is private: needs the owner's token
    assert client.get(pred["image_url"], headers=_auth(token)).status_code == 200
    assert client.get(pred["image_url"]).status_code == 401

    assert client.delete(f"/api/v1/history/{pred['id']}", headers=_auth(token)).status_code == 204
    assert client.get("/api/v1/history", headers=_auth(token)).json()["total"] == 0


def test_two_users_cannot_see_each_other(client):
    a = client.post("/api/v1/auth/signup", json={"email": "ua@example.com", "password": "passw0rd"}).json()["access_token"]
    b = client.post("/api/v1/auth/signup", json={"email": "ub@example.com", "password": "passw0rd"}).json()["access_token"]
    with open(SAMPLE, "rb") as fh:
        pid = client.post("/api/v1/predict", headers=_auth(a), files={"file": ("p.jpg", fh, "image/jpeg")}).json()["id"]
    assert client.get(f"/api/v1/history/{pid}", headers=_auth(b)).status_code == 404
    assert client.delete(f"/api/v1/history/{pid}", headers=_auth(b)).status_code == 404
    assert client.get("/api/v1/history", headers=_auth(b)).json()["total"] == 0


def test_heic_upload_is_rejected_with_a_clear_code(client):
    token = client.post("/api/v1/auth/signup", json={"email": "heic@example.com", "password": "passw0rd"}).json()["access_token"]
    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 512
    r = client.post("/api/v1/predict", headers=_auth(token), files={"file": ("p.heic", heic, "image/heic")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_type"


# --------------------------------------------------------------------- profile / avatar / account
def test_avatar_path_matches_what_account_deletion_accepts(client):
    from app.utils.validators import is_owned_storage_path

    token = client.post("/api/v1/auth/signup", json={"email": "av@example.com", "password": "passw0rd"}).json()["access_token"]
    with open(SAMPLE, "rb") as fh:
        r = client.put("/api/v1/profile/avatar", headers=_auth(token), files={"file": ("a.jpg", fh, "image/jpeg")})
    assert r.status_code == 201
    path = r.json()["avatar_url"]
    uid = client.get("/api/v1/profile", headers=_auth(token)).json()["id"]
    assert is_owned_storage_path(path, uid), path            # B2 regression guard
    assert client.get(r.json()["avatar_url_signed"], headers=_auth(token)).status_code == 200


def test_profile_preferences_and_save_images_opt_out(client):
    token = client.post("/api/v1/auth/signup", json={"email": "prefs@example.com", "password": "passw0rd"}).json()["access_token"]
    patched = client.patch("/api/v1/profile", headers=_auth(token),
                           json={"save_images": False, "theme": "dark", "preferred_language": "hi"})
    assert patched.status_code == 200 and patched.json()["save_images"] is False
    with open(SAMPLE, "rb") as fh:
        pred = client.post("/api/v1/predict", headers=_auth(token), files={"file": ("p.jpg", fh, "image/jpeg")}).json()
    assert pred["image_saved"] is False


def test_account_deletion_removes_rows_and_avatar(client, store):
    token = client.post("/api/v1/auth/signup", json={"email": "bye@example.com", "password": "passw0rd"}).json()["access_token"]
    with open(SAMPLE, "rb") as fh:
        client.put("/api/v1/profile/avatar", headers=_auth(token), files={"file": ("a.jpg", fh, "image/jpeg")})
    assert client.delete("/api/v1/account", headers=_auth(token)).status_code == 204
    assert client.post("/api/v1/auth/login", json={"email": "bye@example.com", "password": "passw0rd"}).status_code == 401
    assert store.get_user_by_email("bye@example.com") is None
    # no orphaned avatar left on disk
    assert not any(p.name.startswith("avatar-") and "bye" in str(p) for p in (TMP / "storage").rglob("*"))
