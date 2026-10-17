#!/usr/bin/env python3
"""
Amex Cobalt Statement Parser v3
Uses pdfplumber for text extraction. Excludes payments/refunds.
Matches points by (date, amount) with description fallback.
"""
import csv
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Missing pdfplumber. Install: pip install pdfplumber", file=sys.stderr)
    sys.exit(1)


EARN_RATES = {
    "Eligible Food/Drink": 5,
    "Eligible Streaming": 3,
    "Eligible Gas/Transit/Ride Share": 2,
    "All Other Purchases": 1,
}

MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

# Keywords that indicate non-purchase transactions
PAYMENT_KEYWORDS = [
    "PAYMENT RECEIVED",
    "RETURNED PAYMENT",
    "MEMBERSHIP FEE",
    "Total of Payment Activity",
    "Total of New Transactions",
    "Total of Other Account",
]


def extract_all_text(pdf_path: str) -> list[str]:
    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def parse_header(pages: list[str]) -> dict:
    first = pages[0]
    info = {}
    m = re.search(r"(\w{3}\d{1,2},\s*\d{4})\s*(\w{3}\d{1,2},\s*\d{4})", first)
    if m:
        info["opening_date"] = m.group(1)
        info["closing_date"] = m.group(2)
        year_m = re.search(r"(\d{4})", m.group(2))
        if year_m:
            info["year"] = year_m.group(1)
    return info


def parse_date(date_str: str, year: str) -> str:
    m = re.match(r"(\w{3})(\d{1,2})", date_str)
    if not m:
        return ""
    month_num = MONTHS.get(m.group(1))
    if not month_num:
        return ""
    return f"{year}-{month_num}-{int(m.group(2)):02d}"


def is_payment(desc: str) -> bool:
    desc_upper = desc.upper()
    return any(kw in desc_upper for kw in PAYMENT_KEYWORDS)


def parse_transactions(pages: list[str], year: str) -> list[dict]:
    txn_pattern = re.compile(
        r"^(\w{3}\d{1,2})\s+(\w{3}\d{1,2})\s+(.+?)\s+(-?[\d,]+\.\d{2})$"
    )
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

            m = txn_pattern.match(line)
            if not m:
                continue

            txn_date_raw, post_date_raw, desc_raw, amount_str = (
                m.group(1), m.group(2), m.group(3).strip(), m.group(4).replace(",", "")
            )

            # Skip foreign currency conversion lines
            if re.search(r"@\s*[\d.]+$", desc_raw):
                continue

            desc_clean = re.sub(r"\s+", " ", desc_raw).strip()

            # Skip payments, refunds, totals
            if is_payment(desc_clean):
                continue

            txn_date = parse_date(txn_date_raw, year)
            post_date = parse_date(post_date_raw, year)
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


def parse_points_section(pages: list[str]) -> list[dict]:
    """
    Parse Membership Rewards section.
    Returns list of {date, description, amount, points, category, rate}.
    """
    entries = []
    current_rate = None
    current_category = None

    for page in pages:
        for line in page.split("\n"):
            line = line.strip()

            # Category header
            cat_match = re.match(r"(\d)\s*pts/\$1\s+(.+?)\s+\$[\d,.]+\s+[\d,]+", line)
            if cat_match:
                current_rate = int(cat_match.group(1))
                current_category = cat_match.group(2).strip()
                continue

            # Points entry
            pts_match = re.match(
                r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\$(-?[\d,.]+)\s+([\d,]+)", line
            )
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


