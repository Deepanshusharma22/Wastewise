"""Test fixtures.

* A tiny ONNX graph with the SAME interface as the exported WasteWise model
  (input ``image`` -> ``features``, ``category_logits``, ``item_logits``; head = GAP -> Linear -> Hardswish
  -> Linear) so the real inference / Grad-CAM / API code paths run end to end without the 15+ MB artefact.
  Tests that need the real exported model live in test_real_model.py and are skipped when it is absent.
* A real ES256 key pair + JWKS, so JWT verification is exercised exactly as in production.
* An in-memory Supabase fake behind httpx.MockTransport that scopes every row / object to the JWT ``sub``
  (emulating RLS + storage policies).
"""
from __future__ import annotations

import base64
import copy
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

CATEGORIES = ["organic", "paper_cardboard", "plastic", "metal", "glass", "e_waste", "hazardous"]
ITEMS = ["food_waste", "eggshells", "coffee_grounds", "tea_bags", "cardboard", "newspaper_magazine", "office_paper",
         "plastic_bottle", "plastic_food_container", "plastic_bag", "plastic_cutlery_straw", "plastic_cup_lid",
         "styrofoam", "aluminium_can", "steel_food_can", "glass_bottle", "glass_jar_container", "battery",
         "mobile_phone", "laptop", "keyboard", "computer_mouse", "television", "camera", "microwave", "smartwatch",
         "aerosol_can"]
ITEM_TO_CATEGORY = {**{i: "organic" for i in ITEMS[0:4]}, **{i: "paper_cardboard" for i in ITEMS[4:7]},
                    **{i: "plastic" for i in ITEMS[7:13]}, **{i: "metal" for i in ITEMS[13:15]},
                    **{i: "glass" for i in ITEMS[15:17]}, **{i: "e_waste" for i in ITEMS[17:26]},
                    "aerosol_can": "hazardous"}
SUPABASE_URL = "https://test-project.supabase.co"
ANON = "sb_publishable_test"
SERVICE = "sb_secret_test"
HIDDEN = 8


def _build_tiny_model(model_dir: Path) -> dict:
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    rng = np.random.default_rng(0)
    w1 = (rng.standard_normal((HIDDEN, 3)) * 4).astype(np.float32)
    b1 = (rng.standard_normal(HIDDEN) * 0.5).astype(np.float32)
    w2 = (rng.standard_normal((len(CATEGORIES), HIDDEN)) * 3).astype(np.float32)
    b2 = np.zeros(len(CATEGORIES), np.float32)
    w3 = (rng.standard_normal((len(ITEMS), HIDDEN)) * 3).astype(np.float32)
    b3 = np.zeros(len(ITEMS), np.float32)
    inits = [numpy_helper.from_array(a, n) for a, n in
             [(w1, "w1"), (b1, "b1"), (w2, "w2"), (b2, "b2"), (w3, "w3"), (b3, "b3")]]
    nodes = [
        helper.make_node("AveragePool", ["image"], ["features"], kernel_shape=[32, 32], strides=[32, 32]),
        helper.make_node("GlobalAveragePool", ["features"], ["gap"]),
        helper.make_node("Flatten", ["gap"], ["flat"], axis=1),
        helper.make_node("Gemm", ["flat", "w1", "b1"], ["z"], transB=1),
        helper.make_node("HardSwish", ["z"], ["h"]),
        helper.make_node("Gemm", ["h", "w2", "b2"], ["category_logits"], transB=1),
        helper.make_node("Gemm", ["h", "w3", "b3"], ["item_logits"], transB=1),
    ]
    graph = helper.make_graph(
        nodes, "tiny_wastewise",
        [helper.make_tensor_value_info("image", TensorProto.FLOAT, ["batch", 3, 224, 224])],
        [helper.make_tensor_value_info("features", TensorProto.FLOAT, ["batch", 3, 7, 7]),
         helper.make_tensor_value_info("category_logits", TensorProto.FLOAT, ["batch", len(CATEGORIES)]),
         helper.make_tensor_value_info("item_logits", TensorProto.FLOAT, ["batch", len(ITEMS)])],
        inits)
    m = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    m.ir_version = 8
    onnx.checker.check_model(m)
    model_dir.mkdir(parents=True, exist_ok=True)
    onnx.save(m, str(model_dir / "wastewise.onnx"))
    np.savez(model_dir / "gradcam_head.npz", w1=w1, b1=b1, w2=w2, b2=b2)
    card = {
        "model_name": "wastewise-classifier", "model_version": "test-0.0.1-tiny", "architecture": "tiny_test_graph",
        "dataset_version": "test", "exported_at": "2026-01-01T00:00:00Z",
        "categories": CATEGORIES, "items": ITEMS, "item_to_category": ITEM_TO_CATEGORY,
        "preprocessing": {"image_size": 224, "resize_size": 256, "mean": [0.485, 0.456, 0.406],
                          "std": [0.229, 0.224, 0.225]},
        "temperature": 1.0, "confidence_threshold": 0.5, "item_display_threshold": 0.6,
        "metrics": {"note": "test model - no metrics"}, "latency": {}, "training_data": [],
        "limitations": ["test model"],
    }
    (model_dir / "model_card.json").write_text(json.dumps(card))
    return card


