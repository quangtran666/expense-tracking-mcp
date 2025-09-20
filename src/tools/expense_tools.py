from __future__ import annotations

import datetime
from typing import Annotated

from fastmcp import FastMCP
from googleapiclient.errors import HttpError
from pydantic import Field

from src.config import COLUMNS
from src.models import ExpenseEntry
from src.services import GoogleSheetsService


def setup_expense_tools(
    mcp: FastMCP, sheets_service: GoogleSheetsService, spreadsheet_id: str
):
    @mcp.tool(
        name="log_expense",
        description="""Ghi lại một khoản chi tiêu vào Google Sheets (mỗi tháng một sheet riêng).
        ⚠️ Lưu ý: Toàn bộ tham số nội dung (item, category, note) nên nhập bằng TIẾNG VIỆT nếu đầu vào bằng TIẾNG ANH.""",
    )
    def log_expense(
        item: Annotated[
            str, """Mô tả khoản chi tiêu (ví dụ: "ăn trưa", "mua sách")."""
        ],
        amount: Annotated[float, """Số tiền (VND). Bắt buộc, phải là số."""],
        category: Annotated[
            str,
            """Nhóm chi tiêu (ví dụ: "Ăn uống", "Giải trí"). Bắt buộc, KHÔNG được nhập tiếng Anh.""",
        ],
        when: Annotated[
            datetime.datetime,
            """Thời điểm phát sinh chi tiêu. Nếu không có timezone thì sẽ gán theo `config.TIMEZONE`.""",
        ],
        note: Annotated[
            str | None,
            Field(description="Ghi chú thêm (ví dụ: 'ăn cùng bạn A', 'giảm giá 20%')."),
        ] = None,
    ) -> str:
        try:
            expense = ExpenseEntry(
                item=item, amount=amount, category=category, when=when, note=note
            )
        except Exception as e:
            return f"Lỗi dữ liệu đầu vào: {e}"

        from src.config import TIMEZONE

        if expense.when.tzinfo is None:
            if hasattr(TIMEZONE, "localize"):
                current_dt = TIMEZONE.localize(expense.when)
            else:
                current_dt = expense.when.replace(tzinfo=TIMEZONE)
        else:
            try:
                current_dt = expense.when.astimezone(TIMEZONE)
            except Exception:
                current_dt = expense.when

        sheet_name = f"{current_dt.year}-{current_dt.month:02d}"

        date_str = current_dt.strftime("%Y-%m-%d %H:%M")
        values = [
            [
                date_str,
                expense.item,
                expense.amount,
                expense.category,
                expense.note or "",
            ]
        ]
        range_name = f"{sheet_name}!A:E"

        try:
            spreadsheet_info = sheets_service.get_spreadsheet_info(spreadsheet_id)
            sheets_info = spreadsheet_info.get("sheets", [])
            sheet_map = {
                s["properties"]["title"]: s["properties"]["sheetId"]
                for s in sheets_info
            }

            sheet_id = sheet_map.get(sheet_name)
            if sheet_id is None:
                sheet_id = sheets_service.create_sheet(spreadsheet_id, sheet_name)

            header_range = f"{sheet_name}!A1:A1"
            resp = sheets_service.get_values(spreadsheet_id, header_range)

            if "values" not in resp:
                header_range = f"{sheet_name}!A1:E1"
                sheets_service.update_values(spreadsheet_id, header_range, [COLUMNS])

                format_requests = [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": {
                                        "red": 0.9,
                                        "green": 0.9,
                                        "blue": 0.9,
                                    },
                                    "horizontalAlignment": "CENTER",
                                    "textFormat": {"bold": True},
                                }
                            },
                            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,userEnteredFormat.textFormat.bold",
                        }
                    }
                ]
                try:
                    sheets_service.batch_update(spreadsheet_id, format_requests)
                except HttpError:
                    pass

            sheets_service.append_values(spreadsheet_id, range_name, values)
            try:
                sheets_service.sort_sheet(
                    spreadsheet_id, sheet_id, column_index=0, ascending=True
                )
            except HttpError:
                pass

            return f"Đã ghi: {expense.item} - {expense.amount} ({expense.category}) vào sheet {sheet_name} ({date_str}). Dữ liệu đã được sắp xếp theo thời gian."

        except HttpError as e:
            return f"Không thể ghi chi phí: {e}"
        except Exception as e:
            return f"Lỗi không mong đợi: {e}"
