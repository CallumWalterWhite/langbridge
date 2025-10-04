from pydantic import BaseModel


class _Base(BaseModel):
    class Config:
        allow_population_by_field_name = True