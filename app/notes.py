"""Transaction notes — persisted across DB rebuilds."""
import json
import os

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
NOTES_PATH = os.environ.get("NOTES_PATH", os.path.join(DATA_DIR, "transaction_notes.json"))


def _load() -> dict:
    if not os.path.exists(NOTES_PATH):
        return {}
    with open(NOTES_PATH, "r") as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(os.path.dirname(NOTES_PATH), exist_ok=True)
    with open(NOTES_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _make_key(txn_date: str, description: str, amount: float) -> str:
    """Composite key for matching transactions across rebuilds."""
    return f"{txn_date}|{description.strip()}|{round(amount, 2)}"


def get_notes() -> dict:
    return _load()


def set_note(txn_date: str, description: str, amount: float, note: str):
    data = _load()
    key = _make_key(txn_date, description, amount)
    if note.strip():
        data[key] = note.strip()
    elif key in data:
        del data[key]
    _save(data)


def apply_notes_to_transactions(conn) -> dict:
    """Re-apply saved notes to transactions after DB rebuild. Returns notes dict."""
    notes = _load()
    if not notes:
        return {}
    rows = conn.execute("SELECT id, transaction_date, description, amount FROM transactions").fetchall()
    for row in rows:
        key = _make_key(row["transaction_date"], row["description"], row["amount"])
        if key in notes:
            conn.execute("UPDATE transactions SET notes = ? WHERE id = ?", (notes[key], row["id"]))
    conn.commit()
    return notes