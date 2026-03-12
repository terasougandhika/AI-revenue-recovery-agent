"""
Seed the Knowledge Base with playbooks, past cases, and offer templates.
These are the documents the RAG agent retrieves during intervention generation.

Usage: python scripts/seed_knowledge_base.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
from loguru import logger
from src.database.models import insert_knowledge_doc
from src.rag.embeddings import embed_batch

load_dotenv()

KNOWLEDGE_DOCS = [

    # ─── PLAYBOOKS ────────────────────────────────────────────
    {
        "category": "playbook",
        "content": """SILENT CHURN PLAYBOOK — Re-engagement for Disengaging Customers

Situation: Customer has reduced login frequency by 50%+ over the past 7 days.

Step 1 (Day 1): Send personalized feature discovery email highlighting 1-2 features
the customer hasn't explored that align with their use case. Do NOT mention
the usage drop.

Step 2 (Day 3, if no response): Invite to a 15-minute product check-in call.
Frame as "we'd love to hear your feedback on recent updates."

Step 3 (Day 7, if still no response): Escalate to Customer Success Manager.
Offer a complimentary strategy session. For enterprise customers ($5k+ MRR),
offer executive sponsor outreach.

Success rate: 62% re-engagement within 14 days when Step 1 is executed within
24 hours of signal detection."""
    },

    {
        "category": "playbook",
        "content": """INCIDENT RESPONSE PLAYBOOK — Technical Failures and Errors

Situation: Customer has experienced 5+ errors in the last hour or a
critical system failure.

