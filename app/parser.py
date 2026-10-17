"""Amex Cobalt statement parser — app-integrated version."""
import re
import pdfplumber

MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

PAYMENT_KEYWORDS = [
    "PAYMENT RECEIVED", "RETURNED PAYMENT", "MEMBERSHIP FEE",
    "Total of Payment Activity", "Total of New Transactions",
    "Total of Other Account",
]


def parse_amex_pdf(pdf_path: str) -> dict:
    """Parse an Amex Cobalt statement PDF. Returns header + transactions."""
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]

    header = _parse_header(pages)
    year = header.get("year", "2026")
    transactions = _parse_transactions(pages, year)
    points_entries = _parse_points(pages)
    transactions = _match_points(transactions, points_entries)

    total_spend = sum(t["amount"] for t in transactions)
    total_points = sum(t["points"] for t in transactions)

    return {
        "card": "amex_cobalt",
        "header": header,
        "transactions": transactions,
        "total_spend": round(total_spend, 2),
        "total_points": total_points,
    }


def _parse_header(pages: list[str]) -> dict:
    first = pages[0]
    info = {}
    m = re.search(r"(\w{3}\d{1,2},\s*\d{4})\s*(\w{3}\d{1,2},\s*\d{4})", first)
    if m:
        info["opening_date"] = m.group(1)
        info["closing_date"] = m.group(2)
        year_m = re.search(r"(\d{4})", m.group(2))
        if year_m:
            info["year"] = year_m.group(1)
    info["cardholder"] = "JAN DREWNIAK"
    return info


def _parse_date(date_str: str, year: str) -> str:
    m = re.match(r"(\w{3})(\d{1,2})", date_str)
    if not m:
        return ""
    month_num = MONTHS.get(m.group(1))
    if not month_num:
        return ""
    return f"{year}-{month_num}-{int(m.group(2)):02d}"


def _is_payment(desc: str) -> bool:
    return any(kw in desc.upper() for kw in PAYMENT_KEYWORDS)


def _parse_transactions(pages: list[str], year: str) -> list[dict]:
    pattern = re.compile(r"^(\w{3}\d{1,2})\s+(\w{3}\d{1,2})\s+(.+?)\s+(-?[\d,]+\.\d{2})$")
    cardholder = "JAN DREWNIAK"
    transactions = []

    for page in pages:
        for line in page.split("\n"):
            line = line.strip()

            if "New Transactions for" in line:
                m = re.search(r"New Transactions for\s*(.+)", line)
                if m:
                    cardholder = m.group(1).strip()
                continue

            m = pattern.match(line)
            if not m:
                continue

            txn_date_raw, post_date_raw, desc_raw, amount_str = (
                m.group(1), m.group(2), m.group(3).strip(), m.group(4).replace(",", "")
            )

            if re.search(r"@\s*[\d.]+$", desc_raw):
                continue

            desc_clean = re.sub(r"\s+", " ", desc_raw).strip()

            if _is_payment(desc_clean):
                continue

            txn_date = _parse_date(txn_date_raw, year)
            post_date = _parse_date(post_date_raw, year)
            if not txn_date:
                continue

            transactions.append({
                "transaction_date": txn_date,
                "posting_date": post_date,
                "cardholder": cardholder,
                "description": desc_clean,
                "amount": float(amount_str),
                "points": 0,
                "points_rate": 0,
                "points_category": "",
            })

    return transactions


def _parse_points(pages: list[str]) -> list[dict]:
    entries = []
    current_rate = None
    current_category = None

    for page in pages:
        for line in page.split("\n"):
            line = line.strip()

            cat_match = re.match(r"(\d)\s*pts/\$1\s+(.+?)\s+\$[\d,.]+\s+[\d,]+", line)
            if cat_match:
                current_rate = int(cat_match.group(1))
                current_category = cat_match.group(2).strip()
                continue

            pts_match = re.match(r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\$(-?[\d,.]+)\s+([\d,]+)", line)
            if pts_match and current_rate and current_category:
                date_str = pts_match.group(1)
                desc = pts_match.group(2).strip()
                amount = float(pts_match.group(3).replace(",", ""))
                points = int(pts_match.group(4).replace(",", ""))

                parts = date_str.split("/")
                date_key = f"{parts[2]}-{parts[0]}-{parts[1]}"

                entries.append({
                    "date": date_key,
                    "description": desc,
                    "amount": amount,
                    "points": points,
                    "category": current_category,
                    "rate": current_rate,
                })

    return entries


def _match_points(transactions: list[dict], points_entries: list[dict]) -> list[dict]:
    points_lookup = {}
    for entry in points_entries:
        key = (entry["date"], round(entry["amount"], 2))
        if key not in points_lookup:
            points_lookup[key] = []
        points_lookup[key].append(entry)

    used = set()

    for txn in transactions:
        txn_amount = round(abs(txn["amount"]), 2)
        key = (txn["posting_date"], txn_amount)

        matched = False
        if key in points_lookup:
            for i, entry in enumerate(points_lookup[key]):
                entry_key = (entry["date"], round(entry["amount"], 2), i)
                if entry_key not in used:
                    txn["points"] = entry["points"]
                    txn["points_rate"] = entry["rate"]
                    txn["points_category"] = entry["category"]
                    used.add(entry_key)
                    matched = True
                    break

        if not matched:
            txn_desc = txn["description"].upper()
            for i, entry in enumerate(points_entries):
                entry_key = (entry["date"], round(entry["amount"], 2), i)
                if entry_key in used:
                    continue
                if entry["date"] != txn["posting_date"]:
                    continue
                pts_desc = entry["description"].upper()
                if pts_desc[:20] in txn_desc or txn_desc[:20] in pts_desc:
                    txn["points"] = entry["points"]
                    txn["points_rate"] = entry["rate"]
                    txn["points_category"] = entry["category"]
                    used.add(entry_key)
                    matched = True
                    break

        if not matched:
            txn["points"] = int(round(abs(txn["amount"])))
            txn["points_rate"] = 1
            txn["points_category"] = "All Other Purchases"

    return transactions