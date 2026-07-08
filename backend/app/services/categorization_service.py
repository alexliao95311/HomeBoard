"""Rule-based transaction categorization for HOA finances."""

import re

# (keywords, category, confidence)
# First matching rule wins. Keywords are matched as substrings of lowercased description.
_RULES: list[tuple[list[str], str, float]] = [
    # Income
    (["assessment", "dues", "hoa fee", "homeowner fee", "unit fee"], "Assessment Income", 0.90),
    (["interest income", "interest earned", "dividend"], "Interest Income", 0.90),
    # Operating expenses
    (["landscap", "lawn", "mow", "irrigation", "garden", "tree trim"], "Landscaping", 0.90),
    (["pool", "spa", "aquatic"], "Pool Maintenance", 0.90),
    (["electric", "pge", "pg&e", "sdge", "sdg&e", "utility", "utilities", "water", "gas ", "sewage", "sewer"], "Utilities", 0.90),
    (["insurance", "insur"], "Insurance", 0.90),
    (["management", "mgmt", "property mgmt", "prop mgmt"], "Management Fees", 0.90),
    (["legal", "attorney", "counsel", "law office", "law firm"], "Legal", 0.90),
    (["gate", "security", "patrol", "guard"], "Security", 0.90),
    (["trash", "garbage", "waste", "recycl", "sanitation"], "Trash & Recycling", 0.90),
    (["pest", "termite", "extermina"], "Pest Control", 0.90),
    (["elevator", "lift service"], "Elevator", 0.90),
    (["janitorial", "cleaning", "clean", "sweep", "pressure wash"], "Janitorial", 0.85),
    (["repair", "maintenance", "maint ", "hvac", "plumb", "roof", "paint", "flooring"], "Repairs & Maintenance", 0.85),
    (["accounting", "audit", "cpa", "bookkeeping", "tax prep"], "Accounting & Audit", 0.85),
    (["bank service", "service charge", "bank fee", "nsf fee", "nsf charge", "overdraft", "wire fee", "monthly maintenance fee"], "Bank Fees", 0.90),
    # Reserve / transfers — checked before generic "transfer" / "service fee"
    (["reserve fund", "reserve contrib", "to reserve", "reserve transfer"], "Reserve Contribution", 0.90),
    (["transfer", "wire transfer", "ach transfer", "interfund"], "Transfer", 0.80),
]

_DEFAULT_CATEGORY = "Uncategorized"
_DEFAULT_CONFIDENCE = 0.0


def categorize(description: str) -> tuple[str, float]:
    """Return (category, confidence_score) for a transaction description."""
    lower = description.lower()
    for keywords, category, confidence in _RULES:
        if any(kw in lower for kw in keywords):
            return category, confidence
    return _DEFAULT_CATEGORY, _DEFAULT_CONFIDENCE


_VENDOR_DIGITS_RE = re.compile(r"\d{3,}")
_VENDOR_PUNCT_RE = re.compile(r"[^a-z0-9&\s]")
_VENDOR_WS_RE = re.compile(r"\s+")

# Words that describe the transaction rather than identify the payee — dropped
# so "Acme Painting Invoice #501" and "Acme Painting Autopay #502" key the same.
_VENDOR_NOISE_WORDS = {
    "invoice", "order", "payment", "autopay", "bill", "billing",
    "statement", "receipt", "ref", "reference", "no", "number",
    "check", "chk", "inc", "llc", "corp", "co", "ltd",
}


def vendor_key(description: str, vendor_name: str | None) -> str:
    """Normalize a transaction's vendor/description into a grouping key.

    Strips reference numbers, punctuation, and generic transaction words so
    that the same payee (e.g. "PG&E Electric #48291" and "PG&E Electric
    Autopay #77213") groups together for category reuse and AI-batch
    deduplication.
    """
    base = (vendor_name or description or "").lower()
    base = _VENDOR_DIGITS_RE.sub(" ", base)
    base = _VENDOR_PUNCT_RE.sub(" ", base)
    tokens = [t for t in _VENDOR_WS_RE.split(base) if t and t not in _VENDOR_NOISE_WORDS]
    return " ".join(tokens)


# Canonical category list (for frontend dropdowns and report grouping)
CATEGORIES: list[str] = [
    "Assessment Income",
    "Interest Income",
    "Landscaping",
    "Pool Maintenance",
    "Utilities",
    "Insurance",
    "Management Fees",
    "Legal",
    "Security",
    "Trash & Recycling",
    "Pest Control",
    "Elevator",
    "Janitorial",
    "Repairs & Maintenance",
    "Accounting & Audit",
    "Bank Fees",
    "Reserve Contribution",
    "Transfer",
    "Uncategorized",
]
