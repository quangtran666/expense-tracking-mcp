from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExpenseEntry(BaseModel):
    item: str = Field(description="Mô tả khoản chi tiêu (ví dụ: 'ăn trưa', 'mua sách')")
    amount: float = Field(gt=0, description="Số tiền (VND). Phải là số dương.")
    category: str = Field(description="Nhóm chi tiêu (ví dụ: 'Ăn uống', 'Giải trí')")
    when: datetime.datetime = Field(description="Thời điểm phát sinh chi tiêu")
    note: Optional[str] = Field(default=None, description="Ghi chú thêm (tùy chọn)")
