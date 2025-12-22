# Semantic Model SQL Translator (T-SQL)

This folder provides a CubeJS-style semantic query translator that turns a structured semantic query plus a Langbridge semantic model into T-SQL.

## Quick demo

```powershell
python -m experimental.semantic_model.demo
```

This builds a small SQLite database, loads `sample_semantic_model.yml`, generates T-SQL, and (if `sqlglot` is available) executes the query against SQLite after transpiling.

## Usage

```python
from experimental.semantic_model import SemanticModel, SemanticQuery, TsqlSemanticTranslator
import yaml

model = SemanticModel.model_validate(yaml.safe_load(open("sample_semantic_model.yml", "r")))
query = SemanticQuery.model_validate({
    "measures": ["total_revenue"],
    "dimensions": ["customers.region"],
    "timeDimensions": [{"dimension": "orders.order_date", "granularity": "month"}],
    "filters": [{"member": "orders.status", "operator": "equals", "values": ["completed"]}],
    "order": {"total_revenue": "desc"},
    "limit": 10,
})

sql = TsqlSemanticTranslator().translate(query, model)
print(sql)
```

## Supported query features

- Measures, dimensions, time dimensions with granularity + date ranges
- Filters with CubeJS-like operators (`equals`, `contains`, `inDateRange`, `set`, etc.)
- Segments mapped from table filters in the semantic model
- Joins resolved via model relationships
- Order, limit, and offset handling for T-SQL