# ---------------------------------------------------------------- keys / tokens
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
import jwt  # noqa: E402

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
KID = "test-kid-1"


def _b64(n: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()


_pub = PRIVATE_KEY.public_key().public_numbers()
JWKS = {"keys": [{"kty": "EC", "crv": "P-256", "x": _b64(_pub.x), "y": _b64(_pub.y), "kid": KID, "alg": "ES256",
                  "use": "sig"}]}


def make_token(sub: str, *, exp_in: int = 3600, aud: str = "authenticated", role: str = "authenticated",
               iss: str | None = None, key=None, alg: str = "ES256", kid: str = KID) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": aud, "role": role, "exp": now + exp_in, "iat": now,
              "iss": iss or f"{SUPABASE_URL}/auth/v1", "email": f"{sub[:8]}@example.com"}
    return jwt.encode(claims, key or PRIVATE_KEY, algorithm=alg, headers={"kid": kid})


# ---------------------------------------------------------------- environment (before app import)
MODEL_DIR = Path(tempfile.mkdtemp(prefix="ww_model_"))
TINY_CARD = _build_tiny_model(MODEL_DIR)
os.environ.update({
    # The Supabase contract suite always runs in Supabase mode, even if backend/.env
    # enables LOCAL_MODE for the demo. The local-mode suite lives in tests_local/.
    "LOCAL_MODE": "0",
    "ENVIRONMENT": "test", "SUPABASE_URL": SUPABASE_URL, "SUPABASE_ANON_KEY": ANON,
    "SUPABASE_SERVICE_ROLE_KEY": SERVICE, "SUPABASE_JWKS": json.dumps(JWKS), "MODEL_DIR": str(MODEL_DIR),
    "CORS_ORIGINS": "http://localhost:3000", "PREDICT_RATE_PER_MINUTE": "1000", "PREDICT_RATE_PER_DAY": "100000",
})

# tests_local/ sets LOCAL_MODE=1 at import time; this suite must always be Supabase mode.
os.environ["LOCAL_MODE"] = "0"

import httpx  # noqa: E402
import pytest  # noqa: E402


