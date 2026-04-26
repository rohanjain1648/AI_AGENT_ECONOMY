import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic / TokenRouter
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TOKENROUTER_API_KEY = os.getenv("TOKENROUTER_API_KEY", "")

# Use TokenRouter if key provided, else fallback to Anthropic directly
USE_TOKENROUTER = bool(TOKENROUTER_API_KEY)

RESEARCH_MODEL = "claude-sonnet-4-6"
WRITING_MODEL = "claude-sonnet-4-6"

# Gmail OAuth
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "token.json")

# Search
SEARCH_RESULTS_PER_COMPANY = 5
MAX_LEADS_TO_RESEARCH = 10
