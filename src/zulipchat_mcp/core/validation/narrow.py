"""Narrow filter definitions and builders for message filtering."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator

from ...utils.logging import get_logger
from ..exceptions import ValidationError

logger = get_logger(__name__)


class NarrowOperator(str, Enum):
    """Supported narrow operators for message filtering."""

    STREAM = "stream"
    TOPIC = "topic"
    SENDER = "sender"
    PM_WITH = "pm-with"
    ID = "id"
    SEARCH = "search"
    NEAR = "near"
    HAS = "has"
    IS = "is"
    GROUP_PM_WITH = "group-pm-with"


class NarrowFilter(BaseModel):
    """A single narrow filter for message queries."""

    operator: NarrowOperator
    operand: str | int | list[str]
    negated: bool = False

    def __init__(self, operator=None, operand=None, negated=False, **data):
        """Initialize with positional or keyword arguments."""
        if operator is not None and operand is not None and not data:
            # Handle positional arguments
            super().__init__(operator=operator, operand=operand, negated=negated)
        else:
            # Handle keyword arguments
            if operator is not None:
                data['operator'] = operator
            if operand is not None:
                data['operand'] = operand
            if negated:
                data['negated'] = negated
            super().__init__(**data)

    @field_validator("operand")
    def validate_operand(cls, v, info):
        """Validate operand based on operator type."""
        operator = info.data.get("operator")
        if operator == NarrowOperator.ID and not isinstance(v, int):
            raise ValueError("ID operator requires integer operand")
        if operator in [NarrowOperator.STREAM, NarrowOperator.TOPIC, NarrowOperator.SENDER] and not isinstance(v, str):
            raise ValueError(f"{operator} operator requires string operand")
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to Zulip API format."""
        result = {"operator": self.operator.value, "operand": self.operand}
        if self.negated:
            result["negated"] = True
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NarrowFilter:
        """Create NarrowFilter from dictionary."""
        try:
            operator = NarrowOperator(data["operator"])
        except (KeyError, ValueError):
            raise ValidationError(f"Invalid narrow operator: {data.get('operator', 'missing')}") from None

        try:
            return cls(
                operator=operator,
                operand=data["operand"],
                negated=data.get("negated", False)
            )
        except (KeyError, ValueError) as e:
            raise ValidationError(f"Invalid narrow filter data: {e}") from None

    def __str__(self) -> str:
        """String representation of narrow filter."""
        return f"NarrowFilter(operator={self.operator.value}, operand={self.operand})"

    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if not isinstance(other, NarrowFilter):
            return False
        return (
            self.operator == other.operator
            and self.operand == other.operand
            and self.negated == other.negated
        )


class NarrowBuilder:
    """Fluent interface for building complex narrow filters."""

    def __init__(self):
        """Initialize narrow builder."""
        self.filters: list[NarrowFilter] = []

    def stream(self, name: str, negated: bool = False) -> NarrowBuilder:
        """Add stream filter."""
        self.filters.append(
            NarrowFilter(operator=NarrowOperator.STREAM, operand=name, negated=negated)
        )
        return self

    def topic(self, name: str, negated: bool = False) -> NarrowBuilder:
        """Add topic filter."""
        self.filters.append(
            NarrowFilter(operator=NarrowOperator.TOPIC, operand=name, negated=negated)
        )
        return self

    def sender(self, email: str, negated: bool = False) -> NarrowBuilder:
        """Add sender filter."""
        self.filters.append(
            NarrowFilter(operator=NarrowOperator.SENDER, operand=email, negated=negated)
        )
        return self

    def has(self, attribute: str, negated: bool = False) -> NarrowBuilder:
        """Add 'has' filter (e.g., 'attachment', 'link', 'image')."""
        self.filters.append(
            NarrowFilter(operator=NarrowOperator.HAS, operand=attribute, negated=negated)
        )
        return self

    def is_filter(self, attribute: str, negated: bool = False) -> NarrowBuilder:
        """Add 'is' filter (e.g., 'private', 'starred', 'mentioned')."""
        self.filters.append(
            NarrowFilter(operator=NarrowOperator.IS, operand=attribute, negated=negated)
        )
        return self

    def search(self, query: str, negated: bool = False) -> NarrowBuilder:
        """Add search filter."""
        self.filters.append(
            NarrowFilter(operator=NarrowOperator.SEARCH, operand=query, negated=negated)
        )
        return self

    def time_range(self, after: datetime, before: datetime | None = None) -> NarrowBuilder:
        """Add time-based filters."""
        self.filters.append(
            NarrowFilter(
                operator=NarrowOperator.SEARCH,
                operand=f"after:{after.isoformat()}",
            )
        )
        if before:
            self.filters.append(
                NarrowFilter(
                    operator=NarrowOperator.SEARCH,
                    operand=f"before:{before.isoformat()}",
                )
            )
        return self

    def build(self) -> list[dict[str, Any]]:
        """Build the narrow list for Zulip API."""
        return [f.to_dict() for f in self.filters]

    @staticmethod
    def from_dict(filters: list[dict[str, Any]]) -> list[NarrowFilter]:
        """Create NarrowFilter objects from dictionary format."""
        result = []
        for f in filters:
            result.append(
                NarrowFilter(
                    operator=NarrowOperator(f["operator"]),
                    operand=f["operand"],
                    negated=f.get("negated", False),
                )
            )
        return result
