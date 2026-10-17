"""Credit Card Statement Dashboard — FastAPI backend."""
import os
import shutil
from datetime import date
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db, db, insert_statement, insert_transactions
from database import get_transactions, get_daily_spending, get_spending_by_category
from database import get_spending_by_vendor, get_points_over_time, get_statements
from database import delete_statement, get_transaction_count
from parser import parse_amex_pdf

app = FastAPI(title="Credit Card Dashboard")

BASE_DIR = Path(__file__).parent
STATEMENTS_DIR = Path(os.environ.get("STATEMENTS_DIR", str(BASE_DIR / "statements")))
STATEMENTS_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ── Statement Upload ──────────────────────────────────────────────

@app.post("/api/upload")
async def upload_statement(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")

    # Save the uploaded PDF
    dest = STATEMENTS_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Parse the statement
    try:
        result = parse_amex_pdf(str(dest))
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"Failed to parse statement: {e}")

    if not result["transactions"]:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, "No transactions found in PDF")

    # Determine statement date (closing date)
    closing = result["header"].get("closing_date", "")
    statement_date = closing if closing else "unknown"

    # Store in database
    with db() as conn:
        stmt_id = insert_statement(conn, {
            "card": result["card"],
            "statement_date": statement_date,
            "opening_date": result["header"].get("opening_date"),
            "closing_date": closing,
            "cardholder": result["header"].get("cardholder"),
            "total_spend": result["total_spend"],
            "total_points": result["total_points"],
            "filename": file.filename,
        })
        insert_transactions(conn, stmt_id, result["card"], result["transactions"])

    return {
        "status": "ok",
        "statement_id": stmt_id,
        "filename": file.filename,
        "transactions": len(result["transactions"]),
        "total_spend": result["total_spend"],
        "total_points": result["total_points"],
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