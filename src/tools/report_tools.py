"""Reporting tools."""

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

        # Skip header row if present
        if rows and rows[0] == COLUMNS:
            rows = rows[1:]

        if not rows:
            return f"Không có khoản chi nào trong tháng {month:02d}/{year}."

        total = 0.0
        category_sums: dict[str, float] = {}
        entries: list[tuple[str, float, str]] = []

        for row in rows:
            # Ensure row has 5 columns
            row_extended = list(row) + [""] * (5 - len(row))
            _, item, amount_str, category, _ = row_extended[:5]

            if not amount_str:
                continue

            try:
                amt = float(amount_str)
            except Exception:
                continue

            total += amt
            cat = (category or "").strip() or "Không phân loại"
            category_sums[cat] = category_sums.get(cat, 0) + amt
            entries.append((item, amt, cat))

        # Total expenses
        total_str = format_vnd(total)
        total_line = f"Tổng chi: {total_str} VND"

        # Expenses by category
        sorted_cats = sorted(category_sums.items(), key=lambda x: x[1], reverse=True)
        category_lines: list[str] = [
            f"- {cat}: {format_vnd(sum_amt)} VND" for cat, sum_amt in sorted_cats
        ]

        # Largest expenses (max 3)
        entries.sort(key=lambda x: x[1], reverse=True)
        largest_entries = entries[:3]
        largest_section_lines: list[str] = []

        if not largest_entries:
            largest_section_lines.append("Không có khoản chi nào.")
        elif len(largest_entries) == 1:
            item, amt, cat = largest_entries[0]
            amt_str = format_vnd(amt)
            if cat == "Không phân loại":
                largest_section_lines.append(
                    f"Khoản chi lớn nhất: {item} - {amt_str} VND"
                )
            else:
                largest_section_lines.append(
                    f"Khoản chi lớn nhất: {item} ({cat}) - {amt_str} VND"
                )
        else:
            largest_section_lines.append("Những khoản chi lớn nhất:")
            for i, (item, amt, cat) in enumerate(largest_entries, start=1):
                amt_str = format_vnd(amt)
                if cat == "Không phân loại":
                    largest_section_lines.append(f"{i}. {item} - {amt_str} VND")
                else:
                    largest_section_lines.append(f"{i}. {item} ({cat}) - {amt_str} VND")

        # Assemble report
        report_lines: list[str] = [f"Báo cáo chi tiêu tháng {month:02d}/{year}:"]
        report_lines.append(total_line)
        report_lines.append("Chi theo nhóm:")
        report_lines.extend(category_lines)
        report_lines.append("")  # empty line
        report_lines.extend(largest_section_lines)

        return "\n".join(report_lines)