IMMEDIATE (within 1 hour):
- Acknowledge the issue proactively (don't wait for them to contact you)
- Assign a dedicated support engineer
- Send status update: "We are aware and actively working on a fix"

24-HOUR ACTIONS:
- Provide a root cause analysis (even preliminary)
- Offer a service credit proportional to downtime impact:
  * Starter plan: 1 week credit
  * Pro plan: 2 weeks credit
  * Enterprise plan: 1 month credit + executive call

FOLLOW-UP (3-5 days post-resolution):
- Share full incident post-mortem
- Explain preventive measures implemented
- Check satisfaction score

Critical: Enterprise customers ($5k+ MRR) with incidents must have
C-level acknowledgment email from your VP of Engineering or CTO within 4 hours."""
    },

    {
        "category": "playbook",
        "content": """SUPPORT TICKET ESCALATION PLAYBOOK — Multiple Unresolved Tickets

Situation: Customer has 3+ open tickets or a high-severity ticket
unresolved for 24+ hours.

Tiered Response by Plan:
STARTER: Ensure tickets are in queue. Send acknowledgment with expected
resolution time (48-72 hours for standard, 24 hours for high severity).

PRO: Assign a dedicated support engineer. Priority queue. Resolution
target: 24 hours standard, 4 hours high severity. Consider temporary
Slack channel for real-time communication on complex issues.

ENTERPRISE: Immediate dedicated engineer assignment. Proactive status
calls every 4 hours for critical issues. Direct CSM phone contact.
Consider on-site support for critical data issues.

Goodwill gestures after resolution:
- Extended free month of service
- Free onboarding/training session
- Access to beta features
- Dedicated CSM contact upgrade"""
    },

    # ─── PAST SUCCESSFUL CASES ────────────────────────────────
    {
        "category": "past_case",
        "content": """CASE STUDY: Data Export Failure — Enterprise Customer Retained

Customer: StellarTech (Enterprise, $12,000/month MRR)
Issue: Critical data export feature failing for 3 consecutive days.
Customer had filed 4 support tickets with no resolution.

Intervention used:
1. Immediate VP Engineering personal email acknowledging failure
2. Dedicated senior engineer assigned within 2 hours
3. Root cause identified: database timeout on large exports
4. Hotfix deployed within 6 hours
5. Offered 2-month service credit ($24,000 value)
6. Follow-up call with customer's CTO to review preventive measures

OUTCOME: Customer retained. Contract renewed 3 months early.
Customer became a reference customer.

KEY LEARNING: For enterprise customers, speed of personal acknowledgment
matters more than speed of technical fix. Human touch + accountability
= retention even after serious failures."""
    },

    {
        "category": "past_case",
        "content": """CASE STUDY: Silent Churn Re-engagement — Pro Plan Customer

Customer: BrightMedia Co (Pro, $3,200/month MRR)
Issue: Login frequency dropped from daily to once per week over 2 weeks.
No support tickets. No complaints.

Intervention used:
Email subject: "Sarah, here's something we built just for your team"
Content: Highlighted the new automated reporting feature (customer was
manually exporting data weekly — exactly the pain point this solved).
Included a 90-second Loom video walkthrough.
Offered a free 30-minute onboarding call to set it up together.

OUTCOME: Customer responded within 4 hours. Booked the onboarding call.
Within 1 week, daily active usage resumed. Customer expanded to 3
additional seats (+$960/month MRR increase).

KEY LEARNING: Silent churners often haven't discovered features that
solve their exact pain. Feature discovery emails with specific use-case
relevance are the highest-converting re-engagement tactic."""
    },

    {
        "category": "past_case",
        "content": """CASE STUDY: Multiple Tickets — Starter Plan Conversion

Customer: GrowFast Agency (Starter, $290/month MRR)
Issue: 5 support tickets in 2 weeks, all related to API integration confusion.
Customer clearly needed hands-on help beyond starter plan support level.

Intervention used:
1. Consolidated all 5 tickets into one with a single owner
2. Offered a free 45-minute API integration consultation call
3. During the call, showed how Pro plan included priority support
   and dedicated integration assistance
4. Presented Pro plan as "removing the friction they were experiencing"
5. Offered first 2 months of Pro at Starter pricing as migration incentive

OUTCOME: Customer upgraded to Pro plan ($3,100/month MRR — 10× increase).
All integration issues resolved within 1 week of upgrade.

KEY LEARNING: High ticket volume on lower-tier plans often signals a
product-plan fit mismatch, not product dissatisfaction. Upgrade offers
framed as "removing friction" (not as upsells) convert at 3× the rate."""
    },

    # ─── OFFER TEMPLATES ──────────────────────────────────────
    {
        "category": "offer_template",
        "content": """SERVICE CREDIT OFFER TEMPLATES by Plan Tier

STARTER PLAN ($0–$500/month):
- Standard: 1 week free (25% of monthly)
- High severity incident: 1 month free
- Extended outage: 2 months free

PRO PLAN ($500–$5,000/month):
- Standard: 2 weeks free
- High severity incident: 1 month free
- Extended outage: 2 months free + priority support upgrade for 3 months

ENTERPRISE PLAN ($5,000+/month):
- Standard: 1 month free
- High severity incident: 2 months free + dedicated CSM for 6 months
- Data loss or critical breach: 3 months free + contract SLA review
  + C-level apology call

IMPORTANT: Never offer credits as the FIRST communication.
Lead with acknowledgment + action plan. Credits come AFTER showing
you understand and are fixing the root cause.
Credits offered before demonstrating accountability are perceived
as "buying silence" and reduce trust."""
    },

    {
        "category": "offer_template",
        "content": """RE-ENGAGEMENT OFFER TEMPLATES — Silent Churn Prevention

For DISENGAGED users (login drop, feature underuse):

FEATURE DISCOVERY OFFER:
"We noticed you haven't explored [SPECIFIC FEATURE] yet — it's designed
exactly for [CUSTOMER USE CASE]. We'd love to give you a personal
walkthrough. Would a 20-minute session this week work?"

SUCCESS PLAN OFFER:
"We want to make sure you're getting maximum value from [PRODUCT].
Would you be open to a quick Success Review where we map your goals
to the features that best support them?"

BETA ACCESS OFFER (for engaged power users who've gone quiet):
"As one of our most active customers, we'd love your feedback on
[NEW FEATURE] before it launches. Interested in early access?"

ROI REVIEW OFFER (for business/enterprise customers):
"We'd like to show you the measurable impact [PRODUCT] has had on
your team's [METRIC]. Can we schedule a 30-minute ROI review call?"

Conversion rates (internal benchmarks):
- Feature walkthrough offer: 34% acceptance
- Success plan offer: 28% acceptance
- Beta access offer: 52% acceptance (for qualifying customers)
- ROI review offer: 41% acceptance (enterprise only)"""
    },

    # ─── PRODUCT KNOWLEDGE ────────────────────────────────────
    {
        "category": "product_doc",
        "content": """COMMON TECHNICAL ISSUES AND RESOLUTIONS

Data Export Failures:
Root cause: Usually database query timeout on large datasets (>100K rows)
Quick fix: Use filtered exports (date range, specific fields)
Permanent fix: Enable async export with email notification (Settings > Exports)
Workaround while fixing: CSV export via API with pagination

API Rate Limit Errors:
Root cause: Customer exceeding plan-tier limits
Quick fix: Implement exponential backoff in client code
Upgrade path: Pro plan has 10× the rate limits of Starter
Emergency: Contact support for temporary rate limit increase

Dashboard Loading Timeout:
Root cause: Complex dashboard with too many real-time widgets
Quick fix: Reduce time range from 90 days to 30 days
Optimization: Use "snapshot" mode for historical dashboards
Browser fix: Clear cache + try Chrome/Firefox (not Safari)

Authentication Issues:
Root cause 1: SSO misconfiguration (most common for enterprise)
Root cause 2: Session token expiration settings too aggressive
Root cause 3: IP allowlist blocking legitimate users
Fix: Check Settings > Security > Session Configuration"""
    },
]


def seed():
    logger.info(f"Seeding {len(KNOWLEDGE_DOCS)} knowledge base documents...")

    # Embed all documents in one batch (much faster than one-by-one)
    texts    = [doc["content"] for doc in KNOWLEDGE_DOCS]
    logger.info("Generating embeddings (this may take a moment)...")
    embeddings = embed_batch(texts)

    for i, (doc, embedding) in enumerate(zip(KNOWLEDGE_DOCS, embeddings)):
        doc_id = insert_knowledge_doc(
            content   = doc["content"],
            category  = doc["category"],
            embedding = embedding,
        )
        logger.success(f"[{i+1}/{len(KNOWLEDGE_DOCS)}] Seeded: "
                       f"category={doc['category']} | id={doc_id}")

    logger.success(
        f"\n✅ Knowledge base seeded with {len(KNOWLEDGE_DOCS)} documents!\n"
        f"   Categories: playbooks, past_cases, offer_templates, product_docs\n"
        f"   The RAG agent will search these during intervention generation."
    )


if __name__ == "__main__":
    seed()
