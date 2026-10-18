"""Vendor normalization rules — loaded from persisted JSON file."""
import json
import os
import shutil
from pathlib import Path

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
RULES_PATH = os.environ.get("VENDOR_RULES_PATH", os.path.join(DATA_DIR, "vendor_rules.json"))
SEED_PATH = os.path.join(os.path.dirname(__file__), "seed", "vendor_rules.json")


def load_rules() -> list[dict]:
    """Load ordered vendor rules from JSON file. Creates from seed if missing."""
    if not os.path.exists(RULES_PATH):
        _init_from_seed()
    with open(RULES_PATH, "r") as f:
        return json.load(f)


def _init_from_seed():
    """Copy seed rules to the data directory on first run."""
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    if os.path.exists(SEED_PATH):
        shutil.copy2(SEED_PATH, RULES_PATH)
    else:
        save_rules([])


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


def get_rule_category(description: str, rules: list[dict] = None) -> str:
    """Return the category from the matching vendor rule, or '' if none."""
    if rules is None:
        rules = load_rules()
    desc_upper = description.upper()
    for rule in rules:
        if rule["pattern"].upper() in desc_upper:
            return rule.get("category", "")
    return ""


def add_rule(pattern: str, vendor: str, category: str = ""):
    """Add a new rule at the top (most specific first)."""
    rules = load_rules()
    rules = [r for r in rules if r["pattern"].upper() != pattern.upper()]
    rule = {"pattern": pattern, "vendor": vendor}
    if category:
        rule["category"] = category
    rules.insert(0, rule)
    save_rules(rules)


def delete_rule(pattern: str):
    """Delete a rule by pattern."""
    rules = load_rules()
    rules = [r for r in rules if r["pattern"].upper() != pattern.upper()]
    save_rules(rules)


def update_rule(old_pattern: str, new_pattern: str, vendor: str, category: str = ""):
    """Update an existing rule."""
    rules = load_rules()
    rules = [r for r in rules if r["pattern"].upper() != old_pattern.upper()]
    rule = {"pattern": new_pattern, "vendor": vendor}
    if category:
        rule["category"] = category
    rules.insert(0, rule)
    save_rules(rules)