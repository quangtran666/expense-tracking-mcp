from __future__ import annotations

from fastmcp import FastMCP
from googleapiclient.errors import HttpError

from src.config import COLUMNS
from src.services import GoogleSheetsService, format_vnd
from typing import Annotated


def setup_report_tools(
    mcp: FastMCP, sheets_service: GoogleSheetsService, spreadsheet_id: str
):
    @mcp.tool(
        name="expense_report",
        description="""Trả về báo cáo tổng hợp chi tiêu cho tháng được chỉ định.""",
    )
    def expense_report(
        year: Annotated[int, """Năm (ví dụ: 2025)"""],
        month: Annotated[int, """Tháng (1-12)"""],
    ) -> str:
        sheet_name = f"{year}-{month:02d}"

        try:
            range_name = f"{sheet_name}!A:E"
            resp = sheets_service.get_values(spreadsheet_id, range_name)
        except HttpError:
            return f"Không tìm thấy dữ liệu cho tháng {month:02d}/{year}."

        rows = resp.get("values", [])

        if rows and rows[0] == COLUMNS:
            rows = rows[1:]

        if not rows:
            return f"Không có khoản chi nào trong tháng {month:02d}/{year}."

        entries = []
        category_sums = {}

        for row in rows:
            row_data = (list(row) + [""] * 5)[:5]
            _, item, amount_str, category, _ = row_data

            try:
                amt = float(amount_str) if amount_str else 0
                if amt <= 0:
                    continue

                cat = (category or "").strip() or "Không phân loại"
                entries.append((item, amt, cat))
                category_sums[cat] = category_sums.get(cat, 0) + amt
            except (ValueError, TypeError):
                continue

        if not entries:
            return f"Không có khoản chi nào trong tháng {month:02d}/{year}."

        # Tạo report
        total = sum(amt for _, amt, _ in entries)
        sorted_entries = sorted(entries, key=lambda x: x[1], reverse=True)[:3]
        sorted_cats = sorted(category_sums.items(), key=lambda x: x[1], reverse=True)

        # Format output
        def format_entry(item, amt, cat, index=None):
            amt_str = format_vnd(amt)
            cat_part = f" ({cat})" if cat != "Không phân loại" else ""
            prefix = f"{index}. " if index else "Khoản chi lớn nhất: "
            return f"{prefix}{item}{cat_part} - {amt_str} VND"

        report_parts = [
            f"Báo cáo chi tiêu tháng {month:02d}/{year}:",
            f"Tổng chi: {format_vnd(total)} VND",
            "Chi theo nhóm:",
            *[f"- {cat}: {format_vnd(amt)} VND" for cat, amt in sorted_cats],
            "",
            "Những khoản chi lớn nhất:" if len(sorted_entries) > 1 else "",
            *(
                [format_entry(*sorted_entries[0])]
                if len(sorted_entries) == 1
                else [
                    format_entry(item, amt, cat, i + 1)
                    for i, (item, amt, cat) in enumerate(sorted_entries)
                ]
            ),
        ]

        return "\n".join(filter(None, report_parts))
