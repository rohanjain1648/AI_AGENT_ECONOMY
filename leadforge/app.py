import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import threading
import queue
import time
from agents.orchestrator import LeadForgeOrchestrator
from models.lead import Lead, CampaignResult

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LeadForge AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .main { background: #0f0f13; }
  .block-container { padding-top: 1.5rem; }
  h1 { font-size: 2.6rem !important; font-weight: 800 !important; }
  .score-pill {
      display: inline-block;
      padding: 2px 12px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.85rem;
  }
  .score-high  { background: #16a34a22; color: #4ade80; border: 1px solid #16a34a; }
  .score-mid   { background: #d9770622; color: #fb923c; border: 1px solid #d97706; }
  .score-low   { background: #dc262622; color: #f87171; border: 1px solid #dc2626; }
  .email-card {
      background: #1a1a24;
      border: 1px solid #2a2a3a;
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 0.75rem;
  }
  .tag {
      display: inline-block;
      background: #1e293b;
      color: #94a3b8;
      border-radius: 4px;
      padding: 1px 8px;
      font-size: 0.75rem;
      margin: 2px;
  }
  .metric-card {
      background: #1a1a24;
      border: 1px solid #2a2a3a;
      border-radius: 8px;
      padding: 1rem 1.5rem;
      text-align: center;
  }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# ⚡ LeadForge")
st.markdown("**Autonomous B2B Lead Research & Personalized Outreach Agent**")
st.markdown("---")


# ── Sidebar — configuration ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        help="Get yours at console.anthropic.com",
    )
    tokenrouter_key = st.text_input(
        "TokenRouter API Key (optional)",
        type="password",
        value=os.getenv("TOKENROUTER_API_KEY", ""),
        help="From PaleBlueDot.AI — gives $200 free credits",
    )
    st.markdown("---")
    st.markdown("### Gmail Drafts")
    gmail_enabled = st.checkbox("Enable Gmail Drafts", value=False)
    recipient_email = ""
    if gmail_enabled:
        recipient_email = st.text_input("Recipient email for drafts", placeholder="prospect@company.com")
        st.info("Place your `credentials.json` from Google Cloud Console in the leadforge/ folder.")
    st.markdown("---")
    st.markdown("### Advanced")
    score_threshold = st.slider("Minimum lead score", 0, 90, 50)
    num_leads = st.slider("Leads to qualify", 1, 10, 5)


# ── Apply keys to env ─────────────────────────────────────────────────────────
if api_key:
    os.environ["ANTHROPIC_API_KEY"] = api_key
if tokenrouter_key:
    os.environ["TOKENROUTER_API_KEY"] = tokenrouter_key


# ── Main form ─────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("### Your Product")
    product_description = st.text_area(
        "What do you sell?",
        placeholder="e.g., AI-powered inventory management software that reduces stockouts by 35% for mid-market retailers.",
        height=100,
    )
    sender_name = st.text_input("Your name", placeholder="Alex Johnson")
    sender_company = st.text_input("Your company", placeholder="Acme SaaS Inc.")

with col_right:
    st.markdown("### Ideal Customer Profile")
    icp_industry = st.text_input(
        "Target industry",
        placeholder="e.g., E-commerce, Healthcare, Construction",
    )
    icp_size = st.selectbox(
        "Company size",
        ["1-50", "50-200", "200-500", "500-2000", "2000+"],
        index=2,
    )
    icp_title = st.text_input(
        "Decision maker title",
        placeholder="e.g., VP of Operations, CTO, Head of Supply Chain",
    )

st.markdown("")
run_button = st.button("🚀 Launch LeadForge", type="primary", use_container_width=True)


# ── Lead card renderer (must be defined before run_button block) ──────────────
def _render_leads(leads):
    for lead in leads:
        with st.expander(
            f"{'🟢' if lead.score >= 70 else '🟡' if lead.score >= 50 else '🔴'}  "
            f"**{lead.company_name}** — Score: {lead.score}/100",
            expanded=lead.score >= 70,
        ):
            tab_research, tab_outreach = st.tabs(["🔍 Research", "✉️ Email Sequence"])

            with tab_research:
                r = lead.research
                if r:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Website:** {r.website or 'N/A'}")
                        st.markdown(f"**Industry:** {r.industry or 'N/A'}")
                        st.markdown(f"**Size:** {r.size_estimate or 'N/A'}")
                        st.markdown(f"**Key Contact:** {r.key_person} — {r.key_person_title}" if r.key_person else "**Key Contact:** N/A")
                    with col_b:
                        if r.pain_points:
                            st.markdown("**Pain Points:**")
                            for p in r.pain_points:
                                st.markdown(f"- {p}")
                        if r.growth_signals:
                            st.markdown("**Growth Signals:**")
                            for g in r.growth_signals:
                                st.markdown(f"- {g}")
                    if r.recent_news:
                        st.markdown("**Recent News:**")
                        for n in r.recent_news:
                            st.markdown(f"- {n}")
                    if r.raw_summary:
                        st.success(f"**Why this lead:** {r.raw_summary}")
                    st.caption(f"Score reasoning: {lead.score_reasoning}")

            with tab_outreach:
                o = lead.outreach
                if o:
                    if o.email_1_subject:
                        st.markdown("**Email 1 — Day 1**")
                        st.markdown(f"Subject: `{o.email_1_subject}`")
                        st.text_area("", o.email_1_body, height=180, key=f"e1_{lead.company_name}", label_visibility="collapsed")
                    if o.email_2_subject:
                        st.markdown("**Email 2 — Day 3**")
                        st.markdown(f"Subject: `{o.email_2_subject}`")
                        st.text_area("", o.email_2_body, height=150, key=f"e2_{lead.company_name}", label_visibility="collapsed")
                    if o.email_3_subject:
                        st.markdown("**Email 3 — Day 7**")
                        st.markdown(f"Subject: `{o.email_3_subject}`")
                        st.text_area("", o.email_3_body, height=130, key=f"e3_{lead.company_name}", label_visibility="collapsed")
                    if lead.gmail_draft_ids:
                        st.success(f"✅ {len(lead.gmail_draft_ids)} drafts created in Gmail")
                else:
                    st.warning("Outreach not yet generated.")


# ── Results area ──────────────────────────────────────────────────────────────
if run_button:
    # Validate
    missing = []
    if not (api_key or tokenrouter_key):
        missing.append("API key (Anthropic or TokenRouter)")
    if not product_description:
        missing.append("Product description")
    if not icp_industry:
        missing.append("Target industry")
    if not sender_name:
        missing.append("Your name")
    if not sender_company:
        missing.append("Your company")

    if missing:
        st.error(f"Please fill in: {', '.join(missing)}")
        st.stop()

    # ── Live log area ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🤖 Agent Activity")
    log_container = st.empty()
    progress_bar = st.progress(0)

    # ── Results placeholders ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Qualified Leads")
    results_container = st.container()

    # ── Run orchestrator in thread ────────────────────────────────────────────
    log_lines = []
    completed_leads = []
    result_holder = [None]
    error_holder = [None]
    status_queue = queue.Queue()
    lead_queue = queue.Queue()

    def _run():
        try:
            orch = LeadForgeOrchestrator()
            if gmail_enabled:
                orch.setup_gmail()

            def on_status(msg):
                status_queue.put(("status", msg))

            def on_lead(lead):
                status_queue.put(("lead", lead))

            result = orch.run(
                product_description=product_description,
                icp_industry=icp_industry,
                icp_size=icp_size,
                icp_title=icp_title,
                sender_name=sender_name,
                sender_company=sender_company,
                recipient_email=recipient_email,
                num_leads=num_leads,
                score_threshold=score_threshold,
                status_callback=on_status,
                lead_callback=on_lead,
            )
            result_holder[0] = result
        except Exception as e:
            error_holder[0] = str(e)
        finally:
            status_queue.put(("done", None))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # ── Poll queue and update UI ──────────────────────────────────────────────
    processed_leads = 0
    done = False
    lead_slots = []

    while not done:
        try:
            while True:
                msg_type, msg_data = status_queue.get_nowait()
                if msg_type == "done":
                    done = True
                    break
                elif msg_type == "status":
                    log_lines.append(msg_data)
                    log_text = "\n".join(log_lines[-30:])
                    log_container.code(log_text, language=None)
                elif msg_type == "lead":
                    completed_leads.append(msg_data)
                    processed_leads += 1
                    progress_bar.progress(min(processed_leads / num_leads, 1.0))
        except queue.Empty:
            pass

        # Render any new completed leads in real time
        if completed_leads:
            with results_container:
                _render_leads(completed_leads if not done else completed_leads)

        if not done:
            time.sleep(0.3)

    thread.join()
    progress_bar.progress(1.0)

    if error_holder[0]:
        st.error(f"Error: {error_holder[0]}")
        st.stop()

    final_result: CampaignResult = result_holder[0]
    if not final_result:
        st.error("No results returned.")
        st.stop()

    # Final render
    with results_container:
        _render_leads(final_result.leads)

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Campaign Summary")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Companies Researched", final_result.total_researched)
    with m2:
        st.metric("Leads Qualified", final_result.total_qualified)
    with m3:
        avg_score = (
            sum(l.score for l in final_result.leads) // len(final_result.leads)
            if final_result.leads else 0
        )
        st.metric("Avg Lead Score", f"{avg_score}/100")
    with m4:
        st.metric("Gmail Drafts Created", final_result.drafts_created)

    if final_result.campaign_summary:
        st.info(final_result.campaign_summary)


