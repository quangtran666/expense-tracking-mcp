from __future__ import annotations

import os
from typing import Sequence

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config.settings import BASE_DIR, DEFAULT_SCOPES


class GoogleSheetsService:
    def __init__(
        self,
        scopes: Sequence[str] = DEFAULT_SCOPES,
        credentials_file: str | None = None,
        token_file: str | None = None,
    ):
        self.scopes = scopes
        self.credentials_file = credentials_file or (BASE_DIR / "credentials.json")
        self.token_file = token_file or (BASE_DIR / "token.json")
        self._service = None

    def get_credentials(self) -> Credentials:
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Không tìm thấy {self.credentials_file}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes
                )
                creds = flow.run_local_server(port=0, prompt="consent")
            with open(self.token_file, "w") as f:
                f.write(creds.to_json())
        return creds

    @property
    def service(self):
        if self._service is None:
            creds = self.get_credentials()
            self._service = build(
                "sheets", "v4", credentials=creds, cache_discovery=False
            )
        return self._service

    def get_spreadsheet_info(self, spreadsheet_id: str) -> dict:
        try:
            return (
                self.service.spreadsheets()
                .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
                .execute()
            )
        except HttpError as e:
            raise HttpError(f"Unable to access spreadsheet: {e}")

    def create_sheet(self, spreadsheet_id: str, sheet_name: str) -> int:
        batch_body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        try:
            res = (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=spreadsheet_id, body=batch_body)
                .execute()
            )
            return res["replies"][0]["addSheet"]["properties"]["sheetId"]
        except HttpError as e:
            raise HttpError(f"Unable to create sheet: {e}")

    def get_values(self, spreadsheet_id: str, range_name: str) -> dict:
        try:
            return (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
                .execute()
            )
        except HttpError as e:
            raise HttpError(f"Unable to read values: {e}")

    def update_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list],
        value_input_option: str = "RAW",
    ) -> dict:
        try:
            return (
                self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    body={"values": values},
                )
                .execute()
            )
        except HttpError as e:
            raise HttpError(f"Unable to update values: {e}")

    def append_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list],
        value_input_option: str = "RAW",
        insert_data_option: str = "INSERT_ROWS",
    ) -> dict:
        try:
            return (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    insertDataOption=insert_data_option,
                    body={"values": values},
                )
                .execute()
            )
        except HttpError as e:
            raise HttpError(f"Unable to append values: {e}")

    def batch_update(self, spreadsheet_id: str, requests: list[dict]) -> dict:
        try:
            return (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
                .execute()
            )
        except HttpError as e:
            raise HttpError(f"Unable to perform batch update: {e}")

    def sort_sheet(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        column_index: int = 0,
        ascending: bool = True,
    ) -> dict:
        sort_request = {
            "sortRange": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                },
                "sortSpecs": [
                    {
                        "dimensionIndex": column_index,
                        "sortOrder": "ASCENDING" if ascending else "DESCENDING",
                    }
                ],
            }
        }

        try:
            return self.batch_update(spreadsheet_id, [sort_request])
        except HttpError as e:
            raise HttpError(f"Unable to sort sheet: {e}")
