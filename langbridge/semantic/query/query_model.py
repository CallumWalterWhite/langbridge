from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DateRange = Union[str, List[str]]

class TimeDimension(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dimension: str
    granularity: Optional[str] = None
    date_range: Optional[DateRange] = Field(default=None, alias="dateRange")
    compare_date_range: Optional[DateRange] = Field(default=None, alias="compareDateRange")

    @field_validator("granularity")
    @classmethod
    def _normalize_granularity(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip().lower()


class FilterItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    member: Optional[str] = None
    dimension: Optional[str] = None
    measure: Optional[str] = None
    time_dimension: Optional[str] = Field(default=None, alias="timeDimension")
    operator: str
    values: Optional[List[str]] = None

    @model_validator(mode="after")
    def _ensure_member(self) -> "FilterItem":
        if not any((self.member, self.dimension, self.measure, self.time_dimension)):
            raise ValueError("Filter must include member, dimension, measure, or timeDimension.")
        return self


class SemanticQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    measures: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    time_dimensions: List[TimeDimension] = Field(default_factory=list, alias="timeDimensions")
    filters: List[FilterItem] = Field(default_factory=list)
    segments: List[str] = Field(default_factory=list)
    order: Any = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    timezone: Optional[str] = None
