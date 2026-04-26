import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from models.lead import ResearchData, EmailSequence
from config import ANTHROPIC_API_KEY, TOKENROUTER_API_KEY, USE_TOKENROUTER, WRITING_MODEL


def _get_client() -> anthropic.Anthropic:
    if USE_TOKENROUTER:
        return anthropic.Anthropic(
            api_key=TOKENROUTER_API_KEY,
            base_url="https://tokenrouter.paleblueai.com",
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class OutreachWriter:
    def __init__(self):
        self.client = _get_client()

    def write_sequence(
        self,
        research: ResearchData,
        product_description: str,
        sender_name: str,
        sender_company: str,
        icp: str,
    ) -> EmailSequence:
        """Write a 3-touch personalized email sequence for a lead."""

        prompt = f"""You are an elite B2B sales copywriter. Write a 3-email cold outreach sequence that feels genuinely personal, not templated.

SELLER INFO:
- Name: {sender_name}
- Company: {sender_company}
- Product: {product_description}

PROSPECT INFO:
- Company: {research.company_name}
- Industry: {research.industry}
- Size: {research.size_estimate}
- Key contact: {research.key_person} ({research.key_person_title})
- Recent news: {'; '.join(research.recent_news[:2]) if research.recent_news else 'N/A'}
- Pain points: {'; '.join(research.pain_points[:3]) if research.pain_points else 'N/A'}
- Growth signals: {'; '.join(research.growth_signals[:2]) if research.growth_signals else 'N/A'}
- Summary: {research.raw_summary}

SEQUENCE RULES:
- Email 1: Short (5-7 lines). Reference ONE specific thing about their company. One clear value prop. Soft CTA (15-min call).
- Email 2 (3 days later): Follow up. Share a relevant result/case study. Different angle. Even shorter.
- Email 3 (7 days later): Breakup email. Humorous, respectful. Leave door open.
- NO buzzwords (synergy, leverage, disrupt). NO generic intros ("Hope this finds you well").
- Write to {research.key_person or 'the relevant decision maker'}.
- Subject lines must be specific and curiosity-inducing.

Return ONLY valid JSON:
{{
  "email_1_subject": "...",
  "email_1_body": "...",
  "email_2_subject": "...",
  "email_2_body": "...",
  "email_3_subject": "...",
  "email_3_body": "..."
}}"""

        response = self.client.messages.create(
            model=WRITING_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
                return EmailSequence(
                    email_1_subject=data.get("email_1_subject", ""),
                    email_1_body=data.get("email_1_body", ""),
                    email_2_subject=data.get("email_2_subject", ""),
                    email_2_body=data.get("email_2_body", ""),
                    email_3_subject=data.get("email_3_subject", ""),
                    email_3_body=data.get("email_3_body", ""),
                )
            except json.JSONDecodeError:
                pass

        return EmailSequence(
            email_1_subject="Following up",
            email_1_body=text,
        )
