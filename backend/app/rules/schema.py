from __future__ import annotations

from pydantic import BaseModel

from app.models import Rule


class RulesConfig(BaseModel):
    rules: list[Rule]
