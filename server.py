from __future__ import annotations

import datetime
from typing import Optional

from fastmcp import FastMCP
from googleapiclient.errors import HttpError

import settings as config
from google_api import get_credentials, build_sheets_service

mcp = FastMCP("fast-track")

# Chuẩn bị Google API services (tạo 1 lần)
creds = get_credentials()
sheets_service = build_sheets_service(creds)


# Hàm tiện ích: định dạng số tiền VND (phân cách nghìn bằng '.', thập phân bằng ',')
def _format_vnd(amount: float) -> str:
    if float(amount).is_integer():
        # dạng số nguyên
        s = f"{int(amount):,}"
        s = s.replace(",", ".")
    else:
        s = f"{amount:,.2f}"
        parts = s.split(".")
        if len(parts) == 2:
            parts[0] = parts[0].replace(",", ".")
            s = parts[0] + "," + parts[1]
    return s


# ---------------------------
# Tool: Ghi chi phí vào Google Sheets (theo tháng)
# ---------------------------
@mcp.tool()
def log_expense(
    item: str,
    amount: float,
    category: str,
    when: datetime.datetime,
    note: Optional[str] = None,  # note vẫn optional
) -> str:
    """
    Ghi lại một khoản chi tiêu vào Google Sheets (mỗi tháng một sheet riêng).

    Tham số:
      - item (str): mô tả khoản chi (vd: "ăn trưa")
      - amount (float): số tiền (VND)
      - category (str): nhóm chi tiêu (vd: "Ăn uống", "Giải trí") — BẮT BUỘC, không được rỗng
      - when (datetime): thời điểm chi tiêu (bắt buộc). Nếu datetime không có timezone, sẽ gán config.TIMEZONE.
      - note (str, optional): ghi chú

    Trả về: chuỗi xác nhận sau khi ghi thành công.
    """
    # Validate inputs cơ bản
    cat = (category or "").strip()
    if not cat:
        return "Lỗi: 'category' không được để trống."

    if amount is None:
        return "Lỗi: 'amount' không được để trống."
    try:
        amount = float(amount)
    except Exception:
        return "Lỗi: 'amount' phải là số."

    tz = config.TIMEZONE  # ví dụ: pytz.timezone('Asia/Ho_Chi_Minh') hoặc zoneinfo.ZoneInfo('Asia/Ho_Chi_Minh')

    # Chuẩn hóa timezone cho 'when'
    if when.tzinfo is None:
        # naive -> gán tz mặc định
        if hasattr(tz, "localize"):
            current_dt = tz.localize(when)  # pytz
        else:
            current_dt = when.replace(tzinfo=tz)  # zoneinfo
    else:
        # aware -> convert về tz mặc định (đề phòng when theo tz khác)
        try:
            current_dt = when.astimezone(tz)
        except Exception:
            # nếu tz không hỗ trợ astimezone (trường hợp hiếm), giữ nguyên
            current_dt = when

    sheet_name = f"{current_dt.year}-{current_dt.month:02d}"

    # Date/time string (hiển thị cả giờ:phút)
    date_str = current_dt.strftime("%Y-%m-%d %H:%M")
    values = [[date_str, item, amount, cat, note or ""]]
    rng = f"{sheet_name}!A:E"

    try:
        # Lấy danh sách sheet hiện có
        spreadsheet = (
            sheets_service.spreadsheets()
            .get(spreadsheetId=config.SPREADSHEET_ID, fields="sheets.properties")
            .execute()
        )
        sheets_info = spreadsheet.get("sheets", [])
        sheet_map = {
            s["properties"]["title"]: s["properties"]["sheetId"] for s in sheets_info
        }

        # Tạo sheet tháng nếu chưa có
        sheet_id = sheet_map.get(sheet_name)
        if sheet_id is None:
            batch_body = {
                "requests": [{"addSheet": {"properties": {"title": sheet_name}}}]
            }
            res = (
                sheets_service.spreadsheets()
                .batchUpdate(spreadsheetId=config.SPREADSHEET_ID, body=batch_body)
                .execute()
            )
            sheet_id = res["replies"][0]["addSheet"]["properties"]["sheetId"]

        # Ghi header nếu sheet còn trống
        resp = (
            sheets_service.spreadsheets()
            .values()
            .get(spreadsheetId=config.SPREADSHEET_ID, range=f"{sheet_name}!A1:A1")
            .execute()
        )
        if "values" not in resp:
            sheets_service.spreadsheets().values().update(
                spreadsheetId=config.SPREADSHEET_ID,
                range=f"{sheet_name}!A1:E1",
                valueInputOption="RAW",
                body={"values": [config.COLUMNS]},
            ).execute()

            # Định dạng header
            format_req = {
                "requests": [
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
            }
            try:
                sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=config.SPREADSHEET_ID, body=format_req
                ).execute()
            except HttpError:
                pass  # không chặn luồng nếu format lỗi

        # Append dòng dữ liệu
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config.SPREADSHEET_ID,
            range=rng,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()

        return f"Đã ghi: {item} - {amount} ({cat}) vào sheet {sheet_name} ({date_str})."
    except HttpError as e:
        return f"Không thể ghi chi phí: {e}"


