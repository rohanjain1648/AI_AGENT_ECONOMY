from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ResearchData:
    company_name: str
    website: str = ""
    industry: str = ""
    size_estimate: str = ""
    recent_news: List[str] = field(default_factory=list)
    pain_points: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    growth_signals: List[str] = field(default_factory=list)
    key_person: str = ""
    key_person_title: str = ""
    raw_summary: str = ""


@dataclass
class EmailSequence:
    email_1_subject: str = ""
    email_1_body: str = ""
    email_2_subject: str = ""
    email_2_body: str = ""
    email_3_subject: str = ""
    email_3_body: str = ""


@dataclass
class Lead:
    company_name: str
    score: int = 0
    score_reasoning: str = ""
    research: Optional[ResearchData] = None
    outreach: Optional[EmailSequence] = None
    gmail_draft_ids: List[str] = field(default_factory=list)


@dataclass
class CampaignResult:
    leads: List[Lead] = field(default_factory=list)
    total_researched: int = 0
    total_qualified: int = 0
    drafts_created: int = 0
    campaign_summary: str = ""
