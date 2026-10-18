"""Credit Card Statement Dashboard — FastAPI backend."""
import asyncio
import os
import shutil
from datetime import date
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db, db, insert_statement, insert_transactions
from database import get_transactions, get_daily_spending, get_monthly_spending, get_spending_by_category
from database import get_spending_by_vendor, get_points_over_time, get_statements
from database import delete_statement, get_transaction_count, get_spending_by_custom_category
from database import reapply_vendor_rules
from parser import parse_amex_pdf
from categories import categorize
from vendor_rules import load_rules, normalize_vendor, save_rules, add_rule, delete_rule, get_rule_category
from category_list import load_categories, save_categories

app = FastAPI(title="Credit Card Dashboard")

BASE_DIR = Path(__file__).parent
STATEMENTS_DIR = Path(os.environ.get("STATEMENTS_DIR", str(BASE_DIR / "statements")))
STATEMENTS_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def ingest_pdf(pdf_path: Path) -> dict | None:
    """Parse a PDF and insert into DB. Returns result dict or None if skipped/failed."""
    if not pdf_path.name.lower().endswith(".pdf"):
        return None

    # Check if already ingested
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM statements WHERE filename = ?", (pdf_path.name,)
        ).fetchone()
        if existing:
            return None

    try:
        result = parse_amex_pdf(str(pdf_path))
    except Exception:
        return None

    if not result["transactions"]:
        return None

    # Add auto-categories and vendor normalization
    rules = load_rules()
    for t in result["transactions"]:
        t["vendor"] = normalize_vendor(t["description"], rules)
        # Vendor rule category > keyword auto-categorizer > "Other"
        rule_cat = get_rule_category(t["description"], rules)
        if rule_cat:
            t["category"] = rule_cat
        else:
            t["category"] = categorize(t["description"])

    closing = result["header"].get("closing_date", "")
    statement_date = closing if closing else "unknown"

    with db() as conn:
        stmt_id = insert_statement(conn, {
            "card": result["card"],
            "statement_date": statement_date,
            "opening_date": result["header"].get("opening_date"),
            "closing_date": closing,
            "cardholder": result["header"].get("cardholder"),
            "total_spend": result["total_spend"],
            "total_points": result["total_points"],
            "filename": pdf_path.name,
        })
        insert_transactions(conn, stmt_id, result["card"], result["transactions"])

    return {
        "statement_id": stmt_id,
        "filename": pdf_path.name,
        "transactions": len(result["transactions"]),
        "total_spend": result["total_spend"],
        "total_points": result["total_points"],
    }


def scan_statements_folder():
    """Scan statements/ for any PDFs not yet in the DB and ingest them."""
    ingested = []
    for pdf_path in STATEMENTS_DIR.glob("*.pdf"):
        result = ingest_pdf(pdf_path)
        if result:
            ingested.append(result)
    return ingested


@app.on_event("startup")
def startup():
    # Blow away and rebuild DB from source PDFs on every start
    db_path = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "credit_cards.db"))
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()
    results = scan_statements_folder()
    if results:
        print(f"Rebuilt DB: ingested {len(results)} statement(s) from {STATEMENTS_DIR}")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ── Statement Upload ──────────────────────────────────────────────

@app.post("/api/upload")
async def upload_statements(files: list[UploadFile] = File(...)):
    results = []
    errors = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append({"filename": file.filename, "error": "Not a PDF"})
            continue

        # Save the uploaded PDF
        dest = STATEMENTS_DIR / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Parse and ingest
        result = ingest_pdf(dest)
        if result:
            results.append(result)
        else:
            errors.append({"filename": file.filename, "error": "Failed to parse or already ingested"})

    return {
        "status": "ok",
        "ingested": len(results),
        "results": results,
        "errors": errors,
    }


# ── Data API ──────────────────────────────────────────────────────

@app.get("/api/transactions")
async def api_transactions(
    start: str = Query(None),
    end: str = Query(None),
    card: str = Query(None),
    category: str = Query(None),
    vendor: str = Query(None),
    limit: int = Query(5000),
    offset: int = Query(0),
):
    with db() as conn:
        txns = get_transactions(conn, start, end, card, category, vendor, limit, offset)
    return {"transactions": txns, "count": len(txns)}


@app.get("/api/spending/daily")
async def api_daily_spending(
    start: str = Query(None),
    end: str = Query(None),
    card: str = Query(None),
):
    with db() as conn:
        data = get_daily_spending(conn, start, end, card)
    return {"data": data}


