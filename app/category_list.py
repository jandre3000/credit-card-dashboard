"""Manage the list of available spending categories."""
import json
import os

CATEGORIES_PATH = os.environ.get("CATEGORIES_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "categories.json"))

DEFAULT_CATEGORIES = [
    "Grocery", "Dining & Drinks", "Gas & Transit", "Subscriptions",
    "Shopping", "Health", "Telecom", "Home & Services", "Donations",
    "Travel", "Kids & Education", "Auto", "Gifts", "Other",
]


def load_categories() -> list[str]:
    if not os.path.exists(CATEGORIES_PATH):
        save_categories(DEFAULT_CATEGORIES)
        return list(DEFAULT_CATEGORIES)
    with open(CATEGORIES_PATH, "r") as f:
        return json.load(f)


def save_categories(categories: list[str]):
    os.makedirs(os.path.dirname(CATEGORIES_PATH), exist_ok=True)
    with open(CATEGORIES_PATH, "w") as f:
        json.dump(categories, f, indent=2)