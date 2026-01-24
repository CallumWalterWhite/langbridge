from langbridge.packages.connectors.langbridge_connectors.api.config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorRuntimeType,
)


class PostgresConnectorConfig(BaseConnectorConfig):
    host: str
    port: int = 5432
    database: str
    user: str
    password: str
    ssl_mode: str | None = None


class PostgresConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorRuntimeType.POSTGRES

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return PostgresConnectorConfig(**config)


class PostgresConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorRuntimeType.POSTGRES

    @classmethod
    def create(cls, _: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="PostgreSQL",
            description="Connect to a PostgreSQL-compatible database.",
            version="1.0.0",
            label="PostgreSQL",
            icon="postgres.png",
            connector_type="database",
            config=[
                ConnectorConfigEntrySchema(
                    field="host",
                    label="Host",
                    description="Database host address.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="port",
                    label="Port",
                    description="Database port number.",
                    type="number",
                    required=True,
                    default="5432",
                ),
                ConnectorConfigEntrySchema(
                    field="database",
                    label="Database",
                    description="Database name.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="user",
                    label="User",
                    description="Database user.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="password",
                    label="Password",
                    description="Database password.",
                    type="password",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="ssl_mode",
                    label="SSL mode",
                    description="Optional SSL mode (disable, allow, prefer, require, verify-ca, verify-full).",
                    type="string",
                    required=False,
                    value_list=["disable", "allow", "prefer", "require", "verify-ca", "verify-full"],
                ),
            ],
        )
