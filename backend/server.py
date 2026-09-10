from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
import uuid
import math
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone, timedelta, date
import httpx
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from emergentintegrations.llm.chat import LlmChat, UserMessage
from pypdf import PdfReader
import json as _json
import re
import ipaddress
import secrets as _secrets
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from fastapi import BackgroundTasks

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============== AUTH ===============

async def get_current_user(request: Request):
    """REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH"""
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = sess["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


class SessionIn(BaseModel):
    session_id: str


@api_router.post("/auth/session")
async def process_session(payload: SessionIn, response: Response):
    async with httpx.AsyncClient(timeout=15.0) as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": payload.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session id")
    data = r.json()
    email = data["email"]
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture", "")
    session_token = data["session_token"]

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    expires = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    response.set_cookie(
        key="session_token", value=session_token,
        max_age=7 * 24 * 3600, httponly=True, secure=True,
        samesite="none", path="/",
    )
    return {"user_id": user_id, "email": email, "name": name, "picture": picture}


@api_router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"],
            "name": user["name"], "picture": user.get("picture", "")}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}

# =============== MODELS ===============

class Client(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    codice_cliente: Optional[str] = ""
    name: str
    address: str
    city: Optional[str] = ""
    cap: Optional[str] = ""
    provincia: Optional[str] = ""
    contact_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    piva: Optional[str] = ""
    codice_fiscale: Optional[str] = ""
    codice_destinatario: Optional[str] = ""  # 7-char SdI code, "0000000" default
    pec: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ClientIn(BaseModel):
    codice_cliente: Optional[str] = ""
    name: str
    address: str
    city: Optional[str] = ""
    cap: Optional[str] = ""
    provincia: Optional[str] = ""
    contact_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    piva: Optional[str] = ""
    codice_fiscale: Optional[str] = ""
    codice_destinatario: Optional[str] = ""
    pec: Optional[str] = ""
    notes: Optional[str] = ""


class Contract(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    numero_preventivo: Optional[str] = ""
    client_id: str
    title: str
    total_days: float
    daily_rate: float = 0
    intervention_type: str = "consulenza"
    max_per_month: Optional[int] = None  # limite interventi al mese
    priority: str = "medium"  # high, medium, low
    start_date: Optional[str] = None  # ISO date
    deadline: Optional[str] = None  # ISO date
    signed_date: Optional[str] = None
    status: str = "active"  # active, planned, completed, invoiced
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContractIn(BaseModel):
    numero_preventivo: Optional[str] = ""
    client_id: str
    title: str
    total_days: float
    daily_rate: float = 0
    intervention_type: str = "consulenza"
    max_per_month: Optional[int] = None
    priority: str = "medium"
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    signed_date: Optional[str] = None
    notes: Optional[str] = ""


class Intervention(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    contract_id: str
    client_id: str
    date: str  # YYYY-MM-DD
    slot: str = "full"  # full | morning | afternoon
    day_index: int  # 1..total_days
    status: str = "planned"  # planned | confirmed | done | cancelled
    confirmed_at: Optional[str] = None
    confirmation_email_id: Optional[str] = None
    notes: Optional[str] = ""


# =============== GEOCODING ===============

async def geocode(address: str, city: str = "") -> Optional[dict]:
    q = f"{address}, {city}" if city else address
    try:
        async with httpx.AsyncClient(timeout=10.0) as hc:
            r = await hc.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": "PlanOp/1.0 (planop@example.com)"},
            )
        if r.status_code == 200:
            arr = r.json()
            if arr:
                return {"lat": float(arr[0]["lat"]), "lng": float(arr[0]["lon"])}
    except Exception as e:
        logger.warning(f"Geocoding failed: {e}")
    return None


def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# =============== CLIENTS ===============

@api_router.get("/clients", response_model=List[Client])
async def list_clients(user=Depends(get_current_user)):
    docs = await db.clients.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    return [Client(**d) for d in docs]


@api_router.post("/clients", response_model=Client)
async def create_client(payload: ClientIn, user=Depends(get_current_user)):
    coords = await geocode(payload.address, payload.city or "")
    c = Client(user_id=user["user_id"], **payload.model_dump(),
               lat=coords["lat"] if coords else None,
               lng=coords["lng"] if coords else None)
    await db.clients.insert_one(c.model_dump())
    return c


@api_router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, payload: ClientIn, user=Depends(get_current_user)):
    doc = await db.clients.find_one({"id": client_id, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Client not found")
    coords = await geocode(payload.address, payload.city or "")
    updates = payload.model_dump()
    if coords:
        updates["lat"] = coords["lat"]
        updates["lng"] = coords["lng"]
    await db.clients.update_one({"id": client_id}, {"$set": updates})
    doc = await db.clients.find_one({"id": client_id}, {"_id": 0})
    return Client(**doc)


@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, user=Depends(get_current_user)):
    await db.clients.delete_one({"id": client_id, "user_id": user["user_id"]})
    return {"ok": True}


# =============== CONTRACTS ===============

@api_router.get("/contracts", response_model=List[Contract])
async def list_contracts(user=Depends(get_current_user)):
    docs = await db.contracts.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [Contract(**d) for d in docs]


@api_router.post("/contracts", response_model=Contract)
async def create_contract(payload: ContractIn, user=Depends(get_current_user)):
    client_doc = await db.clients.find_one({"id": payload.client_id, "user_id": user["user_id"]}, {"_id": 0})
    if not client_doc:
        raise HTTPException(400, "Client not found")
    c = Contract(user_id=user["user_id"], **payload.model_dump())
    await db.contracts.insert_one(c.model_dump())
    return c


@api_router.put("/contracts/{contract_id}", response_model=Contract)
async def update_contract(contract_id: str, payload: ContractIn, user=Depends(get_current_user)):
    doc = await db.contracts.find_one({"id": contract_id, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Contract not found")
    await db.contracts.update_one({"id": contract_id}, {"$set": payload.model_dump()})
    doc = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    return Contract(**doc)


@api_router.delete("/contracts/{contract_id}")
async def delete_contract(contract_id: str, user=Depends(get_current_user)):
    await db.contracts.delete_one({"id": contract_id, "user_id": user["user_id"]})
    await db.interventions.delete_many({"contract_id": contract_id, "user_id": user["user_id"]})
    return {"ok": True}


@api_router.post("/contracts/{contract_id}/complete")
async def complete_contract(contract_id: str, user=Depends(get_current_user)):
    doc = await db.contracts.find_one({"id": contract_id, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Contract not found")
    await db.contracts.update_one({"id": contract_id}, {"$set": {"status": "completed"}})
    return {"ok": True}


# =============== PLANNING ===============

class PlanRequest(BaseModel):
    start_from: Optional[str] = None  # YYYY-MM-DD, default = tomorrow
    workdays_only: bool = True  # skip weekends
    max_days_per_client_block: int = 1


@api_router.post("/planning/generate")
async def generate_planning(payload: PlanRequest, user=Depends(get_current_user)):
    """Generates optimized planning: groups nearby clients, respects deadlines & priorities."""
    contracts = await db.contracts.find(
        {"user_id": user["user_id"], "status": {"$in": ["active", "planned"]}},
        {"_id": 0}
    ).to_list(1000)
    if not contracts:
        return {"planned": 0, "interventions": []}

    clients_map = {}
    client_ids = list({c["client_id"] for c in contracts})
    if client_ids:
        cli_docs = await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0}).to_list(1000)
        clients_map = {cl["id"]: cl for cl in cli_docs}

    # Count already-planned interventions per contract
    existing = await db.interventions.find(
        {"user_id": user["user_id"]}, {"_id": 0, "contract_id": 1, "date": 1}
    ).to_list(2000)
    planned_per_contract = {}
    booked_dates = set()
    for iv in existing:
        planned_per_contract[iv["contract_id"]] = planned_per_contract.get(iv["contract_id"], 0) + 1
        booked_dates.add(iv["date"])
    # Manual events block their dates
    manual = await db.manual_events.find(
        {"user_id": user["user_id"]}, {"_id": 0, "date": 1, "all_day": 1}
    ).to_list(2000)
    for ev in manual:
        if ev.get("all_day", True):
            booked_dates.add(ev["date"])

    # Compute remaining days (support decimals - 0.5 = half day = 1 intervention with slot=morning)
    remaining = []
    for c in contracts:
        done = planned_per_contract.get(c["id"], 0)
        # Number of interventions needed = ceil(total_days) since half-days count as 1 intervention slot
        needed = math.ceil(float(c["total_days"]))
        rem = needed - done
        if rem > 0:
            remaining.append({"contract": c, "remaining": rem, "client": clients_map.get(c["client_id"])})

    if not remaining:
        return {"planned": 0, "interventions": []}

    # Priority weight: deadline urgency + priority level
    prio_weight = {"high": 100, "medium": 50, "low": 10}
    today = date.today()

    def urgency(item):
        c = item["contract"]
        dl = c.get("deadline")
        dl_days = 9999
        if dl:
            try:
                dl_days = (datetime.fromisoformat(dl).date() - today).days
            except Exception:
                pass
        return -prio_weight.get(c["priority"], 50) + dl_days

    remaining.sort(key=urgency)

    # Geographic clustering: greedy nearest neighbor from top-priority
    ordered = []
    if remaining:
        current = remaining.pop(0)
        ordered.append(current)
        while remaining:
            cur_client = current["client"]
            if not cur_client or cur_client.get("lat") is None:
                nxt = remaining.pop(0)
            else:
                # Find nearest with also acceptable urgency (top 3 by urgency)
                candidates = remaining[:3]
                best = None
                best_score = float("inf")
                for cand in candidates:
                    cc = cand["client"]
                    if cc and cc.get("lat") is not None:
                        d = haversine(cur_client["lat"], cur_client["lng"], cc["lat"], cc["lng"])
                    else:
                        d = 500
                    # combine distance + urgency
                    dl = cand["contract"].get("deadline")
                    dl_days = 60
                    if dl:
                        try:
                            dl_days = max(0, (datetime.fromisoformat(dl).date() - today).days)
                        except Exception:
                            pass
                    score = d + dl_days * 2
                    if score < best_score:
                        best_score = score
                        best = cand
                if best is None:
                    best = candidates[0]
                remaining.remove(best)
                nxt = best
            ordered.append(nxt)
            current = nxt

    # Assign dates - each contract has its own cursor bounded by [start_date, deadline]
    global_start = datetime.fromisoformat(payload.start_from).date() if payload.start_from else today + timedelta(days=1)
    new_interventions = []
    skipped = []  # {contract_id, reason, remaining}
    max_block = max(1, payload.max_days_per_client_block)
    # Count interventions per (contract_id, YYYY-MM) to enforce max_per_month
    per_month_count = {}
    for iv in existing:
        month_key = iv["date"][:7]
        per_month_count[(iv["contract_id"], month_key)] = per_month_count.get((iv["contract_id"], month_key), 0) + 1

    def _parse_date(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None

    for item in ordered:
        c = item["contract"]
        rem = item["remaining"]
        max_pm = c.get("max_per_month")
        c_start = _parse_date(c.get("start_date"))
        c_deadline = _parse_date(c.get("deadline"))
        # Contract-specific cursor: start not before global_start AND not before contract.start_date
        cur = max(global_start, c_start) if c_start else global_start
        # Skip past-deadline immediately
        if c_deadline and cur > c_deadline:
            skipped.append({"contract_id": c["id"], "reason": "deadline_expired", "remaining": rem})
            continue
        done_for_contract = planned_per_contract.get(c["id"], 0)
        # If contract has fractional total_days (e.g. 3.5), last intervention is a half-day (morning)
        total_days_f = float(c["total_days"])
        has_half = (total_days_f - int(total_days_f)) > 0
        total_needed = math.ceil(total_days_f)
        # RESERVED END DATES: se c'è deadline e servono >=1 interventi, riserva gli ultimi
        # 2 (o 1 se total_needed==1) sui workday finali che finiscono alla deadline
        reserved_end = []  # list of (day_index, date, slot)
        if c_deadline and total_needed >= 1 and done_for_contract == 0:
            n_reserve = 2 if total_needed >= 2 else 1
            end_d = c_deadline
            if payload.workdays_only:
                while end_d.weekday() >= 5:
                    end_d = end_d - timedelta(days=1)
            while end_d.isoformat() in booked_dates and end_d >= cur:
                end_d = end_d - timedelta(days=1)
                if payload.workdays_only:
                    while end_d.weekday() >= 5:
                        end_d = end_d - timedelta(days=1)
            if end_d >= cur:
                slot_last = "morning" if has_half else "full"
                reserved_pairs = [(total_needed, end_d, slot_last)]
                if n_reserve == 2:
                    prev_d = end_d - timedelta(days=1)
                    if payload.workdays_only:
                        while prev_d.weekday() >= 5:
                            prev_d = prev_d - timedelta(days=1)
                    while prev_d.isoformat() in booked_dates and prev_d >= cur:
                        prev_d = prev_d - timedelta(days=1)
                        if payload.workdays_only:
                            while prev_d.weekday() >= 5:
                                prev_d = prev_d - timedelta(days=1)
                    if prev_d >= cur:
                        reserved_pairs.insert(0, (total_needed - 1, prev_d, "full"))
                for day_idx, dt, slot in reserved_pairs:
                    booked_dates.add(dt.isoformat())
                    if max_pm:
                        mk = (c["id"], dt.isoformat()[:7])
                        per_month_count[mk] = per_month_count.get(mk, 0) + 1
                    reserved_end.append((day_idx, dt, slot))
        # Riduci rem del numero di date riservate: il loop pianifica solo i giorni "iniziali"
        rem_body = max(0, rem - len(reserved_end))
        contract_full = False
        while rem_body > 0 and not contract_full:
            block = min(max_block, rem_body)
            for _ in range(block):
                # Skip weekends + booked
                if payload.workdays_only:
                    while cur.weekday() >= 5 or cur.isoformat() in booked_dates:
                        cur = cur + timedelta(days=1)
                        if c_deadline and cur > c_deadline:
                            break
                else:
                    while cur.isoformat() in booked_dates:
                        cur = cur + timedelta(days=1)
                        if c_deadline and cur > c_deadline:
                            break
                if c_deadline and cur > c_deadline:
                    skipped.append({"contract_id": c["id"], "reason": "deadline_reached", "remaining": rem_body})
                    contract_full = True
                    break
                # Enforce max_per_month cap
                if max_pm:
                    mkey = (c["id"], cur.isoformat()[:7])
                    while per_month_count.get(mkey, 0) >= max_pm:
                        nxt_month = cur.replace(day=1) + timedelta(days=32)
                        cur = nxt_month.replace(day=1)
                        if c_deadline and cur > c_deadline:
                            break
                        if payload.workdays_only:
                            while cur.weekday() >= 5 or cur.isoformat() in booked_dates:
                                cur = cur + timedelta(days=1)
                                if c_deadline and cur > c_deadline:
                                    break
                        else:
                            while cur.isoformat() in booked_dates:
                                cur = cur + timedelta(days=1)
                                if c_deadline and cur > c_deadline:
                                    break
                        if c_deadline and cur > c_deadline:
                            break
                        mkey = (c["id"], cur.isoformat()[:7])
                    if c_deadline and cur > c_deadline:
                        skipped.append({"contract_id": c["id"], "reason": "deadline_reached", "remaining": rem_body})
                        contract_full = True
                        break
                iv = Intervention(
                    user_id=user["user_id"],
                    contract_id=c["id"],
                    client_id=c["client_id"],
                    date=cur.isoformat(),
                    slot="full",
                    day_index=done_for_contract + 1,
                )
                new_interventions.append(iv.model_dump())
                booked_dates.add(cur.isoformat())
                if max_pm:
                    mkey = (c["id"], cur.isoformat()[:7])
                    per_month_count[mkey] = per_month_count.get(mkey, 0) + 1
                done_for_contract += 1
                cur = cur + timedelta(days=1)
                rem_body -= 1
        # Append reserved end interventions with the correct final day_index
        for day_idx, dt, slot in reserved_end:
            iv = Intervention(
                user_id=user["user_id"],
                contract_id=c["id"],
                client_id=c["client_id"],
                date=dt.isoformat(),
                slot=slot,
                day_index=day_idx,
            )
            new_interventions.append(iv.model_dump())

    response_items = []
    if new_interventions:
        # Copy dicts before insert to avoid Motor mutating them with _id (ObjectId)
        response_items = [dict(iv) for iv in new_interventions]
        await db.interventions.insert_many(new_interventions)
        contract_ids = list({iv["contract_id"] for iv in new_interventions})
        await db.contracts.update_many({"id": {"$in": contract_ids}}, {"$set": {"status": "planned"}})

    return {"planned": len(response_items), "interventions": response_items, "skipped": skipped}


@api_router.get("/interventions")
async def list_interventions(user=Depends(get_current_user)):
    docs = await db.interventions.find({"user_id": user["user_id"]}, {"_id": 0}).sort("date", 1).to_list(2000)
    return docs


def _slot_label(slot: str) -> str:
    return {"morning": "Mattina (09:00 - 13:30)",
            "afternoon": "Pomeriggio (14:30 - 18:00)",
            "full": "Giornata intera (09:00 - 18:00)"}.get(slot or "full", "Giornata intera (09:00 - 18:00)")


def _confirmation_html(client_name: str, intervention_date: str, slot: str,
                       contract_title: str, day_index: int, total_days: int,
                       address: str) -> str:
    safe_client = escape(client_name)
    safe_title = escape(contract_title)
    safe_date = escape(intervention_date)
    safe_addr = escape(address or "")
    safe_from = escape(EMAIL_FROM_NAME)
    safe_slot = escape(_slot_label(slot))
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0F172A">'
        f'<h2 style="margin:0 0 12px 0;color:#059669">Conferma appuntamento</h2>'
        f'<p>Gentile {safe_client},</p>'
        f'<p>confermiamo il nostro intervento presso la vostra sede ({safe_addr}) '
        f'nell&#39;ambito del contratto <strong>{safe_title}</strong>.</p>'
        f'<div style="background:#ECFDF5;padding:12px;border-radius:6px;margin:16px 0;border-left:3px solid #059669">'
        f'<p style="margin:0"><strong>Data:</strong> {safe_date}</p>'
        f'<p style="margin:4px 0 0 0"><strong>Orario:</strong> {safe_slot}</p>'
        f'<p style="margin:4px 0 0 0"><strong>Giornata:</strong> {day_index} di {total_days}</p>'
        f'</div>'
        f'<p>Riceverete un ulteriore promemoria 24 ore prima. Per qualsiasi variazione, rispondere pure a questa email.</p>'
        f'<p style="margin-top:24px">Cordiali saluti,<br>{safe_from}</p>'
        f'<hr style="border:none;border-top:1px solid #E2E8F0;margin:20px 0">'
        f'<p style="font-size:11px;color:#64748B">Email inviata da {safe_from}. Non chiediamo mai password, codici o dati di pagamento via email.</p>'
        f'</td></tr></table>'
    )


class InterventionUpdate(BaseModel):
    slot: Optional[str] = None  # full | morning | afternoon
    notes: Optional[str] = None


@api_router.put("/interventions/{intervention_id}")
async def update_intervention(intervention_id: str, payload: InterventionUpdate, user=Depends(get_current_user)):
    doc = await db.interventions.find_one({"id": intervention_id, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Intervento non trovato")
    updates = {}
    if payload.slot is not None:
        if payload.slot not in ("full", "morning", "afternoon"):
            raise HTTPException(400, "Slot non valido")
        updates["slot"] = payload.slot
    if payload.notes is not None:
        updates["notes"] = payload.notes
    if updates:
        await db.interventions.update_one({"id": intervention_id}, {"$set": updates})
    fresh = await db.interventions.find_one({"id": intervention_id}, {"_id": 0})
    return fresh


@api_router.post("/interventions/{intervention_id}/confirm")
async def confirm_intervention(intervention_id: str, user=Depends(get_current_user)):
    """Mark an intervention as confirmed and send confirmation email to the client."""
    iv = await db.interventions.find_one({"id": intervention_id, "user_id": user["user_id"]}, {"_id": 0})
    if not iv:
        raise HTTPException(404, "Intervento non trovato")
    client = await db.clients.find_one({"id": iv["client_id"]}, {"_id": 0})
    contract = await db.contracts.find_one({"id": iv["contract_id"]}, {"_id": 0})
    if not client or not contract:
        raise HTTPException(400, "Cliente o contratto non trovato")

    email_id = None
    warning = None
    if client.get("email"):
        try:
            html = _confirmation_html(
                client_name=client.get("name", "Cliente"),
                intervention_date=iv["date"],
                slot=iv.get("slot", "full"),
                contract_title=contract.get("title", ""),
                day_index=iv.get("day_index", 1),
                total_days=contract.get("total_days", 0),
                address=f"{client.get('address','')} {client.get('city','')}".strip(),
            )
            email_id = await send_email(
                to=client["email"],
                subject=f"Conferma intervento {iv['date']} - {contract.get('title','')[:50]}",
                html=html,
            )
        except HTTPException as e:
            warning = f"Email non inviata: {e.detail}"
    else:
        warning = "Cliente senza email in anagrafica"

    await db.interventions.update_one(
        {"id": intervention_id},
        {"$set": {
            "status": "confirmed",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "confirmation_email_id": email_id,
        }},
    )
    return {"ok": True, "email_id": email_id, "warning": warning}


@api_router.post("/interventions/{intervention_id}/unconfirm")
async def unconfirm_intervention(intervention_id: str, user=Depends(get_current_user)):
    result = await db.interventions.update_one(
        {"id": intervention_id, "user_id": user["user_id"]},
        {"$set": {"status": "planned", "confirmed_at": None, "confirmation_email_id": None}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Intervento non trovato")
    return {"ok": True}


@api_router.delete("/interventions/{intervention_id}")
async def delete_intervention(intervention_id: str, user=Depends(get_current_user)):
    await db.interventions.delete_one({"id": intervention_id, "user_id": user["user_id"]})
    return {"ok": True}


@api_router.delete("/interventions/contract/{contract_id}")
async def delete_by_contract(contract_id: str, user=Depends(get_current_user)):
    await db.interventions.delete_many({"contract_id": contract_id, "user_id": user["user_id"]})
    await db.contracts.update_one({"id": contract_id, "user_id": user["user_id"]}, {"$set": {"status": "active"}})
    return {"ok": True}


# =============== MANUAL / EXTRA EVENTS (appuntamenti non previsti) ===============

class ManualEventIn(BaseModel):
    date: str  # YYYY-MM-DD
    title: str
    client_id: Optional[str] = None
    notes: Optional[str] = ""
    slot: str = "full"  # full | morning | afternoon
    all_day: bool = True
    start_time: Optional[str] = None  # HH:MM
    end_time: Optional[str] = None


class ManualEvent(ManualEventIn):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@api_router.get("/manual-events")
async def list_manual_events(user=Depends(get_current_user)):
    docs = await db.manual_events.find({"user_id": user["user_id"]}, {"_id": 0}).sort("date", 1).to_list(1000)
    return docs


@api_router.post("/manual-events", response_model=ManualEvent)
async def create_manual_event(payload: ManualEventIn, user=Depends(get_current_user)):
    ev = ManualEvent(user_id=user["user_id"], **payload.model_dump())
    await db.manual_events.insert_one(ev.model_dump())
    return ev


@api_router.delete("/manual-events/{event_id}")
async def delete_manual_event(event_id: str, user=Depends(get_current_user)):
    await db.manual_events.delete_one({"id": event_id, "user_id": user["user_id"]})
    return {"ok": True}


# =============== RESCHEDULE ALL ===============

@api_router.post("/planning/reschedule")
async def reschedule_all(payload: PlanRequest, user=Depends(get_current_user)):
    """Deletes all currently planned interventions and regenerates from scratch,
    respecting manual events (which block their dates)."""
    await db.interventions.delete_many({"user_id": user["user_id"]})
    await db.contracts.update_many(
        {"user_id": user["user_id"], "status": "planned"},
        {"$set": {"status": "active"}},
    )
    return await generate_planning(payload, user)


# =============== CALENDAR EXPORT (.ics) ===============

@api_router.get("/calendar/export.ics")
async def export_ics(user_id: str, token: str):
    """Public-token endpoint to allow Google Calendar to subscribe via URL.
    Also usable for one-shot download. Token = session_token for validation."""
    sess = await db.user_sessions.find_one({"session_token": token, "user_id": user_id}, {"_id": 0})
    if not sess:
        raise HTTPException(401, "Invalid token")
    ivs = await db.interventions.find({"user_id": user_id}, {"_id": 0}).to_list(2000)
    manual = await db.manual_events.find({"user_id": user_id}, {"_id": 0}).to_list(2000)
    # Bulk fetch contracts + clients in 2 queries (avoid N+1)
    contract_ids = list({iv["contract_id"] for iv in ivs})
    client_ids = list({iv["client_id"] for iv in ivs} | {ev["client_id"] for ev in manual if ev.get("client_id")})
    contracts_map = {}
    clients_map = {}
    if contract_ids:
        c_docs = await db.contracts.find({"id": {"$in": contract_ids}}, {"_id": 0}).to_list(1000)
        contracts_map = {c["id"]: c for c in c_docs}
    if client_ids:
        cl_docs = await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0}).to_list(1000)
        clients_map = {cl["id"]: cl for cl in cl_docs}
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PlanOp//IT//",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:PlanOp - Interventi"]
    for ev in manual:
        cli = clients_map.get(ev.get("client_id")) if ev.get("client_id") else None
        summary = ev.get("title", "Appuntamento")
        loc = f"{cli.get('address','')}, {cli.get('city','')}" if cli else ""
        desc = (ev.get("notes") or "").replace("\n", "\\n")
        d = ev["date"].replace("-", "")
        slot = ev.get("slot", "full")
        if slot == "morning":
            dtstart = f"{d}T090000"; dtend = f"{d}T133000"; slot_label = "Mattina"
        elif slot == "afternoon":
            dtstart = f"{d}T143000"; dtend = f"{d}T180000"; slot_label = "Pomeriggio"
        else:
            dtstart = f"{d}T090000"; dtend = f"{d}T180000"; slot_label = "Giornata intera"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev['id']}@planop-manual",
            f"DTSTART;TZID=Europe/Rome:{dtstart}",
            f"DTEND;TZID=Europe/Rome:{dtend}",
            f"SUMMARY:[Extra {slot_label}] {summary}",
            f"LOCATION:{loc}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ]
    for iv in ivs:
        c = contracts_map.get(iv["contract_id"], {})
        cli = clients_map.get(iv["client_id"], {})
        d = iv["date"].replace("-", "")
        slot = iv.get("slot", "full")
        # Slot times: morning 09:00-13:30, afternoon 14:30-18:00, full 09:00-18:00
        if slot == "morning":
            dtstart = f"{d}T090000"; dtend = f"{d}T133000"
            slot_label = "Mattina"
        elif slot == "afternoon":
            dtstart = f"{d}T143000"; dtend = f"{d}T180000"
            slot_label = "Pomeriggio"
        else:
            dtstart = f"{d}T090000"; dtend = f"{d}T180000"
            slot_label = "Giornata intera"
        summary = f"[{slot_label}] {c.get('title', 'Intervento')} @ {cli.get('name', '')}"
        loc = f"{cli.get('address','')}, {cli.get('city','')}"
        desc = f"Contratto: {c.get('title','')}\\nGiorno {iv['day_index']}/{c.get('total_days','')}\\nSlot: {slot_label}\\nReferente: {cli.get('contact_name','')} {cli.get('phone','')}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{iv['id']}@planop",
            f"DTSTART;TZID=Europe/Rome:{dtstart}",
            f"DTEND;TZID=Europe/Rome:{dtend}",
            f"SUMMARY:{summary}",
            f"LOCATION:{loc}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines)
    return Response(content=body, media_type="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=planop.ics"})


@api_router.get("/calendar/subscribe-url")
async def subscribe_url(request: Request, user=Depends(get_current_user)):
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    # Honor proxy scheme (k8s ingress sets X-Forwarded-Proto=https)
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    base = f"{scheme}://{host}"
    url = f"{base}/api/calendar/export.ics?user_id={user['user_id']}&token={token}"
    return {"url": url}


# =============== INVOICE ===============

class InvoiceReq(BaseModel):
    contract_id: str
    invoice_number: str
    invoice_date: Optional[str] = None
    vat_rate: float = 22.0  # IVA %
    withholding_rate: float = 0.0  # Ritenuta d'acconto %
    regime_forfettario: bool = False
    marca_da_bollo: bool = False
    issuer_name: str = ""
    issuer_vat: str = ""
    issuer_address: str = ""


@api_router.post("/invoices/generate")
async def generate_invoice(payload: InvoiceReq, user=Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": payload.contract_id, "user_id": user["user_id"]}, {"_id": 0})
    if not contract:
        raise HTTPException(404, "Contract not found")
    client_doc = await db.clients.find_one({"id": contract["client_id"]}, {"_id": 0})
    ivs = await db.interventions.find({"contract_id": payload.contract_id}, {"_id": 0}).to_list(1000)
    worked_days = len(ivs) or contract["total_days"]
    daily = contract.get("daily_rate", 0) or 0
    imponibile = daily * worked_days

    if payload.regime_forfettario:
        iva = 0.0
        ritenuta = 0.0
    else:
        iva = imponibile * payload.vat_rate / 100
        ritenuta = imponibile * payload.withholding_rate / 100
    marca = 2.0 if payload.marca_da_bollo else 0.0
    totale = imponibile + iva - ritenuta + marca

    buf = io.BytesIO()
    pdf = pdfcanvas.Canvas(buf, pagesize=A4)
    W, H = A4
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(20*mm, H - 25*mm, "FATTURA")
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.drawRightString(W - 20*mm, H - 25*mm, f"N. {payload.invoice_number}")
    pdf.drawRightString(W - 20*mm, H - 30*mm, f"Data: {payload.invoice_date or date.today().isoformat()}")

    y = H - 45*mm
    pdf.setFillColor(colors.HexColor("#1E40AF"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20*mm, y, "Emittente")
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(20*mm, y - 6*mm, payload.issuer_name or user.get("name", ""))
    pdf.drawString(20*mm, y - 11*mm, f"P.IVA: {payload.issuer_vat}")
    pdf.drawString(20*mm, y - 16*mm, payload.issuer_address)

    pdf.setFillColor(colors.HexColor("#1E40AF"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(110*mm, y, "Cliente")
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(110*mm, y - 6*mm, client_doc.get("name", "") if client_doc else "")
    pdf.drawString(110*mm, y - 11*mm, client_doc.get("address", "") if client_doc else "")
    pdf.drawString(110*mm, y - 16*mm, client_doc.get("city", "") if client_doc else "")

    y = y - 35*mm
    pdf.setFillColor(colors.HexColor("#E2E8F0"))
    pdf.rect(20*mm, y - 2*mm, W - 40*mm, 8*mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(22*mm, y + 1*mm, "Descrizione")
    pdf.drawString(110*mm, y + 1*mm, "Giorni")
    pdf.drawString(135*mm, y + 1*mm, "Tariffa")
    pdf.drawRightString(W - 22*mm, y + 1*mm, "Importo")

    y -= 12*mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(22*mm, y, contract["title"][:60])
    pdf.drawString(110*mm, y, str(worked_days))
    pdf.drawString(135*mm, y, f"EUR {daily:.2f}")
    pdf.drawRightString(W - 22*mm, y, f"EUR {imponibile:.2f}")

    y -= 20*mm
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(W - 60*mm, y, "Imponibile:")
    pdf.drawRightString(W - 22*mm, y, f"EUR {imponibile:.2f}")
    if not payload.regime_forfettario:
        y -= 6*mm
        pdf.drawRightString(W - 60*mm, y, f"IVA {payload.vat_rate:.0f}%:")
        pdf.drawRightString(W - 22*mm, y, f"EUR {iva:.2f}")
        if payload.withholding_rate:
            y -= 6*mm
            pdf.drawRightString(W - 60*mm, y, f"Ritenuta d'acconto {payload.withholding_rate:.0f}%:")
            pdf.drawRightString(W - 22*mm, y, f"-EUR {ritenuta:.2f}")
    if payload.marca_da_bollo:
        y -= 6*mm
        pdf.drawRightString(W - 60*mm, y, "Marca da bollo:")
        pdf.drawRightString(W - 22*mm, y, f"EUR {marca:.2f}")
    y -= 10*mm
    pdf.setFillColor(colors.HexColor("#1E40AF"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(W - 60*mm, y, "TOTALE:")
    pdf.drawRightString(W - 22*mm, y, f"EUR {totale:.2f}")

    if payload.regime_forfettario:
        y -= 15*mm
        pdf.setFillColor(colors.HexColor("#64748B"))
        pdf.setFont("Helvetica-Oblique", 8)
        pdf.drawString(20*mm, y, "Operazione senza applicazione dell'IVA ai sensi dell'art. 1, commi 54-89, L. 190/2014 - Regime forfettario.")

    pdf.showPage()
    pdf.save()
    buf.seek(0)
    await db.contracts.update_one({"id": payload.contract_id}, {"$set": {"status": "invoiced"}})
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=fattura-{payload.invoice_number}.pdf"})


# =============== DASHBOARD ===============

@api_router.get("/dashboard/stats")
async def stats(user=Depends(get_current_user)):
    contracts = await db.contracts.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    ivs = await db.interventions.find(
        {"user_id": user["user_id"]}, {"_id": 0, "id": 1, "date": 1, "contract_id": 1, "day_index": 1}
    ).to_list(2000)
    clients = await db.clients.count_documents({"user_id": user["user_id"]})
    active = sum(1 for c in contracts if c["status"] in ("active", "planned"))
    total_days = sum(c["total_days"] for c in contracts)
    planned = len(ivs)
    upcoming = sorted([iv for iv in ivs if iv["date"] >= date.today().isoformat()], key=lambda x: x["date"])[:5]
    revenue = sum(c.get("daily_rate", 0) * c.get("total_days", 0) for c in contracts if c["status"] in ("active", "planned", "completed", "invoiced"))
    return {
        "active_contracts": active,
        "total_contracts": len(contracts),
        "clients_count": clients,
        "interventions_planned": planned,
        "total_workdays": total_days,
        "upcoming": upcoming,
        "projected_revenue": revenue,
    }


@api_router.get("/")
async def root():
    return {"app": "PlanOp", "status": "ok"}


# =============== CLAUDE AI (Haiku 4.5) ===============

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def _make_chat(session_id: str, system: str) -> LlmChat:
    return LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system,
    ).with_model("anthropic", CLAUDE_MODEL)


class AnalyzeContractIn(BaseModel):
    text: str


@api_router.post("/ai/analyze-contract")
async def analyze_contract(payload: AnalyzeContractIn, user=Depends(get_current_user)):
    return await _analyze_text(payload.text, user)


@api_router.post("/ai/analyze-contract-pdf")
async def analyze_contract_pdf(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload a signed contract PDF -> extract text -> analyze with Claude."""
    if not (file.filename or "").lower().endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(400, "Il file deve essere un PDF")
    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "PDF troppo grande (max 15MB)")
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages_text = []
        for p in reader.pages[:30]:  # first 30 pages to bound tokens
            try:
                pages_text.append(p.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(pages_text).strip()
    except Exception as e:
        raise HTTPException(422, f"Impossibile leggere il PDF: {e}")
    if len(text) < 40:
        raise HTTPException(422, "Il PDF sembra vuoto o scansionato (nessun testo estraibile). Prova a incollare il testo manualmente.")
    # Cap length to keep prompt cheap
    if len(text) > 30000:
        text = text[:30000]
    result = await _analyze_text(text, user)
    result["pages"] = len(reader.pages)
    result["chars_extracted"] = len(text)
    return result


async def _analyze_text(text: str, user):
    """Extract structured contract fields from raw contract text using Claude Haiku 4.5."""
    sys_msg = (
        "Sei un assistente italiano che estrae dati strutturati da contratti di consulenza. "
        "Restituisci SOLO un oggetto JSON valido con questi campi: "
        "{\"client_name\": string, \"city\": string, \"address\": string, "
        "\"contact_name\": string, \"phone\": string, \"email\": string, "
        "\"title\": string (titolo/oggetto attività), "
        "\"total_days\": number (numero giornate previste, ammette decimali es. 3.5), "
        "\"daily_rate\": number (tariffa giornaliera EUR, 0 se non specificata), "
        "\"intervention_type\": string (es. consulenza/formazione/audit), "
        "\"priority\": string (\"high\"|\"medium\"|\"low\", default medium), "
        "\"start_date\": string (YYYY-MM-DD o \"\"), "
        "\"deadline\": string (YYYY-MM-DD o \"\"), "
        "\"signed_date\": string (YYYY-MM-DD o \"\"), "
        "\"notes\": string (riassunto breve)}. "
        "Se un campo non è presente nel testo, usa stringa vuota o 0. NON aggiungere testo fuori dal JSON."
    )
    chat = _make_chat(f"analyze-{user['user_id']}-{uuid.uuid4().hex[:6]}", sys_msg)
    resp = await chat.send_message(UserMessage(text=f"Analizza il seguente contratto ed estrai i dati:\n\n{text}"))
    raw = resp if isinstance(resp, str) else str(resp)
    # Strip code fences if present
    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
        txt = txt.strip()
    # Find outermost JSON braces
    start = txt.find("{")
    end = txt.rfind("}")
    if start >= 0 and end > start:
        txt = txt[start:end+1]
    try:
        data = _json.loads(txt)
    except Exception:
        raise HTTPException(422, f"AI response was not valid JSON: {raw[:200]}")
    return {"extracted": data, "model": CLAUDE_MODEL}


class ChatIn(BaseModel):
    message: str
    session_id: Optional[str] = None


@api_router.post("/ai/planning-chat")
async def planning_chat(payload: ChatIn, user=Depends(get_current_user)):
    """Conversational planning assistant. Loads current contracts/clients/interventions
    as context so suggestions are grounded in real data."""
    session_id = payload.session_id or f"plan-{user['user_id']}"
    # Load context
    contracts = await db.contracts.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    clients = await db.clients.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    ivs = await db.interventions.find(
        {"user_id": user["user_id"]}, {"_id": 0, "contract_id": 1, "date": 1}
    ).to_list(1000)
    manual = await db.manual_events.find(
        {"user_id": user["user_id"]}, {"_id": 0, "date": 1, "title": 1}
    ).to_list(500)

    context = {
        "today": date.today().isoformat(),
        "clients": [{"id": c["id"], "name": c["name"], "city": c.get("city", "")} for c in clients],
        "contracts": [{"id": c["id"], "title": c["title"], "client_id": c["client_id"],
                       "total_days": c["total_days"], "priority": c["priority"],
                       "deadline": c.get("deadline"), "status": c["status"]} for c in contracts],
        "interventions": [{"contract_id": iv["contract_id"], "date": iv["date"]} for iv in ivs],
        "manual_events": [{"date": e["date"], "title": e["title"]} for e in manual],
    }
    sys_msg = (
        "Sei l'assistente italiano di pianificazione di PlanOp. "
        "Aiuti un consulente a organizzare gli interventi presso i clienti. "
        "Rispondi in italiano, in modo conciso, con eventuali suggerimenti di date/priorità. "
        "Usa il seguente contesto reale dell'utente in JSON per rispondere:\n\n"
        f"{_json.dumps(context, ensure_ascii=False)}"
    )
    # Persist history
    history_key = f"{user['user_id']}:{session_id}"
    await db.ai_messages.insert_one({
        "user_id": user["user_id"], "session_id": session_id,
        "role": "user", "content": payload.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    chat = _make_chat(history_key, sys_msg)
    resp = await chat.send_message(UserMessage(text=payload.message))
    reply = resp if isinstance(resp, str) else str(resp)
    await db.ai_messages.insert_one({
        "user_id": user["user_id"], "session_id": session_id,
        "role": "assistant", "content": reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"reply": reply, "session_id": session_id}


@api_router.get("/ai/chat-history")
async def chat_history(session_id: str, user=Depends(get_current_user)):
    docs = await db.ai_messages.find(
        {"user_id": user["user_id"], "session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return docs


class DraftIn(BaseModel):
    kind: str = "email"  # "email" or "note"
    contract_id: Optional[str] = None
    client_id: Optional[str] = None
    intervention_date: Optional[str] = None
    extra_prompt: Optional[str] = ""


@api_router.post("/ai/draft")
async def ai_draft(payload: DraftIn, user=Depends(get_current_user)):
    """Generate draft email/note for a client or intervention."""
    ctx = {}
    if payload.contract_id:
        c = await db.contracts.find_one({"id": payload.contract_id, "user_id": user["user_id"]}, {"_id": 0})
        if c: ctx["contract"] = c
    if payload.client_id:
        cli = await db.clients.find_one({"id": payload.client_id, "user_id": user["user_id"]}, {"_id": 0})
        if cli: ctx["client"] = cli
    if payload.intervention_date:
        ctx["intervention_date"] = payload.intervention_date

    if payload.kind == "email":
        sys_msg = (
            "Sei un assistente italiano che scrive email professionali brevi e cordiali "
            "da consulenti freelance ai loro clienti. Includi oggetto (prima riga: 'Oggetto: ...'), "
            "corpo con saluto, informazioni chiave, chiusura formale. Firma con [Il tuo nome]."
        )
    else:
        sys_msg = "Sei un assistente italiano che scrive brevi note operative interne di 3-6 righe."

    prompt = f"Contesto: {_json.dumps(ctx, ensure_ascii=False)}\n\nIstruzioni aggiuntive: {payload.extra_prompt or 'nessuna'}"
    chat = _make_chat(f"draft-{user['user_id']}-{uuid.uuid4().hex[:6]}", sys_msg)
    resp = await chat.send_message(UserMessage(text=prompt))
    return {"draft": resp if isinstance(resp, str) else str(resp), "model": CLAUDE_MODEL}


# =============== EMAIL (Emergent-managed Resend) ===============

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "PlanOp")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = (
    "reply with your password", "reply with the code", "send your password", "cvv",
    "send us your password", "enter your password below", "confirm your card number",
    "your full card number", "seed phrase", "recovery phrase", "verify your card",
    "social security number", "confirm your bank details",
)
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> Optional[str]:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as hc:
            resp = await hc.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail="Failed to send email")
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


def _reminder_html(client_name: str, intervention_date: str, contract_title: str,
                   day_index: int, total_days: int, address: str) -> str:
    safe_client = escape(client_name)
    safe_title = escape(contract_title)
    safe_date = escape(intervention_date)
    safe_addr = escape(address or "")
    safe_from = escape(EMAIL_FROM_NAME)
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0F172A">'
        f'<h2 style="margin:0 0 12px 0;color:#1E40AF">Promemoria intervento</h2>'
        f'<p>Gentile {safe_client},</p>'
        f'<p>ti ricordiamo che <strong>domani {safe_date}</strong> è previsto il nostro intervento presso la vostra sede'
        f' ({safe_addr}) nell&#39;ambito del contratto <strong>{safe_title}</strong>.</p>'
        f'<p style="background:#F1F5F9;padding:12px;border-radius:6px;margin:16px 0">'
        f'Giornata <strong>{day_index}</strong> di <strong>{total_days}</strong>.</p>'
        f'<p>Per qualsiasi variazione, risponda pure a questa email.</p>'
        f'<p style="margin-top:24px">Cordiali saluti,<br>{safe_from}</p>'
        f'<hr style="border:none;border-top:1px solid #E2E8F0;margin:20px 0">'
        f'<p style="font-size:11px;color:#64748B">Email inviata da {safe_from}. Non chiediamo mai password, codici o dati di pagamento via email.</p>'
        f'</td></tr></table>'
    )


class ReminderPrefsIn(BaseModel):
    enabled: bool = True
    send_to_client_email: bool = True
    cc_owner: bool = False
    owner_email: Optional[str] = None


@api_router.get("/reminders/prefs")
async def get_prefs(user=Depends(get_current_user)):
    doc = await db.reminder_prefs.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        return {"enabled": True, "send_to_client_email": True, "cc_owner": False, "owner_email": user.get("email", "")}
    return doc


@api_router.put("/reminders/prefs")
async def set_prefs(payload: ReminderPrefsIn, user=Depends(get_current_user)):
    data = payload.model_dump()
    data["user_id"] = user["user_id"]
    await db.reminder_prefs.update_one(
        {"user_id": user["user_id"]}, {"$set": data}, upsert=True,
    )
    return {"ok": True}


@api_router.post("/reminders/test")
async def test_reminder(user=Depends(get_current_user)):
    """Send a test reminder email to the owner (signed-in user)."""
    if not EMAIL_KEY:
        raise HTTPException(500, "Email non configurata")
    html = _reminder_html(
        client_name=user.get("name", "Cliente"),
        intervention_date=(date.today() + timedelta(days=1)).isoformat(),
        contract_title="Contratto di test PlanOp",
        day_index=1, total_days=3, address="Via Roma 1, Milano",
    )
    mid = await send_email(to=user["email"], subject="Promemoria intervento (test)", html=html)
    return {"ok": True, "email_id": mid}


class ReminderCronIn(BaseModel):
    event: Optional[str] = None
    schedule_id: Optional[str] = None
    run_id: Optional[str] = None
    dispatch_time: Optional[str] = None
    job_id: Optional[str] = None
    data: Optional[dict] = None


async def _send_daily_reminders(run_id: str):
    """Background: find tomorrow's interventions and send emails per user prefs.
    Idempotent via run_id + intervention_id."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    # Only send reminders for CONFIRMED interventions
    ivs = await db.interventions.find(
        {"date": tomorrow, "status": "confirmed"}, {"_id": 0}
    ).to_list(2000)
    if not ivs:
        return
    # Bulk fetch clients, contracts, prefs
    contract_ids = list({iv["contract_id"] for iv in ivs})
    client_ids = list({iv["client_id"] for iv in ivs})
    user_ids = list({iv["user_id"] for iv in ivs})
    contracts = {c["id"]: c for c in await db.contracts.find({"id": {"$in": contract_ids}}, {"_id": 0}).to_list(2000)}
    clients = {c["id"]: c for c in await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0}).to_list(2000)}
    prefs_map = {p["user_id"]: p for p in await db.reminder_prefs.find({"user_id": {"$in": user_ids}}, {"_id": 0}).to_list(2000)}

    for iv in ivs:
        prefs = prefs_map.get(iv["user_id"], {"enabled": True, "send_to_client_email": True,
                                              "cc_owner": False, "owner_email": None})
        if not prefs.get("enabled", True):
            continue
        # Idempotency: skip if we already logged this reminder
        already = await db.reminder_log.find_one(
            {"intervention_id": iv["id"], "date": tomorrow}, {"_id": 0}
        )
        if already:
            continue
        cli = clients.get(iv["client_id"])
        c = contracts.get(iv["contract_id"])
        if not cli or not c:
            continue
        recipient = cli.get("email") if prefs.get("send_to_client_email", True) else None
        if not recipient and prefs.get("cc_owner"):
            recipient = prefs.get("owner_email")
        if not recipient:
            continue
        html = _reminder_html(
            client_name=cli.get("name", "Cliente"),
            intervention_date=tomorrow,
            contract_title=c.get("title", "Attivita"),
            day_index=iv.get("day_index", 1),
            total_days=c.get("total_days", 0),
            address=f"{cli.get('address','')} {cli.get('city','')}".strip(),
        )
        try:
            eid = await send_email(to=recipient, subject=f"Promemoria intervento di domani ({tomorrow})", html=html)
            await db.reminder_log.insert_one({
                "intervention_id": iv["id"],
                "user_id": iv["user_id"],
                "date": tomorrow,
                "recipient": recipient,
                "email_id": eid,
                "run_id": run_id,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.error(f"Reminder send failed for {iv['id']}: {e}")


@api_router.post("/cron/reminders")
async def cron_reminders(request: Request, payload: ReminderCronIn, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not WEBHOOK_CRON_SECRET or not _secrets.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("X-Webhook-Id") or (payload.run_id or uuid.uuid4().hex)
    # Idempotency guard
    existing = await db.cron_runs.find_one({"run_id": run_id}, {"_id": 0})
    if existing:
        return {"ok": True, "duplicate": True}
    await db.cron_runs.insert_one({
        "run_id": run_id,
        "schedule_id": payload.schedule_id or "reminder-daily",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    background_tasks.add_task(_send_daily_reminders, run_id)
    return {"ok": True, "run_id": run_id}


@api_router.get("/reminders/log")
async def reminder_log(user=Depends(get_current_user)):
    docs = await db.reminder_log.find({"user_id": user["user_id"]}, {"_id": 0}).sort("sent_at", -1).to_list(200)
    return docs


# =============== ISSUER SETTINGS (dati emittente per FatturaPA) ===============

class IssuerSettingsIn(BaseModel):
    denominazione: str = ""  # Ragione sociale o Nome Cognome
    nome: str = ""
    cognome: str = ""
    piva: str = ""
    codice_fiscale: str = ""
    regime_fiscale: str = "RF01"  # RF01 ordinario, RF19 forfettario
    codice_ateco: str = ""
    address: str = ""
    cap: str = ""
    city: str = ""
    provincia: str = ""
    nazione: str = "IT"
    telefono: str = ""
    email: str = ""
    id_paese_trasmittente: str = "IT"
    id_codice_trasmittente: str = ""  # solitamente P.IVA del trasmittente


@api_router.get("/settings/issuer")
async def get_issuer(user=Depends(get_current_user)):
    doc = await db.issuer_settings.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        return IssuerSettingsIn().model_dump()
    return doc


@api_router.put("/settings/issuer")
async def set_issuer(payload: IssuerSettingsIn, user=Depends(get_current_user)):
    data = payload.model_dump()
    if not data.get("id_codice_trasmittente"):
        data["id_codice_trasmittente"] = data.get("piva") or data.get("codice_fiscale")
    data["user_id"] = user["user_id"]
    await db.issuer_settings.update_one(
        {"user_id": user["user_id"]}, {"$set": data}, upsert=True,
    )
    return {"ok": True}


# =============== INVOICEX EXPORT ===============

def _csv_escape(v) -> str:
    s = "" if v is None else str(v)
    if any(ch in s for ch in [",", '"', "\n", "\r", ";"]):
        s = '"' + s.replace('"', '""') + '"'
    return s


@api_router.get("/export/invoicex/clients.csv")
async def export_invoicex_clients(user=Depends(get_current_user)):
    """Export anagrafica clienti in CSV importabile in Invoicex (import/export -> import CSV)."""
    docs = await db.clients.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(5000)
    headers = [
        "codice_cliente", "ragione_sociale", "indirizzo", "cap", "citta", "provincia", "nazione",
        "partita_iva", "codice_fiscale", "codice_destinatario", "pec",
        "telefono", "email", "referente", "note",
    ]
    lines = [";".join(headers)]
    for c in docs:
        row = [
            c.get("codice_cliente", ""),
            c.get("name", ""), c.get("address", ""), c.get("cap", ""), c.get("city", ""),
            c.get("provincia", ""), "IT",
            c.get("piva", ""), c.get("codice_fiscale", ""),
            c.get("codice_destinatario", ""), c.get("pec", ""),
            c.get("phone", ""), c.get("email", ""), c.get("contact_name", ""),
            (c.get("notes") or "").replace("\n", " "),
        ]
        lines.append(";".join(_csv_escape(x) for x in row))
    body = "\ufeff" + "\r\n".join(lines)  # BOM for Excel/Invoicex UTF-8
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=clienti-invoicex.csv"},
    )


# =============== CSV IMPORT ===============

CLIENTS_TEMPLATE_HEADERS = [
    "codice_cliente", "ragione_sociale", "indirizzo", "cap", "citta", "provincia",
    "partita_iva", "codice_fiscale", "codice_destinatario", "pec",
    "telefono", "email", "referente", "note",
]

CONTRACTS_TEMPLATE_HEADERS = [
    "numero_preventivo", "cliente_ragione_sociale", "cliente_partita_iva", "titolo",
    "giorni_totali", "tariffa_giornaliera", "tipologia",
    "priorita", "data_firma", "data_inizio", "scadenza", "note",
]


@api_router.get("/import/clients-template.csv")
async def clients_template(user=Depends(get_current_user)):
    example_rows = [
        ["C001", "ACME SRL", "Via Roma 10", "20100", "Milano", "MI",
         "12345678901", "", "USAL8PV", "acme@pec.it",
         "0212345", "info@acme.it", "Mario Rossi", "Cliente storico"],
        ["C002", "Bianchi & Figli SNC", "Corso Italia 45", "10121", "Torino", "TO",
         "", "BNCLGI80A01L219X", "0000000", "bianchi@pec.it",
         "0117654321", "bianchi@example.it", "Luigi Bianchi", ""],
    ]
    lines = [";".join(CLIENTS_TEMPLATE_HEADERS)]
    for row in example_rows:
        lines.append(";".join(_csv_escape(x) for x in row))
    body = "\ufeff" + "\r\n".join(lines)
    return Response(
        content=body, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=modello-clienti.csv"},
    )


@api_router.get("/import/contracts-template.csv")
async def contracts_template(user=Depends(get_current_user)):
    example_rows = [
        ["PREV-2026-001", "ACME SRL", "12345678901", "Migrazione ERP + formazione",
         "8", "600", "consulenza",
         "high", "2026-02-15", "2026-03-01", "2026-05-30", "Priorità massima"],
        ["PREV-2026-002", "Bianchi & Figli SNC", "", "Audit sistemi informativi",
         "3", "500", "audit",
         "medium", "2026-02-20", "", "2026-04-30", ""],
    ]
    lines = [";".join(CONTRACTS_TEMPLATE_HEADERS)]
    for row in example_rows:
        lines.append(";".join(_csv_escape(x) for x in row))
    body = "\ufeff" + "\r\n".join(lines)
    return Response(
        content=body, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=modello-preventivi.csv"},
    )


def _read_csv(raw: bytes) -> tuple:
    """Return (headers, rows). Detect ; or , separator. Strip BOM."""
    text = raw.decode("utf-8-sig", errors="replace")
    # Detect separator on first line
    first_line = text.splitlines()[0] if text else ""
    sep = ";" if first_line.count(";") >= first_line.count(",") else ","
    import csv as _csv
    reader = _csv.reader(io.StringIO(text), delimiter=sep, quotechar='"')
    rows = list(reader)
    if not rows:
        return [], []
    headers = [h.strip().lower() for h in rows[0]]
    return headers, rows[1:]


def _row_dict(headers: list, row: list) -> dict:
    d = {}
    for i, h in enumerate(headers):
        d[h] = (row[i].strip() if i < len(row) else "")
    return d


@api_router.post("/import/clients")
async def import_clients(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Il file deve essere un CSV")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV troppo grande (max 5MB)")
    headers, rows = _read_csv(raw)
    if not headers:
        raise HTTPException(422, "CSV vuoto")

    imported = 0
    updated = 0
    errors = []
    for idx, row in enumerate(rows, start=2):  # start=2 accounts for header row
        r = _row_dict(headers, row)
        name = r.get("ragione_sociale") or r.get("nome") or r.get("name") or ""
        if not name:
            continue
        address = r.get("indirizzo") or r.get("address") or ""
        if not address:
            errors.append(f"Riga {idx}: '{name}' senza indirizzo, saltato")
            continue
        piva = r.get("partita_iva") or r.get("piva") or ""
        codice_cli = r.get("codice_cliente") or r.get("codice") or ""
        # match existing by codice_cliente, piva or name
        existing = None
        if codice_cli:
            existing = await db.clients.find_one({"user_id": user["user_id"], "codice_cliente": codice_cli}, {"_id": 0})
        if not existing and piva:
            existing = await db.clients.find_one({"user_id": user["user_id"], "piva": piva}, {"_id": 0})
        if not existing:
            existing = await db.clients.find_one(
                {"user_id": user["user_id"], "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                {"_id": 0},
            )
        payload = {
            "codice_cliente": codice_cli,
            "name": name,
            "address": address,
            "city": r.get("citta") or r.get("city") or "",
            "cap": r.get("cap") or "",
            "provincia": (r.get("provincia") or "").upper()[:2],
            "contact_name": r.get("referente") or r.get("contact_name") or "",
            "phone": r.get("telefono") or r.get("phone") or "",
            "email": r.get("email") or "",
            "piva": piva,
            "codice_fiscale": (r.get("codice_fiscale") or r.get("cf") or "").upper(),
            "codice_destinatario": (r.get("codice_destinatario") or r.get("sdi") or "").upper(),
            "pec": r.get("pec") or "",
            "notes": r.get("note") or r.get("notes") or "",
        }
        coords = await geocode(payload["address"], payload["city"])
        if coords:
            payload["lat"] = coords["lat"]
            payload["lng"] = coords["lng"]
        if existing:
            await db.clients.update_one({"id": existing["id"]}, {"$set": payload})
            updated += 1
        else:
            doc = {"id": uuid.uuid4().hex, "user_id": user["user_id"],
                   "created_at": datetime.now(timezone.utc).isoformat(), **payload}
            await db.clients.insert_one(doc)
            imported += 1
    return {"imported": imported, "updated": updated, "errors": errors[:20], "rows_total": len(rows)}


@api_router.post("/import/contracts")
async def import_contracts(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Il file deve essere un CSV")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV troppo grande (max 5MB)")
    headers, rows = _read_csv(raw)
    if not headers:
        raise HTTPException(422, "CSV vuoto")

    imported = 0
    errors = []
    for idx, row in enumerate(rows, start=2):
        r = _row_dict(headers, row)
        client_name = r.get("cliente_ragione_sociale") or r.get("cliente") or r.get("client_name") or ""
        client_piva = r.get("cliente_partita_iva") or r.get("cliente_piva") or ""
        title = r.get("titolo") or r.get("title") or ""
        days_raw = r.get("giorni_totali") or r.get("giorni") or r.get("total_days") or ""
        if not title or not days_raw:
            errors.append(f"Riga {idx}: titolo o giorni_totali mancante, saltata")
            continue
        try:
            total_days = int(float(days_raw.replace(",", ".")))
        except Exception:
            errors.append(f"Riga {idx}: giorni_totali non numerico '{days_raw}'")
            continue
        # Match client
        client = None
        if client_piva:
            client = await db.clients.find_one({"user_id": user["user_id"], "piva": client_piva}, {"_id": 0})
        if not client and client_name:
            client = await db.clients.find_one(
                {"user_id": user["user_id"], "name": {"$regex": f"^{re.escape(client_name)}$", "$options": "i"}},
                {"_id": 0},
            )
        if not client:
            errors.append(f"Riga {idx}: cliente '{client_name}' non trovato in anagrafica, saltata")
            continue

        rate_raw = (r.get("tariffa_giornaliera") or r.get("tariffa") or "0").replace(",", ".")
        try:
            daily_rate = float(rate_raw)
        except Exception:
            daily_rate = 0.0
        priority = (r.get("priorita") or r.get("priority") or "medium").lower()
        if priority not in ("high", "medium", "low"):
            priority = "medium"

        def _norm_date(s: str) -> Optional[str]:
            s = (s or "").strip()
            if not s:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(s, fmt).date().isoformat()
                except Exception:
                    continue
            return None

        doc = {
            "id": uuid.uuid4().hex,
            "user_id": user["user_id"],
            "numero_preventivo": r.get("numero_preventivo") or r.get("numero") or "",
            "client_id": client["id"],
            "title": title,
            "total_days": total_days,
            "daily_rate": daily_rate,
            "intervention_type": r.get("tipologia") or r.get("intervention_type") or "consulenza",
            "priority": priority,
            "start_date": _norm_date(r.get("data_inizio") or r.get("start_date") or ""),
            "deadline": _norm_date(r.get("scadenza") or r.get("deadline") or ""),
            "signed_date": _norm_date(r.get("data_firma") or r.get("signed_date") or ""),
            "status": "active",
            "notes": r.get("note") or r.get("notes") or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.contracts.insert_one(doc)
        imported += 1
    return {"imported": imported, "errors": errors[:20], "rows_total": len(rows)}


# =============== ARUBA / FATTURAPA XML IMPORT (bulk anagrafica) ===============

def _xml_text(el, tag: str) -> str:
    if el is None:
        return ""
    for child in el.iter():
        if child.tag.split("}")[-1] == tag:
            return (child.text or "").strip()
    return ""


def _extract_anagrafica_from_xml(raw: bytes) -> list:
    """Parse a FatturaPA XML and extract Cedente + Cessionario as client dicts."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(raw)
    except Exception:
        return []
    results = []
    for role_tag in ("CedentePrestatore", "CessionarioCommittente"):
        for el in root.iter():
            if el.tag.split("}")[-1] == role_tag:
                dati = None
                sede = None
                contatti = None
                for c in el:
                    t = c.tag.split("}")[-1]
                    if t == "DatiAnagrafici":
                        dati = c
                    elif t == "Sede":
                        sede = c
                    elif t == "Contatti":
                        contatti = c
                name = ""
                piva = ""
                cf = ""
                if dati is not None:
                    piva = _xml_text(dati, "IdCodice")
                    cf = _xml_text(dati, "CodiceFiscale")
                    denom = _xml_text(dati, "Denominazione")
                    nome = _xml_text(dati, "Nome")
                    cognome = _xml_text(dati, "Cognome")
                    name = denom or f"{nome} {cognome}".strip()
                if not name and not piva and not cf:
                    continue
                addr = _xml_text(sede, "Indirizzo") if sede is not None else ""
                cap = _xml_text(sede, "CAP") if sede is not None else ""
                citta = _xml_text(sede, "Comune") if sede is not None else ""
                prov = _xml_text(sede, "Provincia") if sede is not None else ""
                phone = _xml_text(contatti, "Telefono") if contatti is not None else ""
                email = _xml_text(contatti, "Email") if contatti is not None else ""
                results.append({
                    "name": name or piva or cf,
                    "address": addr or "N/D",
                    "city": citta, "cap": cap, "provincia": prov,
                    "piva": piva, "codice_fiscale": cf,
                    "phone": phone, "email": email,
                    "codice_destinatario": "", "pec": "",
                    "contact_name": "", "notes": "",
                })
    return results


@api_router.post("/import/fatturapa-xml")
async def import_fatturapa_xml(files: List[UploadFile] = File(...), user=Depends(get_current_user)):
    """Upload FatturaPA XML file(s) from Aruba (or any other provider) - extracts anagrafica.
    Supports .xml. Deduplicates against existing clients by P.IVA/C.F./name."""
    if not files:
        raise HTTPException(400, "Nessun file")
    imported = 0
    updated = 0
    skipped = 0
    errors = []
    seen_ids = set()  # (piva, cf, name) tuples within this batch
    for f in files:
        fname = (f.filename or "").lower()
        if not fname.endswith(".xml"):
            errors.append(f"{f.filename}: non è un XML")
            continue
        raw = await f.read()
        if len(raw) > 5 * 1024 * 1024:
            errors.append(f"{f.filename}: troppo grande (max 5MB)")
            continue
        anags = _extract_anagrafica_from_xml(raw)
        if not anags:
            errors.append(f"{f.filename}: nessuna anagrafica riconosciuta")
            continue
        for a in anags:
            key = (a.get("piva", ""), a.get("codice_fiscale", ""), a.get("name", ""))
            if key in seen_ids:
                continue
            seen_ids.add(key)
            existing = None
            if a.get("piva"):
                existing = await db.clients.find_one(
                    {"user_id": user["user_id"], "piva": a["piva"]}, {"_id": 0})
            if not existing and a.get("codice_fiscale"):
                existing = await db.clients.find_one(
                    {"user_id": user["user_id"], "codice_fiscale": a["codice_fiscale"]}, {"_id": 0})
            if not existing and a.get("name"):
                existing = await db.clients.find_one(
                    {"user_id": user["user_id"], "name": {"$regex": f"^{re.escape(a['name'])}$", "$options": "i"}},
                    {"_id": 0})
            # Skip if it's the issuer (same P.IVA as our own settings)
            issuer = await db.issuer_settings.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
            if a.get("piva") and a["piva"] == issuer.get("piva"):
                skipped += 1
                continue
            if existing:
                # Fill only missing fields, preserve user edits
                patch = {}
                for fld in ("cap", "provincia", "codice_fiscale", "phone", "email"):
                    if not existing.get(fld) and a.get(fld):
                        patch[fld] = a[fld]
                if patch:
                    await db.clients.update_one({"id": existing["id"]}, {"$set": patch})
                    updated += 1
                else:
                    skipped += 1
            else:
                coords = await geocode(a["address"], a.get("city", ""))
                if coords:
                    a["lat"] = coords["lat"]
                    a["lng"] = coords["lng"]
                doc = {"id": uuid.uuid4().hex, "user_id": user["user_id"],
                       "codice_cliente": "",
                       "created_at": datetime.now(timezone.utc).isoformat(), **a}
                await db.clients.insert_one(doc)
                imported += 1
    return {"imported": imported, "updated": updated, "skipped": skipped,
            "errors": errors[:30], "files_total": len(files)}


def _xml_escape(v) -> str:
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


@api_router.get("/export/fatturapa/{contract_id}")
async def export_fatturapa(contract_id: str, invoice_number: str = "", user=Depends(get_current_user)):
    """Generate a FatturaPA v1.2.2 XML (formato SdI privato FPR12) importabile in Invoicex."""
    contract = await db.contracts.find_one({"id": contract_id, "user_id": user["user_id"]}, {"_id": 0})
    if not contract:
        raise HTTPException(404, "Contratto non trovato")
    client = await db.clients.find_one({"id": contract["client_id"]}, {"_id": 0})
    if not client:
        raise HTTPException(400, "Cliente non trovato")
    issuer = await db.issuer_settings.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    if not issuer.get("piva") and not issuer.get("codice_fiscale"):
        raise HTTPException(400, "Configura prima i dati emittente (P.IVA/CF) da Impostazioni")

    ivs = await db.interventions.find({"contract_id": contract_id}, {"_id": 0}).to_list(1000)
    worked_days = len(ivs) or contract["total_days"]
    daily = float(contract.get("daily_rate", 0) or 0)
    imponibile = round(daily * worked_days, 2)
    regime = issuer.get("regime_fiscale", "RF01")
    aliquota = 0.0 if regime == "RF19" else 22.0
    natura = None
    if regime == "RF19":
        natura = "N2.2"  # Op. non soggette
    imposta = round(imponibile * aliquota / 100, 2)
    totale = round(imponibile + imposta, 2)
    inv_num = invoice_number or f"{datetime.now().year}-{contract_id[:6]}"
    inv_date = date.today().isoformat()
    cod_dest = (client.get("codice_destinatario") or "").strip().upper() or "0000000"
    if len(cod_dest) != 7:
        cod_dest = "0000000"

    trasm_piva = _xml_escape(issuer.get("id_codice_trasmittente") or issuer.get("piva") or issuer.get("codice_fiscale"))
    ced_piva = _xml_escape(issuer.get("piva", ""))
    ced_cf = _xml_escape(issuer.get("codice_fiscale", ""))
    ced_den = _xml_escape(issuer.get("denominazione") or f"{issuer.get('nome','')} {issuer.get('cognome','')}".strip())
    ces_den = _xml_escape(client.get("name", ""))
    ces_piva = _xml_escape(client.get("piva", ""))
    ces_cf = _xml_escape(client.get("codice_fiscale", ""))

    # Determine cessionario identification
    if client.get("piva"):
        ces_id_block = (f"<IdFiscaleIVA><IdPaese>IT</IdPaese>"
                        f"<IdCodice>{ces_piva}</IdCodice></IdFiscaleIVA>")
    else:
        ces_id_block = ""
    if client.get("codice_fiscale"):
        ces_cf_block = f"<CodiceFiscale>{ces_cf}</CodiceFiscale>"
    else:
        ces_cf_block = ""

    natura_line = f"<Natura>{natura}</Natura>" if natura else ""
    pec_line = f"<PECDestinatario>{_xml_escape(client.get('pec',''))}</PECDestinatario>" if (cod_dest == "0000000" and client.get("pec")) else ""

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <IdTrasmittente>
        <IdPaese>IT</IdPaese>
        <IdCodice>{trasm_piva}</IdCodice>
      </IdTrasmittente>
      <ProgressivoInvio>{_xml_escape(inv_num)}</ProgressivoInvio>
      <FormatoTrasmissione>FPR12</FormatoTrasmissione>
      <CodiceDestinatario>{cod_dest}</CodiceDestinatario>
      {pec_line}
    </DatiTrasmissione>
    <CedentePrestatore>
      <DatiAnagrafici>
        <IdFiscaleIVA>
          <IdPaese>IT</IdPaese>
          <IdCodice>{ced_piva or ced_cf}</IdCodice>
        </IdFiscaleIVA>
        {f'<CodiceFiscale>{ced_cf}</CodiceFiscale>' if ced_cf else ''}
        <Anagrafica><Denominazione>{ced_den}</Denominazione></Anagrafica>
        <RegimeFiscale>{_xml_escape(regime)}</RegimeFiscale>
      </DatiAnagrafici>
      <Sede>
        <Indirizzo>{_xml_escape(issuer.get('address','N/D'))}</Indirizzo>
        <CAP>{_xml_escape((issuer.get('cap') or '00000').zfill(5)[:5])}</CAP>
        <Comune>{_xml_escape(issuer.get('city','N/D'))}</Comune>
        {f"<Provincia>{_xml_escape(issuer.get('provincia',''))}</Provincia>" if issuer.get('provincia') else ''}
        <Nazione>{_xml_escape(issuer.get('nazione','IT'))}</Nazione>
      </Sede>
    </CedentePrestatore>
    <CessionarioCommittente>
      <DatiAnagrafici>
        {ces_id_block}
        {ces_cf_block}
        <Anagrafica><Denominazione>{ces_den}</Denominazione></Anagrafica>
      </DatiAnagrafici>
      <Sede>
        <Indirizzo>{_xml_escape(client.get('address','N/D'))}</Indirizzo>
        <CAP>{_xml_escape((client.get('cap') or '00000').zfill(5)[:5])}</CAP>
        <Comune>{_xml_escape(client.get('city','N/D'))}</Comune>
        {f"<Provincia>{_xml_escape(client.get('provincia',''))}</Provincia>" if client.get('provincia') else ''}
        <Nazione>IT</Nazione>
      </Sede>
    </CessionarioCommittente>
  </FatturaElettronicaHeader>
  <FatturaElettronicaBody>
    <DatiGenerali>
      <DatiGeneraliDocumento>
        <TipoDocumento>TD01</TipoDocumento>
        <Divisa>EUR</Divisa>
        <Data>{inv_date}</Data>
        <Numero>{_xml_escape(inv_num)}</Numero>
        <ImportoTotaleDocumento>{totale:.2f}</ImportoTotaleDocumento>
      </DatiGeneraliDocumento>
    </DatiGenerali>
    <DatiBeniServizi>
      <DettaglioLinee>
        <NumeroLinea>1</NumeroLinea>
        <Descrizione>{_xml_escape(contract.get('title','Prestazione professionale'))}</Descrizione>
        <Quantita>{worked_days:.2f}</Quantita>
        <UnitaMisura>gg</UnitaMisura>
        <PrezzoUnitario>{daily:.2f}</PrezzoUnitario>
        <PrezzoTotale>{imponibile:.2f}</PrezzoTotale>
        <AliquotaIVA>{aliquota:.2f}</AliquotaIVA>
        {natura_line}
      </DettaglioLinee>
      <DatiRiepilogo>
        <AliquotaIVA>{aliquota:.2f}</AliquotaIVA>
        {natura_line}
        <ImponibileImporto>{imponibile:.2f}</ImponibileImporto>
        <Imposta>{imposta:.2f}</Imposta>
        {f'<RiferimentoNormativo>Op. non soggetta ex art. 1 c. 54-89 L. 190/2014 - Regime forfettario</RiferimentoNormativo>' if regime == 'RF19' else ''}
      </DatiRiepilogo>
    </DatiBeniServizi>
  </FatturaElettronicaBody>
</p:FatturaElettronica>
'''
    # Filename convention SdI: IT{piva}_00001.xml - keep simple sequential
    tx_id = (issuer.get("id_codice_trasmittente") or issuer.get("piva") or "IT99999999999").replace(" ", "")
    if not tx_id.startswith("IT"):
        tx_id = "IT" + tx_id
    safe_num = re.sub(r"[^A-Za-z0-9]", "", inv_num)[:5].upper() or "00001"
    filename = f"{tx_id}_{safe_num}.xml"
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# =============== GOOGLE CALENDAR (iCal URL sync) ===============

class GCalSettingsIn(BaseModel):
    ics_url: str = ""
    enabled: bool = True


@api_router.get("/gcal/settings")
async def gcal_get(user=Depends(get_current_user)):
    doc = await db.gcal_settings.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        return {"ics_url": "", "enabled": False, "last_sync": None, "last_count": 0}
    return doc


@api_router.put("/gcal/settings")
async def gcal_set(payload: GCalSettingsIn, user=Depends(get_current_user)):
    url = payload.ics_url.strip()
    if url and not (url.startswith("https://") or url.startswith("webcal://")):
        raise HTTPException(400, "L'URL deve iniziare con https:// o webcal://")
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    await db.gcal_settings.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"user_id": user["user_id"], "ics_url": url, "enabled": payload.enabled}},
        upsert=True,
    )
    return {"ok": True, "ics_url": url}


def _parse_ics(text: str) -> list:
    """Very small ICS parser - returns list of dicts with uid, summary, date (YYYY-MM-DD),
    end_date (exclusive), all_day (bool), notes."""
    # Unfold folded lines (RFC 5545: continuation lines start with space or tab)
    unfolded = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    events = []
    cur = None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur and cur.get("date"):
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key_full, _, value = line.partition(":")
            key = key_full.split(";")[0].upper()
            params = key_full.split(";")[1:]
            if key == "UID":
                cur["uid"] = value.strip()
            elif key == "SUMMARY":
                cur["summary"] = value.replace("\\,", ",").replace("\\n", " ").strip()
            elif key == "DESCRIPTION":
                cur["notes"] = value.replace("\\,", ",").replace("\\n", " ").strip()[:500]
            elif key == "DTSTART":
                v = value.strip()
                is_date = any(p.upper() == "VALUE=DATE" for p in params) or len(v) == 8
                try:
                    if is_date:
                        cur["date"] = f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
                        cur["all_day"] = True
                    else:
                        # DTSTART with time - use date portion only
                        cur["date"] = f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
                        cur["all_day"] = False
                except Exception:
                    pass
            elif key == "DTEND":
                v = value.strip()
                try:
                    cur["end_date"] = f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
                except Exception:
                    pass
    return events


async def _sync_gcal_for_user(user_id: str) -> dict:
    settings = await db.gcal_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not settings or not settings.get("ics_url") or not settings.get("enabled", True):
        return {"synced": 0, "skipped": True}
    url = settings["ics_url"]
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as hc:
            r = await hc.get(url, headers={"User-Agent": "PlanOp/1.0"})
        if r.status_code != 200:
            raise HTTPException(502, f"iCal URL non raggiungibile (HTTP {r.status_code})")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Errore lettura iCal: {e}")

    events = _parse_ics(r.text)
    today = date.today()
    horizon = today + timedelta(days=365)
    # Keep only future events within 1 year
    future = []
    for ev in events:
        try:
            d = datetime.fromisoformat(ev["date"]).date()
            if today <= d <= horizon:
                future.append(ev)
        except Exception:
            continue

    # Delete existing gcal-synced events for this user (only future dates)
    await db.manual_events.delete_many({
        "user_id": user_id,
        "source": "gcal",
        "date": {"$gte": today.isoformat()},
    })
    # Insert fresh
    docs = []
    for ev in future:
        docs.append({
            "id": uuid.uuid4().hex,
            "user_id": user_id,
            "date": ev["date"],
            "title": (ev.get("summary") or "Evento Google")[:200],
            "client_id": None,
            "notes": ev.get("notes", "")[:500],
            "all_day": ev.get("all_day", True),
            "start_time": None,
            "end_time": None,
            "source": "gcal",
            "gcal_uid": ev.get("uid", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if docs:
        await db.manual_events.insert_many(docs)

    await db.gcal_settings.update_one(
        {"user_id": user_id},
        {"$set": {
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "last_count": len(docs),
        }},
    )
    return {"synced": len(docs), "skipped": False}


@api_router.post("/gcal/sync")
async def gcal_sync_now(user=Depends(get_current_user)):
    res = await _sync_gcal_for_user(user["user_id"])
    return res


@api_router.post("/cron/gcal-sync")
async def cron_gcal_sync(request: Request, payload: ReminderCronIn, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not WEBHOOK_CRON_SECRET or not _secrets.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("X-Webhook-Id") or (payload.run_id or uuid.uuid4().hex)
    existing = await db.cron_runs.find_one({"run_id": run_id}, {"_id": 0})
    if existing:
        return {"ok": True, "duplicate": True}
    await db.cron_runs.insert_one({
        "run_id": run_id,
        "schedule_id": payload.schedule_id or "gcal-sync",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    async def _run_all():
        active = await db.gcal_settings.find({"enabled": True, "ics_url": {"$ne": ""}}, {"_id": 0, "user_id": 1}).to_list(1000)
        for s in active:
            try:
                await _sync_gcal_for_user(s["user_id"])
            except Exception as e:
                logger.error(f"gcal sync failed for {s['user_id']}: {e}")

    background_tasks.add_task(_run_all)
    return {"ok": True, "run_id": run_id}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