@app.get("/api/spending/monthly")
async def api_monthly_spending(
    start: str = Query(None),
    end: str = Query(None),
    card: str = Query(None),
):
    with db() as conn:
        data = get_monthly_spending(conn, start, end, card)
    return {"data": data}


@app.get("/api/spending/categories")
async def api_custom_categories(
    start: str = Query(None),
    end: str = Query(None),
):
    with db() as conn:
        data = get_spending_by_custom_category(conn, start, end)
    return {"data": data}


@app.get("/api/spending/category")
async def api_category_spending(
    start: str = Query(None),
    end: str = Query(None),
):
    with db() as conn:
        data = get_spending_by_category(conn, start, end)
    return {"data": data}


@app.get("/api/spending/vendor")
async def api_vendor_spending(
    start: str = Query(None),
    end: str = Query(None),
    top: int = Query(15),
):
    with db() as conn:
        data = get_spending_by_vendor(conn, start, end, top)
    return {"data": data}


@app.get("/api/points")
async def api_points(
    start: str = Query(None),
    end: str = Query(None),
):
    with db() as conn:
        data = get_points_over_time(conn, start, end)
    return {"data": data}


# ── Vendor Rules ───────────────────────────────────────────────────

@app.get("/api/vendor-rules")
async def api_get_vendor_rules():
    return {"rules": load_rules()}


@app.post("/api/vendor-rules")
async def api_add_vendor_rule(data: dict):
    pattern = data.get("pattern", "").strip()
    vendor = data.get("vendor", "").strip()
    if not pattern or not vendor:
        raise HTTPException(400, "Both pattern and vendor are required")
    add_rule(pattern, vendor, category)
    with db() as conn:
        reapply_vendor_rules(conn)
    return {"status": "ok", "rules": load_rules()}


@app.put("/api/vendor-rules")
async def api_update_vendor_rule(data: dict):
    old_pattern = data.get("old_pattern", "").strip()
    new_pattern = data.get("pattern", "").strip()
    vendor = data.get("vendor", "").strip()
    category = data.get("category", "").strip()
    if not old_pattern or not new_pattern or not vendor:
        raise HTTPException(400, "old_pattern, pattern, and vendor are required")
    from vendor_rules import update_rule
    update_rule(old_pattern, new_pattern, vendor, category)
    with db() as conn:
        reapply_vendor_rules(conn)
    return {"status": "ok", "rules": load_rules()}


@app.delete("/api/vendor-rules/{pattern:path}")
async def api_delete_vendor_rule(pattern: str):
    delete_rule(pattern)
    with db() as conn:
        reapply_vendor_rules(conn)
    return {"status": "ok", "rules": load_rules()}


# ── Categories ─────────────────────────────────────────────────────

@app.get("/api/categories")
async def api_get_categories():
    return {"categories": load_categories()}


@app.put("/api/categories")
async def api_update_categories(data: dict):
    cats = data.get("categories", [])
    if not cats:
        raise HTTPException(400, "categories list required")
    save_categories(cats)
    return {"status": "ok", "categories": cats}


@app.put("/api/transactions/{txn_id}/category")
async def api_set_transaction_category(txn_id: int, data: dict):
    category = data.get("category", "").strip()
    with db() as conn:
        conn.execute("UPDATE transactions SET category = ? WHERE id = ?", (category, txn_id))
        conn.commit()
    return {"status": "ok"}


@app.get("/api/statements")
async def api_statements():
    with db() as conn:
        stmts = get_statements(conn)
        count = get_transaction_count(conn)
    return {"statements": stmts, "transaction_count": count}


@app.delete("/api/statements/{statement_id}")
async def api_delete_statement(statement_id: int):
    with db() as conn:
        stmt = conn.execute("SELECT filename FROM statements WHERE id = ?", (statement_id,)).fetchone()
        if not stmt:
            raise HTTPException(404, "Statement not found")
        delete_statement(conn, statement_id)

    # Remove PDF file
    if stmt["filename"]:
        pdf_path = STATEMENTS_DIR / stmt["filename"]
        pdf_path.unlink(missing_ok=True)

    return {"status": "deleted"}


@app.get("/api/pdf/{filename}")
async def serve_pdf(filename: str):
    pdf_path = STATEMENTS_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(404, "PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf")


# ── Health ────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    with db() as conn:
        count = get_transaction_count(conn)
    return {"status": "ok", "transactions": count}