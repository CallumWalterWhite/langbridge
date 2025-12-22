from enum import Enum
from typing import Dict, List, Optional, Literal
import yaml
from pydantic import BaseModel, Field
from .model import Dimension, Measure

class QueryModel(BaseModel):
    dimensions: Dict[str, Dimension]
    measures: Dict[str, Measure]
    filters: Dict[str, str]  # Simple key-value filters