"""
Sample customer data for event generation.
In production, this would be pulled from your CRM/database.
"""

CUSTOMERS = [
    # Enterprise tier — highest MRR, most critical to retain
    {"id": "C-001", "name": "Acme Corp",         "mrr": 8500,  "plan": "enterprise", "industry": "fintech"},
    {"id": "C-002", "name": "TechFlow Inc",       "mrr": 12000, "plan": "enterprise", "industry": "saas"},
    {"id": "C-003", "name": "GlobalData Ltd",     "mrr": 6200,  "plan": "enterprise", "industry": "analytics"},
    {"id": "C-004", "name": "Nexus Systems",      "mrr": 9800,  "plan": "enterprise", "industry": "security"},
    {"id": "C-005", "name": "Vertex AI Labs",     "mrr": 15000, "plan": "enterprise", "industry": "ai"},

    # Pro tier — mid MRR
    {"id": "C-006", "name": "Bright Solutions",  "mrr": 2400,  "plan": "pro",        "industry": "marketing"},
    {"id": "C-007", "name": "Orbit Software",    "mrr": 3100,  "plan": "pro",        "industry": "devtools"},
    {"id": "C-008", "name": "PulseHR",           "mrr": 1800,  "plan": "pro",        "industry": "hr"},
    {"id": "C-009", "name": "Cascade Analytics","mrr": 4200,   "plan": "pro",        "industry": "analytics"},
    {"id": "C-010", "name": "Streamline Ops",    "mrr": 2900,  "plan": "pro",        "industry": "operations"},
    {"id": "C-011", "name": "Apex Commerce",     "mrr": 3600,  "plan": "pro",        "industry": "ecommerce"},
    {"id": "C-012", "name": "Relay Networks",    "mrr": 1950,  "plan": "pro",        "industry": "telecom"},
    {"id": "C-013", "name": "Zenith Retail",     "mrr": 2750,  "plan": "pro",        "industry": "retail"},
    {"id": "C-014", "name": "Nova Health",       "mrr": 5100,  "plan": "pro",        "industry": "healthtech"},
    {"id": "C-015", "name": "Forge Payments",    "mrr": 4800,  "plan": "pro",        "industry": "fintech"},

    # Starter tier — lower MRR, higher churn risk
    {"id": "C-016", "name": "Pixel Studio",      "mrr": 490,   "plan": "starter",    "industry": "creative"},
    {"id": "C-017", "name": "CodeCraft Dev",      "mrr": 290,   "plan": "starter",    "industry": "devtools"},
    {"id": "C-018", "name": "Mint Logistics",     "mrr": 390,   "plan": "starter",    "industry": "logistics"},
    {"id": "C-019", "name": "Solar Tracker",      "mrr": 190,   "plan": "starter",    "industry": "cleantech"},
    {"id": "C-020", "name": "Rapid Recruit",      "mrr": 450,   "plan": "starter",    "industry": "hr"},
]


def get_customer_by_id(customer_id: str) -> dict | None:
    return next((c for c in CUSTOMERS if c["id"] == customer_id), None)


def get_customers_by_plan(plan: str) -> list[dict]:
    return [c for c in CUSTOMERS if c["plan"] == plan]


def get_high_value_customers(min_mrr: int = 3000) -> list[dict]:
    return [c for c in CUSTOMERS if c["mrr"] >= min_mrr]
