import time
from typing import List, Dict
from duckduckgo_search import DDGS


def web_search(query: str, max_results: int = 5) -> List[Dict]:
    """Search the web and return list of {title, url, snippet} dicts."""
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        time.sleep(0.5)  # polite delay
    except Exception as e:
        results.append({"title": "Search error", "url": "", "snippet": str(e)})
    return results


def search_companies(industry: str, size: str, icp_description: str, num: int = 8) -> List[str]:
    """Return a list of company names matching the ICP."""
    queries = [
        f"top {industry} companies {size} employees B2B",
        f"{industry} startups growing companies {size} staff",
        f"best {industry} companies to work with {icp_description[:60]}",
    ]
    company_names = []
    seen = set()
    for query in queries:
        results = web_search(query, max_results=6)
        for r in results:
            # Extract company names from titles heuristically
            title = r["title"].split("|")[0].split("-")[0].strip()
            if title and title not in seen and len(title) < 60:
                seen.add(title)
                company_names.append(title)
            if len(company_names) >= num * 2:
                break
        if len(company_names) >= num * 2:
            break
    return company_names[:num * 2]