# ---------------------------------------------------------------- in-memory Supabase fake
class FakeSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {"profiles": [], "predictions": [], "feedback": []}
        self.objects: dict[str, dict[str, bytes]] = {"waste-images": {}, "avatars": {}}
        self.deleted_users: list[str] = []
        self.fail_insert = False
        self.requests: list[httpx.Request] = []

    # ---- helpers
    @staticmethod
    def _sub(req: httpx.Request) -> str | None:
        auth = req.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return None
        tok = auth[7:]
        if tok in (ANON, SERVICE):
            return None
        return jwt.decode(tok, options={"verify_signature": False})["sub"]

    def add_profile(self, uid: str, save_images: bool = True) -> None:
        self.tables["profiles"].append({"id": uid, "email": f"{uid[:8]}@example.com", "save_images": save_images,
                                        "avatar_url": None})

    def _visible(self, table: str, sub: str) -> list[dict]:
        key = "id" if table == "profiles" else "user_id"
        return [r for r in self.tables[table] if r[key] == sub]          # RLS: own rows only

    @staticmethod
    def _match(row: dict, params: dict) -> bool:
        for k, v in params.items():
            if k in ("select", "order", "limit", "offset"):
                continue
            if k == "and":
                for cond in v.strip("()").split(","):
                    col, op, val = cond.split(".", 2)
                    cell = str(row.get(col))
                    if op == "gte" and not cell >= val:
                        return False
                    if op == "lt" and not cell < val:
                        return False
                continue
            cell = row.get(k)
            if v == "not.is.null":
                if cell is None:
                    return False
            elif v.startswith("eq."):
                want = v[3:]
                if isinstance(cell, bool):
                    if str(cell).lower() != want:
                        return False
                elif str(cell) != want:
                    return False
        return True

    @staticmethod
    def _order(rows: list[dict], order: str | None) -> list[dict]:
        if not order:
            return rows
        for part in reversed(order.split(",")):
            col, direction = part.split(".")
            rows = sorted(rows, key=lambda r: r[col], reverse=direction == "desc")
        return rows

    def _json(self, status: int, data, headers: dict | None = None) -> httpx.Response:
        return httpx.Response(status, json=data, headers=headers or {})

    # ---- router
    def handler(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        path = req.url.path
        if req.headers.get("apikey") not in (ANON, SERVICE):
            return self._json(401, {"message": "no apikey"})
        if path.startswith("/rest/v1/"):
            return self._rest(req, path[len("/rest/v1/"):])
        if path.startswith("/storage/v1/"):
            return self._storage(req, path[len("/storage/v1/"):])
        if path.startswith("/auth/v1/admin/users/") and req.method == "DELETE":
            if req.headers.get("authorization") != f"Bearer {SERVICE}":
                return self._json(403, {"msg": "not admin"})
            uid = path.rsplit("/", 1)[-1]
            self.deleted_users.append(uid)
            for t in ("predictions", "feedback"):
                self.tables[t] = [r for r in self.tables[t] if r["user_id"] != uid]
            self.tables["profiles"] = [r for r in self.tables["profiles"] if r["id"] != uid]
            return self._json(200, {})
        if path == "/auth/v1/health":
            return self._json(200, {"ok": True})
        return self._json(404, {"message": f"unhandled {path}"})

    def _rest(self, req: httpx.Request, table: str) -> httpx.Response:
        sub = self._sub(req)
        if sub is None:
            return self._json(401, {"message": "JWT required"})
        params = dict(req.url.params)
        if req.method in ("GET", "HEAD"):
            rows = [r for r in self._visible(table, sub) if self._match(r, params)]
            rows = self._order(rows, params.get("order"))
            total = len(rows)
            if "range" in req.headers:
                a, b = (int(x) for x in req.headers["range"].split("-"))
                if a >= total and total > 0:
                    return httpx.Response(416, headers={"content-range": f"*/{total}"})
                rows = rows[a:b + 1]
            headers = {"content-range": f"0-{max(len(rows) - 1, 0)}/{total}"}
            if req.method == "HEAD":
                return httpx.Response(200, headers=headers)
            return self._json(200, copy.deepcopy(rows), headers)
        if req.method == "POST":
            if self.fail_insert:
                return self._json(500, {"message": "insert failed (simulated)"})
            row = json.loads(req.content)
            owner = row.get("user_id", row.get("id"))
            if owner != sub:
                return self._json(403, {"message": "new row violates row-level security policy"})
            if table == "predictions":
                if row.get("image_path") and not row["image_path"].startswith(f"{row['user_id']}/"):
                    return self._json(400, {"message": "violates check constraint image_path_scoped"})
            row = {"id": row.get("id") or str(uuid.uuid4()), **row,
                   "created_at": datetime.now(timezone.utc).isoformat()}
            self.tables[table].append(row)
            return self._json(201, [copy.deepcopy(row)])
        if req.method == "PATCH":
            patch = json.loads(req.content)
            hit = [r for r in self._visible(table, sub) if self._match(r, params)]
            for r in hit:
                r.update(patch)
            return self._json(200, copy.deepcopy(hit))
        if req.method == "DELETE":
            hit = [r for r in self._visible(table, sub) if self._match(r, params)]
            ids = {id(r) for r in hit}
            self.tables[table] = [r for r in self.tables[table] if id(r) not in ids]
            if table == "predictions":   # FK cascade
                gone = {r["id"] for r in hit}
                self.tables["feedback"] = [f for f in self.tables["feedback"] if f["prediction_id"] not in gone]
            return self._json(200, copy.deepcopy(hit))
        return self._json(405, {"message": "method"})

    def _storage(self, req: httpx.Request, rest: str) -> httpx.Response:
        sub = self._sub(req)
        if sub is None:
            return self._json(401, {"message": "JWT required"})
        if rest.startswith("object/sign/"):
            bucket = rest[len("object/sign/"):]
            body = json.loads(req.content)
            out = []
            for p in body["paths"]:
                if p.startswith(f"{sub}/") and p in self.objects[bucket]:
                    out.append({"path": p, "signedURL": f"/object/sign/{bucket}/{p}?token=t", "error": None})
                else:
                    out.append({"path": p, "signedURL": None, "error": "not found"})
            return self._json(200, out)
        if req.method == "DELETE" and rest.startswith("object/"):
            bucket = rest[len("object/"):]
            body = json.loads(req.content)
            removed = []
            for p in body["prefixes"]:
                if p.startswith(f"{sub}/") and self.objects[bucket].pop(p, None) is not None:
                    removed.append({"name": p})
            return self._json(200, removed)
        if req.method == "POST" and rest.startswith("object/"):
            bucket, _, objpath = rest[len("object/"):].partition("/")
            if not objpath.startswith(f"{sub}/"):
                return self._json(403, {"message": "new row violates row-level security policy"})
            if len(req.content) > 5 * 1024 * 1024:
                return self._json(413, {"message": "too large"})
            self.objects[bucket][objpath] = req.content
            return self._json(200, {"Key": f"{bucket}/{objpath}"})
        return self._json(404, {"message": "unhandled storage"})


@pytest.fixture
def fake() -> FakeSupabase:
    return FakeSupabase()


@pytest.fixture
def app_client(fake):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.database.supabase_client import SupabaseGateway
    from app.main import app
    from app.utils.rate_limit import limiter

    limiter.reset()
    s = get_settings()
    with TestClient(app) as client:
        transport_client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
        app.state.gateway = SupabaseGateway(s.supabase_url, s.supabase_anon_key, s.supabase_service_role_key,
                                            transport_client)
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def user_a(fake):
    uid = str(uuid.uuid4())
    fake.add_profile(uid)
    return uid, {"Authorization": f"Bearer {make_token(uid)}"}


@pytest.fixture
def user_b(fake):
    uid = str(uuid.uuid4())
    fake.add_profile(uid)
    return uid, {"Authorization": f"Bearer {make_token(uid)}"}


def jpeg_bytes(color=(200, 60, 40), size=(320, 240), noise: bool = True) -> bytes:
    import io

    from PIL import Image
    rng = np.random.default_rng(1)
    arr = np.zeros((size[1], size[0], 3), np.uint8) + np.array(color, np.uint8)
    if noise:  # texture so the blur heuristic does not fire
        arr = np.clip(arr.astype(int) + rng.integers(-60, 60, arr.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=92)
    return buf.getvalue()


def png_bytes(size=(200, 200)) -> bytes:
    import io

    from PIL import Image
    rng = np.random.default_rng(2)
    buf = io.BytesIO()
    Image.fromarray(rng.integers(0, 255, (size[1], size[0], 4), dtype=np.uint8), "RGBA").save(buf, "PNG")
    return buf.getvalue()
