from enum import Enum
from typing import Dict, List, Optional, Literal
import yaml
from pydantic import BaseModel, Field

class MeasureAggregation(str, Enum):
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    _count = "count" 

class Dimension(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    alias: Optional[str] = None
    description: Optional[str] = None
    synonyms: Optional[List[str]] = None
    # sample_data: Optional[List[str]] = None
    vectorized: bool = False


class Measure(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    aggregation: Optional[str] = None
    synonyms: Optional[List[str]] = None

class TableFilter(BaseModel):
    condition: str
    description: Optional[str] = None
    synonyms: Optional[List[str]] = None


class Table(BaseModel):
    schema: str
    name: str
    description: Optional[str] = None
    synonyms: Optional[List[str]] = None
    dimensions: Optional[List[Dimension]] = None
    measures: Optional[List[Measure]] = None
    filters: Optional[Dict[str, TableFilter]] = None


class Relationship(BaseModel):
    name: str
    from_: str = Field(alias="from_")
    to: str
    type: Literal["one_to_many", "many_to_one", "one_to_one", "many_to_many"]
    join_on: str


class Metric(BaseModel):
    description: Optional[str] = None
    expression: str


class SemanticModel(BaseModel):
    version: str
    connector: Optional[str] = None
    description: Optional[str] = None
    tables: Dict[str, Table]
    relationships: Optional[List[Relationship]] = None
    metrics: Optional[Dict[str, Metric]] = None
    
    def yml_dump(self) -> str:
        """Dump the semantic model to a YAML string."""

        return yaml.dump(self.dict(by_alias=True), sort_keys=False)
