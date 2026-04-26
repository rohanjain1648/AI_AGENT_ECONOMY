import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from typing import List, Optional, Callable
from models.lead import ResearchData
from utils.search import web_search
from config import ANTHROPIC_API_KEY, TOKENROUTER_API_KEY, USE_TOKENROUTER, RESEARCH_MODEL


def _get_client() -> anthropic.Anthropic:
    if USE_TOKENROUTER:
        return anthropic.Anthropic(
            api_key=TOKENROUTER_API_KEY,
            base_url="https://tokenrouter.paleblueai.com",
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


RESEARCH_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for information about a company or topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Number of results (1-8)", "default": 5},
            },
            "required": ["query"],
        },
    }
]


class ResearchAgent:
    def __init__(self):
        self.client = _get_client()

    def _run_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "web_search":
            results = web_search(tool_input["query"], tool_input.get("max_results", 5))
            return json.dumps(results, indent=2)
        return "Tool not found"

    def research_company(
        self,
        company_name: str,
        product_description: str,
        icp: str,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> ResearchData:
        """Use Claude with web_search tool to deeply research a company."""

        if status_callback:
            status_callback(f"Researching {company_name}...")

        system_prompt = """You are an expert B2B sales researcher. Given a company name, research it thoroughly using web search.
Extract actionable intelligence for a sales rep: recent news, pain points, growth signals, tech stack, key contacts.
Always search at least 3-4 times to gather comprehensive data. Be specific and factual."""

        user_prompt = f"""Research the company: **{company_name}**

We sell: {product_description}
Our ICP: {icp}

Search for:
1. What {company_name} does, their size, industry, and website
2. Recent news, funding, or growth signals (last 12 months)
3. Likely pain points relevant to what we sell
4. Their tech stack or tools they use
5. Key decision makers (CEO, VP/Head of Operations/Technology)

After researching, return a JSON object with this exact structure:
{{
  "company_name": "...",
  "website": "...",
  "industry": "...",
  "size_estimate": "...",
  "recent_news": ["...", "..."],
  "pain_points": ["...", "..."],
  "tech_stack": ["...", "..."],
  "growth_signals": ["...", "..."],
  "key_person": "...",
  "key_person_title": "...",
  "raw_summary": "2-3 sentence summary of why this is a good lead"
}}"""

        messages = [{"role": "user", "content": user_prompt}]

        # Agentic loop
        for _ in range(8):  # max 8 turns
            response = self.client.messages.create(
                model=RESEARCH_MODEL,
                max_tokens=2048,
                system=system_prompt,
                tools=RESEARCH_TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract JSON from final response
                for block in response.content:
                    if hasattr(block, "text"):
                        text = block.text
                        # Find JSON in the response
                        start = text.find("{")
                        end = text.rfind("}") + 1
                        if start != -1 and end > start:
                            try:
                                data = json.loads(text[start:end])
                                return ResearchData(
                                    company_name=data.get("company_name", company_name),
                                    website=data.get("website", ""),
                                    industry=data.get("industry", ""),
                                    size_estimate=data.get("size_estimate", ""),
                                    recent_news=data.get("recent_news", []),
                                    pain_points=data.get("pain_points", []),
                                    tech_stack=data.get("tech_stack", []),
                                    growth_signals=data.get("growth_signals", []),
                                    key_person=data.get("key_person", ""),
                                    key_person_title=data.get("key_person_title", ""),
                                    raw_summary=data.get("raw_summary", ""),
                                )
                            except json.JSONDecodeError:
                                pass
                break

            # Handle tool use
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if status_callback:
                            status_callback(f"  🔍 Searching: {block.input.get('query', '')[:60]}...")
                        result = self._run_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "user", "content": tool_results})

        # Fallback if parsing failed
        return ResearchData(company_name=company_name, raw_summary="Research incomplete")

    def score_lead(self, research: ResearchData, product_description: str) -> tuple[int, str]:
        """Score a lead 0-100 based on research data."""
        prompt = f"""Given this research about a potential B2B lead, score them from 0-100 on their fit and buying likelihood.

Product we sell: {product_description}

Company research:
- Company: {research.company_name}
- Industry: {research.industry}
- Size: {research.size_estimate}
- Pain points: {', '.join(research.pain_points)}
- Growth signals: {', '.join(research.growth_signals)}
- Summary: {research.raw_summary}

Respond with JSON only:
{{"score": <0-100>, "reasoning": "<1-2 sentences why>"}}

Score high (70-100) if: strong pain point match, growth signals, right size.
Score low (0-40) if: wrong industry, no clear pain points, or too small/large."""

        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1:
            try:
                data = json.loads(text[start:end])
                return int(data.get("score", 50)), data.get("reasoning", "")
            except Exception:
                pass
        return 50, "Could not score"
