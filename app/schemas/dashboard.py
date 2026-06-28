from datetime import datetime

from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_spend: str
    invoice_count: int
    avg_ticket: str
    period_start: datetime
    period_end: datetime
    change_pct: float | None = None


class TimeSeriesPoint(BaseModel):
    date: str
    amount: str
    count: int


class SpendOverTimeResponse(BaseModel):
    points: list[TimeSeriesPoint]


class BreakdownItem(BaseModel):
    label: str
    amount: str
    percentage: float
    count: int
    slug: str | None = None


class BreakdownResponse(BaseModel):
    items: list[BreakdownItem]


class StackedSegment(BaseModel):
    label: str
    slug: str | None = None
    amount: str


class StackedBreakdownItem(BaseModel):
    label: str
    total: str
    segments: list[StackedSegment]


class StackedBreakdownResponse(BaseModel):
    items: list[StackedBreakdownItem]
    categories: list[str]


class SpendOverTimeByCategoryPoint(BaseModel):
    date: str
    segments: list[StackedSegment]


class SpendOverTimeByCategoryResponse(BaseModel):
    points: list[SpendOverTimeByCategoryPoint]
    categories: list[str]


class TopProductItem(BaseModel):
    description: str
    total_quantity: str
    total_amount: str
    purchase_count: int


class TopProductsResponse(BaseModel):
    items: list[TopProductItem]


class RecentInvoicesResponse(BaseModel):
    data: list[dict]
