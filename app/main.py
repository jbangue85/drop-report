from dotenv import load_dotenv
load_dotenv()  # Load .env before anything reads os.getenv()

import os
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .database import get_db, init_db, seed_admin_user
from .parser import parse_xlsx, upsert_records
from .analytics import (
    calc_kpis,
    calc_status_distribution,
    calc_daily_trend,
    calc_product_ranking,
    calc_carrier_performance,
    get_action_orders,
    get_filter_options,
)
from .auth import hash_password, verify_password, create_token, decode_token

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="Drop Report API", docs_url="/api/docs")
security = HTTPBearer()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.on_event("startup")
def startup():
    init_db()
    # Seed default admin from env vars (set in docker-compose)
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "dropi2024")
    seed_admin_user(admin_user, hash_password(admin_pass))


# ── Auth helpers ─────────────────────────────────────────────────────────────

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return payload


def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return user


# ── Auth routes ───────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginRequest):
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash, role FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    conn.close()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_token(body.username, row["role"])
    return {"access_token": token, "token_type": "bearer", "role": row["role"]}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@app.post("/api/auth/change-password")
def change_password(body: ChangePasswordRequest, user=Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?", (user["sub"],)
    ).fetchone()
    if not row or not verify_password(body.old_password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (hash_password(body.new_password), user["sub"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Upload routes ─────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xlsx")
    content = await file.read()
    records = parse_xlsx(content, file.filename)
    if not records:
        raise HTTPException(status_code=422, detail="El archivo no contiene datos válidos")
    conn = get_db()
    count = upsert_records(conn, records)
    conn.execute(
        "INSERT INTO uploads (filename, rows_upserted) VALUES (?, ?)",
        (file.filename, count),
    )
    conn.commit()
    conn.close()
    return {"filename": file.filename, "rows_upserted": count}


@app.get("/api/uploads")
def list_uploads(user=Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT filename, rows_upserted, uploaded_at FROM uploads ORDER BY uploaded_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Dashboard routes ──────────────────────────────────────────────────────────

def common_filters(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    estatus: Optional[List[str]] = Query(None),
):
    return {"date_from": date_from, "date_to": date_to, "estatus": estatus}


@app.get("/api/kpis")
def kpis(filters=Depends(common_filters), user=Depends(get_current_user)):
    conn = get_db()
    result = calc_kpis(conn, **filters)
    conn.close()
    return result


@app.get("/api/charts/status")
def chart_status(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_status_distribution(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/charts/trend")
def chart_trend(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_daily_trend(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/charts/products")
def chart_products(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_product_ranking(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/charts/carriers")
def chart_carriers(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = calc_carrier_performance(conn, date_from, date_to)
    conn.close()
    return result


@app.get("/api/filters/options")
def filter_options(user=Depends(get_current_user)):
    conn = get_db()
    result = get_filter_options(conn)
    conn.close()
    return result


# ── Call Center routes ────────────────────────────────────────────────────────

@app.get("/api/calls/pending")
def calls_pending(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conn = get_db()
    result = get_action_orders(conn, date_from, date_to)
    conn.close()
    return result


class CallNoteRequest(BaseModel):
    order_id: int
    resultado: str   # CONTACTADO | NO_CONTESTO | BUZON | SOLUCIONADO | DEVOLUCION | OTRO
    notas: Optional[str] = None


@app.post("/api/calls/notes")
def save_call_note(body: CallNoteRequest, user=Depends(get_current_user)):
    valid = {"CONTACTADO", "NO_CONTESTO", "BUZON", "SOLUCIONADO", "DEVOLUCION", "OTRO"}
    if body.resultado not in valid:
        raise HTTPException(status_code=400, detail=f"resultado debe ser uno de: {valid}")
    conn = get_db()
    conn.execute(
        "INSERT INTO call_notes (order_id, agent, resultado, notas) VALUES (?, ?, ?, ?)",
        (body.order_id, user["sub"], body.resultado, body.notas),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/calls/notes/{order_id}")
def get_call_notes(order_id: int, user=Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM call_notes WHERE order_id = ? ORDER BY called_at DESC",
        (order_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Users management (admin only) ─────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "agent"


@app.post("/api/users")
def create_user(body: CreateUserRequest, admin=Depends(require_admin)):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (body.username, hash_password(body.password), body.role),
        )
        conn.commit()
    except Exception:
        raise HTTPException(status_code=409, detail="El usuario ya existe")
    finally:
        conn.close()
    return {"ok": True, "username": body.username}


@app.get("/api/users")
def list_users(admin=Depends(require_admin)):
    conn = get_db()
    rows = conn.execute("SELECT id, username, role FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Serve frontend ─────────────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
