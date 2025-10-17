import os
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
import httpx
import xmlrpc.client

LOG = logging.getLogger("tokko_bridge")
logging.basicConfig(level=logging.INFO)

DB_PATH = os.environ.get("TOKKO_DB_PATH", "./tokko_bridge.sqlite3")
TOKKO_API_URL = os.environ.get("TOKKO_API_URL", "https://api.tokkobroker.example/v1/contacts")
TOKKO_API_KEY = os.environ.get("TOKKO_API_KEY", "")
RESPONDIO_API_URL = os.environ.get("RESPONDIO_API_URL", "https://api.respond.io/v1/contacts")
RESPONDIO_API_KEY = os.environ.get("RESPONDIO_API_KEY", "")
VERIFY_TOKEN = os.environ.get("TOKKO_BRIDGE_TOKEN", "changeme")

# Optional Odoo XML-RPC settings (if set, the bridge will create crm.lead records)
ODOO_URL = os.environ.get("ODOO_URL")
ODOO_DB = os.environ.get("ODOO_DB")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD")

app = FastAPI(title="Tokko Broker → respond.io bridge")


class RunRequest(BaseModel):
    initiator: str | None = None
    last_run: str | None = None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS offsets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cursor TEXT UNIQUE,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT,
            status TEXT,
            details TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def get_last_cursor():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT cursor FROM offsets ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def save_cursor(cursor: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO offsets (id, cursor, created_at) VALUES ((SELECT id FROM offsets ORDER BY id DESC LIMIT 1), ?, ?)", (cursor, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def save_run(run_id: str, status: str, details: str | None = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO runs (run_id, started_at, status, details) VALUES (?, ?, ?, ?)", (run_id, datetime.now(timezone.utc).isoformat(), status, details))
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_event():
    LOG.info("Starting tokko_bridge")
    init_db()


@app.post("/run-sync")
async def run_sync(request: Request, authorization: str | None = Header(None)):
    # Simple bearer token check
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    body = await request.json()
    run_req = RunRequest(**body) if body else RunRequest()
    run_id = str(uuid.uuid4())
    save_run(run_id, "started", f"initiator={run_req.initiator}")

    # Fetch from Tokko Broker
    last_cursor = get_last_cursor()
    params = {}
    if last_cursor:
        params["cursor"] = last_cursor

    headers = {"Authorization": f"Bearer {TOKKO_API_KEY}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            LOG.info("Requesting Tokko Broker contacts/leads, cursor=%s", last_cursor)
            resp = await client.get(TOKKO_API_URL, headers=headers, params=params)
            resp.raise_for_status()
            # Accept common shapes: {data: [...]}, {contacts: [...]}, {leads: [...]}
            j = resp.json()
            items = j.get("data") or j.get("contacts") or j.get("leads") or []
            next_cursor = j.get("next_cursor") or j.get("cursor") or None
        except Exception as e:
            save_run(run_id, "failed", str(e))
            LOG.exception("Failed fetching from Tokko Broker")
            raise HTTPException(status_code=502, detail=f"Tokko Broker fetch failed: {e}")

        sent = 0
            created_leads = []
        for item in items:
            payload = transform_to_respondio(item)
            try:
                r = await client.post(RESPONDIO_API_URL, headers={"Authorization": f"Bearer {RESPONDIO_API_KEY}", "Content-Type": "application/json"}, json=payload)
                r.raise_for_status()
                sent += 1
            except Exception:
                LOG.exception("Failed sending to respond.io for contact/lead id=%s", item.get("id"))
                # Continue processing other items; record error
                continue

                # Optionally create lead in Odoo via XML-RPC
                if ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_PASSWORD:
                    try:
                        odoo_result = create_or_get_lead_in_odoo(item)
                        if odoo_result:
                            created_leads.append(odoo_result)
                    except Exception:
                        LOG.exception("Failed creating lead in Odoo for contact id=%s", item.get("id"))
                        # do not abort the whole run
                        continue

        if next_cursor:
            save_cursor(next_cursor)

    save_run(run_id, "completed", f"sent={sent}")
    return {"status": "completed", "run_id": run_id, "sent": sent, "created_leads": created_leads}


def transform_to_respondio(item: dict) -> dict:
    """
    Transform a Tokko contact/lead into a generic respond.io contact payload.
    Adapt this to match your respond.io endpoint schema if needed.
    """
    # Build a display name from common fields
    name = item.get("name") or "".join([part for part in [item.get("first_name"), item.get("last_name")] if part]) or item.get("fullname")
    phone = item.get("phone") or item.get("mobile") or item.get("msisdn")
    email = item.get("email")

    # Build identifiers array as required by respond.io (phone/email as identifiers)
    identifiers = []
    if phone:
        identifiers.append({"type": "phone", "value": phone})
    if email:
        identifiers.append({"type": "email", "value": email})

    contact = {
        "name": name or None,
        "source": "tokko",
        "external_id": item.get("id"),
        "identifiers": identifiers,
        "metadata": {
            "tokko_id": item.get("id"),
            "origin": item.get("origin") or item.get("source")
        }
    }

    # respond.io expects a top-level object for contact creation
    return contact


def odoo_auth():
    """Authenticate to Odoo via XML-RPC and return common endpoints."""
    url = ODOO_URL.rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models


def create_or_get_lead_in_odoo(item: dict) -> dict | None:
    """Idempotent create/search of crm.lead in Odoo. Returns dict with id and external_id."""
    if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_PASSWORD):
        return None

    uid, models = odoo_auth()
    if not uid:
        raise RuntimeError("Odoo authentication failed")

    external_id = item.get("id")
    phone = item.get("phone") or item.get("mobile") or item.get("msisdn")
    email = item.get("email")

    # search by external_id first
    domain = [["x_external_id", "=", external_id]] if external_id else []
    # fallback: search by email or phone
    if not domain and email:
        domain = [["email_from", "=", email]]
    if not domain and phone:
        domain = [["phone", "=", phone]]

    lead_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'crm.lead', 'search', [domain], {'limit': 1}) if domain else []
    if lead_ids:
        return {"odoo_id": lead_ids[0], "external_id": external_id}

    # create
    name = item.get("name") or " ".join([p for p in [item.get("first_name"), item.get("last_name")] if p]) or item.get("fullname") or "New Lead"
    vals = {
        'name': name,
        'contact_name': name,
        'type': 'lead',
        'email_from': email,
        'phone': phone,
    }
    # custom external id stored in x_external_id (you may need to create this field in Odoo)
    if external_id:
        vals['x_external_id'] = external_id

    new_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'crm.lead', 'create', [vals])
    return {"odoo_id": new_id, "external_id": external_id}
