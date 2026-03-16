# SQL Feature

Langbridge includes runtime support for SQL execution across direct sources and
federated datasets.

## Runtime Scope

- SQL parsing and validation
- parameterized execution
- dataset-backed structured SQL
- direct SQL execution for SQL-capable connectors
- preview limits, timeouts, and guardrails
- result rows, artifacts, and execution metadata

## Execution Model

1. A SQL request enters the runtime.
2. The runtime determines whether it is a direct-source or federated workload.
3. Dataset-backed queries resolve into runtime dataset descriptors.
4. The worker applies safety checks and execution limits.
5. The runtime executes the query and returns rows, artifacts, and stats.

## Guardrails

- read-only by default unless explicitly enabled otherwise
- enforced preview row caps
- enforced runtime limits
- result redaction where configured
- shared execution path with the federated engine when multiple datasets are involved
