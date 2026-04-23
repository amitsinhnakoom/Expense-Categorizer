from __future__ import annotations

from datetime import date as DateType
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MatchType(str, Enum):
    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"


class TransactionIn(BaseModel):
    date: Optional[DateType] = None
    description: str = Field(..., min_length=1)
    amount: float
    currency: str = "USD"
    labeled_category: Optional[str] = None


class TransactionOut(BaseModel):
    date: Optional[DateType] = None
    raw_description: str
    normalized_description: str
    amount: float
    currency: str
    predicted_category: str
    matched_rule_id: Optional[str] = None
    status: str


class Rule(BaseModel):
    rule_id: str
    category: str
    match_type: MatchType
    pattern: str
    priority: int = 100
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    active: bool = True


class CategorizeRequest(BaseModel):
    transactions: list[TransactionIn]


class CategorizeResponse(BaseModel):
    transactions: list[TransactionOut]
    total_count: int
    categorized_count: int
    uncategorized_count: int
    coverage_percent: float
    correctness_percent: Optional[float] = None


class MerchantMemoryUpsertRequest(BaseModel):
    merchant: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)


class MerchantMemoryUpsertResponse(BaseModel):
    merchant: str
    normalized_merchant: str
    category: str
