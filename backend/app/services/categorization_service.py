"""Rule-based transaction categorization for HOA finances."""

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
