from __future__ import annotations

import os
from typing import Sequence

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_credentials(
    scopes: Sequence[str] = DEFAULT_SCOPES,
    credentials_file: str = os.path.join(BASE_DIR, "credentials.json"),
    token_file: str = os.path.join(BASE_DIR, "token.json"),
) -> Credentials:
    """
    Lấy/refresh OAuth2 credentials.
    - Lần đầu sẽ mở browser xin quyền và lưu token.json.
    - Các lần sau tự refresh.
    """
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                raise FileNotFoundError(f"Không tìm thấy {credentials_file}")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            creds = flow.run_local_server(port=0, prompt="consent")
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return creds


def build_sheets_service(creds: Credentials):
    return build("sheets", "v4", credentials=creds, cache_discovery=False)
