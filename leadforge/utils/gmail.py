import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


class GmailClient:
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.authenticated = False

    def authenticate(self) -> bool:
        if not GMAIL_AVAILABLE:
            return False
        if not os.path.exists(self.credentials_file):
            return False
        try:
            creds = None
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())
            self.service = build("gmail", "v1", credentials=creds)
            self.authenticated = True
            return True
        except Exception:
            return False

    def create_draft(self, to: str, subject: str, body: str, sender: str = "me") -> Optional[str]:
        """Create a Gmail draft and return draft ID."""
        if not self.authenticated or not self.service:
            return None
        try:
            message = MIMEMultipart("alternative")
            message["to"] = to
            message["subject"] = subject
            text_part = MIMEText(body, "plain")
            message.attach(text_part)
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            draft = self.service.users().drafts().create(
                userId="me", body={"message": {"raw": raw}}
            ).execute()
            return draft.get("id")
        except Exception:
            return None

    def create_multiple_drafts(self, emails: List[dict]) -> List[str]:
        """emails = [{to, subject, body}, ...]"""
        draft_ids = []
        for email in emails:
            draft_id = self.create_draft(
                to=email.get("to", ""),
                subject=email.get("subject", ""),
                body=email.get("body", ""),
            )
            if draft_id:
                draft_ids.append(draft_id)
        return draft_ids
