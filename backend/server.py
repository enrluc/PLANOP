from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
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
import json as _json

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
    name: str
    address: str
    city: Optional[str] = ""
    contact_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ClientIn(BaseModel):
    name: str
    address: str
    city: Optional[str] = ""
    contact_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    notes: Optional[str] = ""


class Contract(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    client_id: str
    title: str
    total_days: int
    daily_rate: float = 0
    intervention_type: str = "consulenza"
    priority: str = "medium"  # high, medium, low
    start_date: Optional[str] = None  # ISO date
    deadline: Optional[str] = None  # ISO date
    signed_date: Optional[str] = None
    status: str = "active"  # active, planned, completed, invoiced
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContractIn(BaseModel):
    client_id: str
    title: str
    total_days: int
    daily_rate: float = 0
    intervention_type: str = "consulenza"
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
    day_index: int  # 1..total_days
    status: str = "planned"  # planned, done
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
    max_days_per_client_block: int = 3


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

    # Compute remaining days
    remaining = []
    for c in contracts:
        done = planned_per_contract.get(c["id"], 0)
        rem = c["total_days"] - done
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

    # Assign consecutive dates
    start = datetime.fromisoformat(payload.start_from).date() if payload.start_from else today + timedelta(days=1)
    cur = start
    new_interventions = []
    max_block = max(1, payload.max_days_per_client_block)
    for item in ordered:
        c = item["contract"]
        rem = item["remaining"]
        # Split into blocks of max_block
        done_for_contract = planned_per_contract.get(c["id"], 0)
        while rem > 0:
            block = min(max_block, rem)
            for _ in range(block):
                # Skip weekends
                if payload.workdays_only:
                    while cur.weekday() >= 5 or cur.isoformat() in booked_dates:
                        cur = cur + timedelta(days=1)
                else:
                    while cur.isoformat() in booked_dates:
                        cur = cur + timedelta(days=1)
                iv = Intervention(
                    user_id=user["user_id"],
                    contract_id=c["id"],
                    client_id=c["client_id"],
                    date=cur.isoformat(),
                    day_index=done_for_contract + 1,
                )
                new_interventions.append(iv.model_dump())
                booked_dates.add(cur.isoformat())
                done_for_contract += 1
                cur = cur + timedelta(days=1)
                rem -= 1

    response_items = []
    if new_interventions:
        # Copy dicts before insert to avoid Motor mutating them with _id (ObjectId)
        response_items = [dict(iv) for iv in new_interventions]
        await db.interventions.insert_many(new_interventions)
        contract_ids = list({iv["contract_id"] for iv in new_interventions})
        await db.contracts.update_many({"id": {"$in": contract_ids}}, {"$set": {"status": "planned"}})

    return {"planned": len(response_items), "interventions": response_items}


@api_router.get("/interventions")
async def list_interventions(user=Depends(get_current_user)):
    docs = await db.interventions.find({"user_id": user["user_id"]}, {"_id": 0}).sort("date", 1).to_list(2000)
    return docs


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
        d = ev["date"].replace("-", "")
        dt_next = (datetime.fromisoformat(ev["date"]).date() + timedelta(days=1)).isoformat().replace("-", "")
        cli = clients_map.get(ev.get("client_id")) if ev.get("client_id") else None
        summary = ev.get("title", "Appuntamento")
        loc = f"{cli.get('address','')}, {cli.get('city','')}" if cli else ""
        desc = (ev.get("notes") or "").replace("\n", "\\n")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev['id']}@planop-manual",
            f"DTSTART;VALUE=DATE:{d}",
            f"DTEND;VALUE=DATE:{dt_next}",
            f"SUMMARY:[Extra] {summary}",
            f"LOCATION:{loc}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ]
    for iv in ivs:
        c = contracts_map.get(iv["contract_id"], {})
        cli = clients_map.get(iv["client_id"], {})
        d = iv["date"].replace("-", "")
        dt_next = (datetime.fromisoformat(iv["date"]).date() + timedelta(days=1)).isoformat().replace("-", "")
        summary = f"{c.get('title', 'Intervento')} @ {cli.get('name', '')}"
        loc = f"{cli.get('address','')}, {cli.get('city','')}"
        desc = f"Contratto: {c.get('title','')}\\nGiorno {iv['day_index']}/{c.get('total_days','')}\\nReferente: {cli.get('contact_name','')} {cli.get('phone','')}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{iv['id']}@planop",
            f"DTSTART;VALUE=DATE:{d}",
            f"DTEND;VALUE=DATE:{dt_next}",
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
    """Extract structured contract fields from raw contract text using Claude Haiku 4.5."""
    sys_msg = (
        "Sei un assistente italiano che estrae dati strutturati da contratti di consulenza. "
        "Restituisci SOLO un oggetto JSON valido con questi campi: "
        "{\"client_name\": string, \"city\": string, \"address\": string, "
        "\"contact_name\": string, \"phone\": string, \"email\": string, "
        "\"title\": string (titolo/oggetto attività), "
        "\"total_days\": integer (numero giornate previste), "
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
    resp = await chat.send_message(UserMessage(text=f"Analizza il seguente contratto ed estrai i dati:\n\n{payload.text}"))
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