# ---------------------------
# Tool: Báo cáo chi tiêu theo tháng (thay cho resource template)
# ---------------------------
@mcp.tool()
def expense_report(year: int, month: int) -> str:
    """
    Trả về báo cáo tổng hợp chi tiêu cho tháng được chỉ định.
    Gọi qua tools/call với params:
      { "name": "expense_report", "arguments": { "year": 2025, "month": 9 } }
    """
    sheet_name = f"{year}-{month:02d}"
    try:
        resp = (
            sheets_service.spreadsheets()
            .values()
            .get(spreadsheetId=config.SPREADSHEET_ID, range=f"{sheet_name}!A:E")
            .execute()
        )
    except HttpError:
        return f"Không tìm thấy dữ liệu cho tháng {month:02d}/{year}."

    rows = resp.get("values", [])
    # Bỏ qua hàng tiêu đề nếu có
    if rows and rows[0] == config.COLUMNS:
        rows = rows[1:]
    if not rows:
        return f"Không có khoản chi nào trong tháng {month:02d}/{year}."

    total = 0.0
    category_sums: dict[str, float] = {}
    entries: list[tuple[str, float, str]] = []

    for row in rows:
        # Đảm bảo độ dài 5 cột cho mỗi hàng
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

    # Tổng chi
    total_str = _format_vnd(total)
    total_line = f"Tổng chi: {total_str} VND"

    # Chi theo nhóm
    sorted_cats = sorted(category_sums.items(), key=lambda x: x[1], reverse=True)
    category_lines: list[str] = [
        f"- {cat}: {_format_vnd(sum_amt)} VND" for cat, sum_amt in sorted_cats
    ]

    # Các khoản chi lớn nhất (tối đa 3)
    entries.sort(key=lambda x: x[1], reverse=True)
    largest_entries = entries[:3]
    largest_section_lines: list[str] = []
    if not largest_entries:
        largest_section_lines.append("Không có khoản chi nào.")
    elif len(largest_entries) == 1:
        item, amt, cat = largest_entries[0]
        amt_str = _format_vnd(amt)
        if cat == "Không phân loại":
            largest_section_lines.append(f"Khoản chi lớn nhất: {item} - {amt_str} VND")
        else:
            largest_section_lines.append(
                f"Khoản chi lớn nhất: {item} ({cat}) - {amt_str} VND"
            )
    else:
        largest_section_lines.append("Những khoản chi lớn nhất:")
        for i, (item, amt, cat) in enumerate(largest_entries, start=1):
            amt_str = _format_vnd(amt)
            if cat == "Không phân loại":
                largest_section_lines.append(f"{i}. {item} - {amt_str} VND")
            else:
                largest_section_lines.append(f"{i}. {item} ({cat}) - {amt_str} VND")

    # Ghép báo cáo
    report_lines: list[str] = [f"Báo cáo chi tiêu tháng {month:02d}/{year}:"]
    report_lines.append(total_line)
    report_lines.append("Chi theo nhóm:")
    report_lines.extend(category_lines)
    report_lines.append("")  # dòng trống
    report_lines.extend(largest_section_lines)

    return "\n".join(report_lines)


# ---------------------------
# Run server (dev/standalone)
# ---------------------------

if __name__ == "__main__":
    mcp.run()
