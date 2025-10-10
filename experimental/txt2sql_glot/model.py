from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field

class Dimension(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    alias: Optional[str] = None
    description: Optional[str] = None
    synonyms: Optional[List[str]] = None

class Measure(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    aggregation: Optional[str] = None  # e.g., "sum", "avg"

class TableFilter(BaseModel):
    condition: str
    description: Optional[str] = None
    synonyms: Optional[List[str]] = None

class Table(BaseModel):
    description: Optional[str] = None
    synonyms: Optional[List[str]] = None
    dimensions: Optional[List[Dimension]] = None
    measures: Optional[List[Measure]] = None
    filters: Optional[Dict[str, TableFilter]] = None

class Relationship(BaseModel):
    name: str
    from_: str = Field(alias="from")
    to: str
    type: Literal["one_to_many", "many_to_one", "one_to_one", "many_to_many"]
    join_on: str

class Metric(BaseModel):
    description: Optional[str] = None
    expression: str  # SQL expression string

class SemanticModel(BaseModel):
    version: str
    database: Optional[str] = None
    description: Optional[str] = None
    tables: Dict[str, Table]
    relationships: Optional[List[Relationship]] = None
    metrics: Optional[Dict[str, Metric]] = None
