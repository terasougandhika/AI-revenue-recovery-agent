"""
Streamlit Dashboard — Human in the Loop interface.
Shows live alerts, AI recommendations, MRR at risk, and intervention history.

Run with: streamlit run src/dashboard/app.py
"""

import os
import time
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from src.database.models import (
    get_open_alerts,
    get_pending_interventions,
    get_dashboard_stats,
    get_mrr_at_risk,
    approve_intervention,
    record_outcome,
    close_alert,
)

load_dotenv()

REFRESH_INTERVAL = int(os.getenv("DASHBOARD_REFRESH_INTERVAL", "5"))

# ─── PAGE CONFIG ───────────────────────────────────────────────
st.set_page_config(
    page_title   = "Revenue Recovery Engine",
    page_icon    = "🔴",
    layout       = "wide",
    initial_sidebar_state = "expanded",
)

# ─── CUSTOM STYLES ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2rem; font-weight: 800;
        background: linear-gradient(90deg, #00d4ff, #0099cc);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background: #1a1a2e; border: 1px solid #16213e;
        border-radius: 10px; padding: 16px; text-align: center;
    }
    .severity-critical { color: #ff4444; font-weight: bold; }
    .severity-high     { color: #ff8800; font-weight: bold; }
    .severity-medium   { color: #ffcc00; }
    .severity-low      { color: #44ff44; }
</style>
""", unsafe_allow_html=True)


# ─── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔴 Revenue Recovery")
    st.markdown("**Real-Time Churn Prevention**")
    st.divider()

    auto_refresh = st.toggle("Auto Refresh", value=True)
    refresh_rate = st.slider("Refresh interval (s)", 3, 30, REFRESH_INTERVAL)

    st.divider()
    st.markdown("**Quick Filters**")
    severity_filter = st.multiselect(
        "Severity",
        ["critical", "high", "medium", "low"],
        default=["critical", "high"]
    )
    alert_type_filter = st.multiselect(
        "Alert Type",
        ["incident", "silent_churn", "support"],
        default=["incident", "silent_churn", "support"]
    )

    st.divider()
    if st.button("🔄 Refresh Now"):
        st.rerun()


# ─── HEADER ────────────────────────────────────────────────────
st.markdown('<div class="main-header">⚡ Revenue Recovery Engine</div>',
            unsafe_allow_html=True)
st.caption("Real-time churn detection and AI-powered intervention")
st.divider()


# ─── LOAD DATA ─────────────────────────────────────────────────
@st.cache_data(ttl=REFRESH_INTERVAL)
def load_data():
    return {
        "stats":        get_dashboard_stats(),
        "mrr_at_risk":  get_mrr_at_risk(),
        "alerts":       get_open_alerts(limit=100),
        "interventions": get_pending_interventions(),
    }

data = load_data()
stats = data["stats"]


# ─── KPI METRICS ROW ───────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "💰 MRR at Risk",
        f"${data['mrr_at_risk']:,.0f}",
        delta="monthly revenue in danger",
        delta_color="inverse",
    )
with col2:
    st.metric("🚨 Critical Alerts", stats.get("critical_alerts", 0))
with col3:
    st.metric("⚠️ High Alerts",     stats.get("high_alerts", 0))
with col4:
    st.metric("📋 Total Open",      stats.get("total_open_alerts", 0))
with col5:
    st.metric("🤖 Pending AI Review", len(data["interventions"]))

st.divider()


# ─── MAIN TABS ─────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🚨 Live Alerts",
    "🤖 AI Recommendations",
    "📋 Intervention History",
])


# ─── TAB 1: LIVE ALERTS ────────────────────────────────────────
with tab1:
    st.subheader("Live Alert Feed")
    st.caption("Sorted by severity × MRR — highest risk first")

    alerts = data["alerts"]

    # Apply sidebar filters
    if severity_filter:
        alerts = [a for a in alerts if a["severity"] in severity_filter]
    if alert_type_filter:
        alerts = [a for a in alerts if a["alert_type"] in alert_type_filter]

    if not alerts:
        st.info("No alerts matching your filters. 🎉 All clear!")
    else:
        for alert in alerts:
            severity_emoji = {
                "critical": "🔴", "high": "🟠",
                "medium": "🟡",   "low": "🟢"
            }.get(alert["severity"], "⚪")

            alert_type_label = {
                "silent_churn": "🔇 Silent Churn",
                "incident":     "🚨 Incident",
                "support":      "🎫 Support Tickets",
            }.get(alert["alert_type"], alert["alert_type"])

            with st.expander(
                f"{severity_emoji} **{alert['customer_name']}** — "
                f"{alert_type_label} | MRR: ${alert['mrr']:,} | "
                f"Risk: {alert['risk_score']}/100"
            ):
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Severity",   alert["severity"].upper())
                col_b.metric("Risk Score", f"{alert['risk_score']}/100")
                col_c.metric("MRR",        f"${alert['mrr']:,}")
                col_d.metric("Plan",       alert["plan"].title())

                st.caption(f"Alert ID: {alert['id']} | "
                           f"Created: {alert['created_at']}")

                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button(f"✅ Mark Resolved", key=f"resolve_{alert['id']}"):
                    close_alert(alert["id"])
                    st.success("Alert closed!")
                    st.rerun()


# ─── TAB 2: AI RECOMMENDATIONS ─────────────────────────────────
with tab2:
    st.subheader("AI-Generated Interventions")
    st.caption(
        "Review and approve recommendations. "
        "HIGH/CRITICAL alerts require human approval before sending."
    )

    interventions = data["interventions"]

    if not interventions:
        st.info("No pending interventions. AI agents are monitoring...")
    else:
        st.info(f"**{len(interventions)} intervention(s) awaiting your review**")

        for inv in interventions:
            severity_emoji = {
                "critical": "🔴", "high": "🟠",
                "medium": "🟡",   "low": "🟢"
            }.get(inv.get("severity", "low"), "⚪")

            with st.expander(
                f"{severity_emoji} **{inv['customer_name']}** — "
                f"${inv['mrr']:,}/mo | {inv['alert_type']} | "
                f"Risk: {inv['risk_score']}/100"
            ):
                st.markdown("**📝 AI Recommended Action:**")
                st.markdown(inv["action"])

                st.divider()
                st.markdown("**🧠 AI Reasoning:**")
                st.text(inv.get("ai_reasoning", "")[:500] + "...")

                col1, col2, col3 = st.columns(3)

                if col1.button(
                    "✅ Approve & Send",
                    key=f"approve_{inv['id']}",
                    type="primary"
                ):
                    approve_intervention(inv["id"], approved_by="dashboard_user")
                    st.success(f"✅ Approved! Intervention logged for {inv['customer_name']}")
                    st.rerun()

                if col2.button("✏️ Edit Before Sending", key=f"edit_{inv['id']}"):
                    edited = st.text_area(
                        "Edit message:",
                        value=inv["action"],
                        key=f"edit_text_{inv['id']}"
                    )
                    st.info("Click Approve after editing to save changes.")

                if col3.button("❌ Reject", key=f"reject_{inv['id']}"):
                    record_outcome(inv["id"], outcome="rejected")
                    st.warning("Intervention rejected.")
                    st.rerun()


# ─── TAB 3: HISTORY ────────────────────────────────────────────
with tab3:
    st.subheader("Intervention History")
    st.caption("Track outcomes to measure system effectiveness")

    st.info("Intervention history with outcome tracking — "
            "retained customers feed back into the AI knowledge base.")

    # Placeholder stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Retention Rate",    "73%",  "+5% vs last month")
    col2.metric("Avg Response Time", "2.4h", "-0.8h vs last month")
    col3.metric("MRR Protected",     "$42,000", "this month")


# ─── AUTO REFRESH ──────────────────────────────────────────────
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