def match_points(transactions: list[dict], points_entries: list[dict]) -> list[dict]:
    """Match points to transactions using (date, amount) as primary key."""
    # Build lookup: (date, amount) -> [points entries]
    points_lookup = {}
    for entry in points_entries:
        key = (entry["date"], round(entry["amount"], 2))
        if key not in points_lookup:
            points_lookup[key] = []
        points_lookup[key].append(entry)

    # Track which points entries have been used
    used = set()

    for txn in transactions:
        txn_date = txn["transaction_date"]
        txn_amount = round(abs(txn["amount"]), 2)

        # Try exact (posting_date, amount) match — points section uses posting dates
        key = (txn["posting_date"], txn_amount)
        if key in points_lookup:
            for i, entry in enumerate(points_lookup[key]):
                entry_key = (entry["date"], round(entry["amount"], 2), i)
                if entry_key not in used:
                    txn["points"] = entry["points"]
                    txn["points_rate"] = entry["rate"]
                    txn["points_category"] = entry["category"]
                    used.add(entry_key)
                    break
            else:
                # All matching entries used, try description match
                _match_by_description(txn, points_entries, used)
        else:
            _match_by_description(txn, points_entries, used)

        # Default: 1 pt/$1
        if not txn["points_category"]:
            txn["points"] = int(round(abs(txn["amount"])))
            txn["points_rate"] = 1
            txn["points_category"] = "All Other Purchases"

    return transactions


def _match_by_description(txn, points_entries, used):
    """Fallback: match by date + description similarity."""
    txn_date = txn["transaction_date"]
    txn_desc = txn["description"].upper()

    for i, entry in enumerate(points_entries):
        entry_key = (entry["date"], round(entry["amount"], 2), i)
        if entry_key in used:
            continue
        if entry["date"] != txn_date:
            continue

        pts_desc = entry["description"].upper()
        # Check description overlap
        if pts_desc[:20] in txn_desc or txn_desc[:20] in pts_desc:
            txn["points"] = entry["points"]
            txn["points_rate"] = entry["rate"]
            txn["points_category"] = entry["category"]
            used.add(entry_key)
            return

        # Word overlap
        txn_words = set(txn_desc.split()) - {"THE", "A", "AN", "OF", "IN", "AT", "CA", "INC", "TORONTO", "CAMBRIDGE"}
        pts_words = set(pts_desc.split()) - {"THE", "A", "AN", "OF", "IN", "AT", "CA", "INC", "TORONTO", "CAMBRIDGE"}
        if len(txn_words & pts_words) >= 2:
            txn["points"] = entry["points"]
            txn["points_rate"] = entry["rate"]
            txn["points_category"] = entry["category"]
            used.add(entry_key)
            return


def parse_amex_statement(pdf_path: str) -> dict:
    pages = extract_all_text(pdf_path)
    header = parse_header(pages)
    year = header.get("year", "2026")

    transactions = parse_transactions(pages, year)
    points_entries = parse_points_section(pages)
    transactions = match_points(transactions, points_entries)

    return {"header": header, "transactions": transactions, "source": pdf_path}


def write_csv(result: dict, output_path: str):
    fields = [
        "transaction_date", "posting_date", "cardholder",
        "description", "amount", "points", "points_rate", "points_category",
    ]
    with open(output_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for txn in result["transactions"]:
            w.writerow({k: txn[k] for k in fields})


def main():
    if len(sys.argv) < 2:
        print("Usage: amex_parser.py <statement.pdf> [output.csv]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else pdf_path.replace(".pdf", ".csv")

    result = parse_amex_statement(pdf_path)
    write_csv(result, output_path)

    txns = result["transactions"]
    header = result["header"]

    print(f"Statement: {header.get('opening_date')} to {header.get('closing_date')}")
    print(f"Transactions: {len(txns)}")
    print(f"Output: {output_path}")

    total_spend = sum(t["amount"] for t in txns)
    total_points = sum(t["points"] for t in txns)

    print(f"Total spend: ${total_spend:,.2f}")
    print(f"Total points: {total_points:,}")

    cats = {}
    for t in txns:
        cat = t["points_category"]
        if cat not in cats:
            cats[cat] = {"count": 0, "spend": 0.0, "points": 0}
        cats[cat]["count"] += 1
        cats[cat]["spend"] += abs(t["amount"])
        cats[cat]["points"] += t["points"]

    print("\nPoints breakdown:")
    for cat in sorted(cats, key=lambda c: EARN_RATES.get(c, 0), reverse=True):
        d = cats[cat]
        rate = EARN_RATES.get(cat, 1)
        print(f"  {rate}x {cat}: {d['count']} txns, ${d['spend']:,.2f}, {d['points']:,} pts")


if __name__ == "__main__":
    main()