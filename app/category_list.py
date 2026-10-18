"""Manage the list of available spending categories."""
import json
import os
import shutil

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
CATEGORIES_PATH = os.environ.get("CATEGORIES_PATH", os.path.join(DATA_DIR, "categories.json"))
SEED_PATH = os.path.join(os.path.dirname(__file__), "seed", "categories.json")


def load_categories() -> list[str]:
    if not os.path.exists(CATEGORIES_PATH):
        _init_from_seed()
    with open(CATEGORIES_PATH, "r") as f:
        return json.load(f)


def _init_from_seed():
    """Copy seed categories to the data directory on first run."""
    os.makedirs(os.path.dirname(CATEGORIES_PATH), exist_ok=True)
    if os.path.exists(SEED_PATH):
        shutil.copy2(SEED_PATH, CATEGORIES_PATH)
    else:
        save_categories(["Other"])


def save_categories(categories: list[str]):
    os.makedirs(os.path.dirname(CATEGORIES_PATH), exist_ok=True)
    with open(CATEGORIES_PATH, "w") as f:
        json.dump(categories, f, indent=2)