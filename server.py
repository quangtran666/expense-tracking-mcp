from __future__ import annotations

from fastmcp import FastMCP

from src.config import SPREADSHEET_ID
from src.services import GoogleSheetsService
from src.tools import setup_expense_tools, setup_report_tools

# Initialize FastMCP server
mcp = FastMCP("fast-track")

# Initialize Google Sheets service
sheets_service = GoogleSheetsService()

# Setup tools
setup_expense_tools(mcp, sheets_service, SPREADSHEET_ID)
setup_report_tools(mcp, sheets_service, SPREADSHEET_ID)

if __name__ == "__main__":
    mcp.run()
