"""Vendor normalization rules — loaded from persisted JSON file."""
import json
import os
from pathlib import Path

RULES_PATH = os.environ.get("VENDOR_RULES_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "vendor_rules.json"))


def load_rules() -> list[dict]:
    """Load ordered vendor rules from JSON file."""
    if not os.path.exists(RULES_PATH):
        return []
    with open(RULES_PATH, "r") as f:
        return json.load(f)


def save_rules(rules: list[dict]):
    """Save rules list to JSON file."""
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    with open(RULES_PATH, "w") as f:
        json.dump(rules, f, indent=2)


def normalize_vendor(description: str, rules: list[dict] = None) -> str:
    """Return normalized vendor name, or raw description if no rule matches."""
    if rules is None:
        rules = load_rules()
    desc_upper = description.upper()
    for rule in rules:
        if rule["pattern"].upper() in desc_upper:
            return rule["vendor"]
    return description.strip()


def add_rule(pattern: str, vendor: str):
    """Add a new rule at the top (most specific first)."""
    rules = load_rules()
    # Remove any existing rule with the same pattern
    rules = [r for r in rules if r["pattern"].upper() != pattern.upper()]
    rules.insert(0, {"pattern": pattern, "vendor": vendor})
    save_rules(rules)


def delete_rule(pattern: str):
    """Delete a rule by pattern."""
    rules = load_rules()
    rules = [r for r in rules if r["pattern"].upper() != pattern.upper()]
    save_rules(rules)


def update_rule(old_pattern: str, new_pattern: str, vendor: str):
    """Update an existing rule."""
    rules = load_rules()
    rules = [r for r in rules if r["pattern"].upper() != old_pattern.upper()]
    rules.insert(0, {"pattern": new_pattern, "vendor": vendor})
    save_rules(rules)