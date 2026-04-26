import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
import json
from typing import List, Optional, Callable
from models.lead import Lead, CampaignResult
from agents.researcher import ResearchAgent
from agents.writer import OutreachWriter
from utils.search import search_companies
from utils.gmail import GmailClient
from config import (
    ANTHROPIC_API_KEY, TOKENROUTER_API_KEY, USE_TOKENROUTER,
    RESEARCH_MODEL, GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE,
)


def _get_client() -> anthropic.Anthropic:
    if USE_TOKENROUTER:
        return anthropic.Anthropic(
            api_key=TOKENROUTER_API_KEY,
            base_url="https://tokenrouter.paleblueai.com",
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class LeadForgeOrchestrator:
    """
    Master orchestrator — runs the full pipeline:
    Discover → Research → Score → Write → Draft
    """

    def __init__(self):
        self.researcher = ResearchAgent()
        self.writer = OutreachWriter()
        self.gmail = GmailClient(GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE)
        self.client = _get_client()
        self._gmail_ready = False

    def setup_gmail(self) -> bool:
        self._gmail_ready = self.gmail.authenticate()
        return self._gmail_ready

    def _discover_companies(
        self,
        industry: str,
        size: str,
        icp_description: str,
        num_leads: int,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> List[str]:
        """Use Claude to intelligently generate company names to research."""
        if status_callback:
            status_callback("Identifying target companies...")

        prompt = f"""You are a B2B sales prospecting expert. Generate a list of {num_leads * 2} specific, real company names that match this ICP.

Industry: {industry}
Company size: {size} employees
ICP description: {icp_description}

Rules:
- Return ONLY real companies that exist
- Mix well-known and mid-market companies
- Vary by geography (US, EU, APAC)
- Return JSON array of strings: ["Company A", "Company B", ...]
- No explanations, just the JSON array"""

        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                companies = json.loads(text[start:end])
                return [str(c) for c in companies[: num_leads * 2]]
            except json.JSONDecodeError:
                pass

        # Fallback to web search
        return search_companies(industry, size, icp_description, num_leads)

    def run(
        self,
        product_description: str,
        icp_industry: str,
        icp_size: str,
        icp_title: str,
        sender_name: str,
        sender_company: str,
        recipient_email: str,
        num_leads: int = 5,
        score_threshold: int = 50,
        status_callback: Optional[Callable[[str], None]] = None,
        lead_callback: Optional[Callable[[Lead], None]] = None,
    ) -> CampaignResult:
        """
        Full pipeline. Calls status_callback(msg) for progress updates.
        Calls lead_callback(lead) each time a lead is fully processed.
        """
        result = CampaignResult()
        icp = f"{icp_title} at {icp_industry} companies with {icp_size} employees"

        # Step 1: Discover companies
        company_names = self._discover_companies(
            icp_industry, icp_size, icp, num_leads, status_callback
        )
        result.total_researched = len(company_names)

        if status_callback:
            status_callback(f"Found {len(company_names)} candidate companies. Starting deep research...")

        # Step 2: Research + score + write for each company
        qualified_leads: List[Lead] = []
        for i, company_name in enumerate(company_names):
            if status_callback:
                status_callback(f"\n[{i+1}/{len(company_names)}] {company_name}")

            # Research
            research_data = self.researcher.research_company(
                company_name=company_name,
                product_description=product_description,
                icp=icp,
                status_callback=status_callback,
            )

            # Score
            score, reasoning = self.researcher.score_lead(research_data, product_description)
            lead = Lead(
                company_name=company_name,
                score=score,
                score_reasoning=reasoning,
                research=research_data,
            )

            if status_callback:
                status_callback(f"  Score: {score}/100 — {reasoning}")

            if score < score_threshold:
                if status_callback:
                    status_callback(f"  Skipping (below threshold of {score_threshold})")
                continue

            # Write outreach
            if status_callback:
                status_callback(f"  Writing personalized outreach sequence...")
            lead.outreach = self.writer.write_sequence(
                research=research_data,
                product_description=product_description,
                sender_name=sender_name,
                sender_company=sender_company,
                icp=icp,
            )

            # Gmail drafts
            if self._gmail_ready and recipient_email and lead.outreach:
                if status_callback:
                    status_callback(f"  Creating Gmail drafts...")
                emails_to_draft = []
                if lead.outreach.email_1_subject:
                    emails_to_draft.append({
                        "to": recipient_email,
                        "subject": f"[{company_name}] {lead.outreach.email_1_subject}",
                        "body": lead.outreach.email_1_body,
                    })
                if lead.outreach.email_2_subject:
                    emails_to_draft.append({
                        "to": recipient_email,
                        "subject": f"[{company_name}] {lead.outreach.email_2_subject}",
                        "body": lead.outreach.email_2_body,
                    })
                if lead.outreach.email_3_subject:
                    emails_to_draft.append({
                        "to": recipient_email,
                        "subject": f"[{company_name}] {lead.outreach.email_3_subject}",
                        "body": lead.outreach.email_3_body,
                    })
                draft_ids = self.gmail.create_multiple_drafts(emails_to_draft)
                lead.gmail_draft_ids = draft_ids
                result.drafts_created += len(draft_ids)

            qualified_leads.append(lead)
            result.total_qualified += 1

            if lead_callback:
                lead_callback(lead)

            if len(qualified_leads) >= num_leads:
                break

        # Sort by score desc
        qualified_leads.sort(key=lambda x: x.score, reverse=True)
        result.leads = qualified_leads

        # Generate campaign summary
        if status_callback:
            status_callback("\nGenerating campaign summary...")
        result.campaign_summary = self._generate_summary(result, product_description)

        return result

    def _generate_summary(self, result: CampaignResult, product: str) -> str:
        company_list = "\n".join(
            f"- {l.company_name} (score {l.score}): {l.score_reasoning}"
            for l in result.leads
        )
        prompt = f"""Write a 3-sentence executive summary of this B2B lead gen campaign.

Product: {product}
Leads qualified: {result.total_qualified} of {result.total_researched} researched
Top leads:
{company_list}

Be specific. Mention the top 2 companies and why they stand out. End with recommended next steps."""

        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
