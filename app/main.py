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
from database import reapply_vendor_rules, get_filter_options
from database import get_yearly_spending
from parser import PARSERS
from database import get_cards
from categories import categorize
from vendor_rules import load_rules, normalize_vendor, save_rules, add_rule, delete_rule, get_rule_category
from category_list import load_categories, save_categories
from notes import set_note, apply_notes_to_transactions

app = FastAPI(title="Credit Card Dashboard")

BASE_DIR = Path(__file__).parent
STATEMENTS_DIR = Path(os.environ.get("STATEMENTS_DIR", str(BASE_DIR / "statements")))
STATEMENTS_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def ingest_pdf(pdf_path: Path, card_slug: str = None) -> dict | None:
    """Parse a PDF and insert into DB. Returns result dict or None if skipped/failed."""
    if not pdf_path.name.lower().endswith(".pdf"):
        return None

    # Resolve card slug from directory name or parameter
    if not card_slug:
        card_slug = pdf_path.parent.name
    # Validate card exists
    with db() as conn:
        cards = {c["slug"] for c in get_cards(conn)}
    if card_slug not in cards:
        return None

    # Relative filename (just the PDF name, not the full path)
    rel_filename = pdf_path.name

    # Check if already ingested
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM statements WHERE filename = ? AND card = ?",
            (rel_filename, card_slug),
        ).fetchone()
        if existing:
            return None

    # Select parser based on card slug's parser (amex default)
    parser_name = card_slug.split("_")[0]  # e.g. "amex" from "amex_cobalt"
    parser_fn = PARSERS.get(parser_name)
    if not parser_fn:
        return None

    try:
        result = parser_fn(str(pdf_path))
    except Exception:
        return None

    if not result["transactions"]:
        return None

    # Add auto-categories and vendor normalization
    rules = load_rules()
    for t in result["transactions"]:
        t["vendor"] = normalize_vendor(t["description"], rules)
        rule_cat = get_rule_category(t["description"], rules)
        if rule_cat:
            t["category"] = rule_cat
        else:
            t["category"] = categorize(t["description"])

    closing = result["header"].get("closing_date", "")
    statement_date = closing if closing else "unknown"

    with db() as conn:
        stmt_id = insert_statement(conn, {
            "card": card_slug,
            "statement_date": statement_date,
            "opening_date": result["header"].get("opening_date"),
            "closing_date": closing,
            "cardholder": result["header"].get("cardholder", ""),
            "total_spend": result["total_spend"],
            "total_points": result["total_points"],
            "filename": rel_filename,
        })
        insert_transactions(conn, stmt_id, card_slug, result["transactions"])

    return {
        "statement_id": stmt_id,
        "card_slug": card_slug,
        "filename": rel_filename,
        "transactions": len(result["transactions"]),
        "total_spend": result["total_spend"],
        "total_points": result["total_points"],
    }


def scan_statements_folder():
    """Scan statements/<card_slug>/ for PDFs and ingest them.
    Also migrates loose PDFs in the statements root into amex_cobalt/ for backward compat."""
    ingested = []
    # Migrate any loose PDFs in root statements/ into amex_cobalt/
    for pdf_path in STATEMENTS_DIR.glob("*.pdf"):
        dest = STATEMENTS_DIR / "amex_cobalt" / pdf_path.name
        if not dest.exists():
            import shutil as _shutil
            dest.parent.mkdir(parents=True, exist_ok=True)
            _shutil.move(str(pdf_path), str(dest))

    # Walk per-card subdirs
    for card_dir in sorted(STATEMENTS_DIR.iterdir()):
        if not card_dir.is_dir() or card_dir.name.startswith("."):
            continue
        for pdf_path in sorted(card_dir.glob("*.pdf")):
            result = ingest_pdf(pdf_path, card_slug=card_dir.name)
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
    with db() as conn:
        apply_notes_to_transactions(conn)
    if results:
        print(f"Rebuilt DB: ingested {len(results)} statement(s) from {STATEMENTS_DIR}")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ── Statement Upload ──────────────────────────────────────────────

@app.post("/api/upload")
async def upload_statements(
    files: list[UploadFile] = File(...),
    card_slug: str = Query("amex_cobalt"),
):
    results = []
    errors = []

    # Validate card exists; create amex_cobalt dir as default
    card_dir = STATEMENTS_DIR / card_slug
    card_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append({"filename": file.filename, "error": "Not a PDF"})
            continue

        dest = card_dir / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        result = ingest_pdf(dest, card_slug=card_slug)
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
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
    limit: int = Query(5000),
    offset: int = Query(0),
):
    with db() as conn:
        txns = get_transactions(conn, start, end, card, category, vendor, limit, offset,
                                vendors, categories, points_categories)
    return {"transactions": txns, "count": len(txns)}


