from pydantic import BaseModel, ConfigDict
from utils.schema import _to_camel


class _Base(BaseModel):    
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, from_attributes=True)