@app.get("/api/spending/daily")
async def api_daily_spending(
    start: str = Query(None),
    end: str = Query(None),
    card: str = Query(None),
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
):
    with db() as conn:
        data = get_daily_spending(conn, start, end, card, vendors, categories, points_categories)
    return {"data": data}


@app.get("/api/spending/monthly")
async def api_monthly_spending(
    start: str = Query(None),
    end: str = Query(None),
    card: str = Query(None),
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
):
    with db() as conn:
        data = get_monthly_spending(conn, start, end, card, vendors, categories, points_categories)
    return {"data": data}

@app.get("/api/spending/yearly")
async def api_yearly_spending(
    start: str = Query(None),
    end: str = Query(None),
    card: str = Query(None),
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
):
    with db() as conn:
        data = get_yearly_spending(conn, start, end, card, vendors, categories, points_categories)
    return {"data": data}


@app.get("/api/spending/categories")
async def api_custom_categories(
    start: str = Query(None),
    end: str = Query(None),
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
):
    with db() as conn:
        data = get_spending_by_custom_category(conn, start, end, vendors, categories, points_categories)
    return {"data": data}


@app.get("/api/spending/category")
async def api_category_spending(
    start: str = Query(None),
    end: str = Query(None),
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
):
    with db() as conn:
        data = get_spending_by_category(conn, start, end, vendors, categories, points_categories)
    return {"data": data}


@app.get("/api/spending/vendor")
async def api_vendor_spending(
    start: str = Query(None),
    end: str = Query(None),
    top: int = Query(15),
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
):
    with db() as conn:
        data = get_spending_by_vendor(conn, start, end, top, vendors, categories, points_categories)
    return {"data": data}


@app.get("/api/points")
async def api_points(
    start: str = Query(None),
    end: str = Query(None),
    vendors: list[str] = Query(None),
    categories: list[str] = Query(None),
    points_categories: list[str] = Query(None),
):
    with db() as conn:
        data = get_points_over_time(conn, start, end, vendors, categories, points_categories)
    return {"data": data}

@app.get("/api/filters")
async def api_filters(
    start: str = Query(None),
    end: str = Query(None),
):
    """Distinct vendors, categories, and points categories (optionally date-scoped)."""
    with db() as conn:
        data = get_filter_options(conn, start, end)
    return data


# ── Cards ─────────────────────────────────────────────────────────

@app.get("/api/cards")
async def api_cards():
    with db() as conn:
        cards = get_cards(conn)
    return {"cards": cards}


# ── Vendor Rules ───────────────────────────────────────────────────

@app.get("/api/vendor-rules")
async def api_get_vendor_rules():
    return {"rules": load_rules()}


@app.post("/api/vendor-rules")
async def api_add_vendor_rule(data: dict):
    pattern = data.get("pattern", "").strip()
    vendor = data.get("vendor", "").strip()
    category = data.get("category", "").strip()
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


@app.put("/api/transactions/{txn_id}/notes")
async def api_set_transaction_notes(txn_id: int, data: dict):
    note = data.get("notes", "").strip()
    with db() as conn:
        # Get transaction details for persistence
        row = conn.execute("SELECT transaction_date, description, amount FROM transactions WHERE id = ?", (txn_id,)).fetchone()
        if row:
            conn.execute("UPDATE transactions SET notes = ? WHERE id = ?", (note, txn_id))
            conn.commit()
            set_note(row["transaction_date"], row["description"], row["amount"], note)
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
        stmt = conn.execute(
            "SELECT filename, card FROM statements WHERE id = ?", (statement_id,)
        ).fetchone()
        if not stmt:
            raise HTTPException(404, "Statement not found")
        delete_statement(conn, statement_id)

    # Remove PDF file from card subdir
    if stmt["filename"] and stmt["card"]:
        pdf_path = STATEMENTS_DIR / stmt["card"] / stmt["filename"]
        pdf_path.unlink(missing_ok=True)

    return {"status": "deleted"}


@app.get("/api/pdf/{card_slug}/{filename}")
async def serve_pdf(card_slug: str, filename: str):
    pdf_path = STATEMENTS_DIR / card_slug / filename
    if not pdf_path.exists():
        raise HTTPException(404, "PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf")


# ── Health ────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    with db() as conn:
        count = get_transaction_count(conn)
    return {"status": "ok", "transactions": count}