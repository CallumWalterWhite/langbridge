from langbridge.packages.connectors.langbridge_connectors.api.config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorRuntimeType,
)


class MySQLConnectorConfig(BaseConnectorConfig):
    host: str
    port: int = 3306
    database: str
    user: str
    password: str
    ssl_mode: str | None = None


class MySQLConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorRuntimeType.MYSQL

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return MySQLConnectorConfig(**config)


class MySQLConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorRuntimeType.MYSQL

    @classmethod
    def create(cls, _: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="MySQL",
            description="Connect to a MySQL-compatible database.",
            version="1.0.0",
            label="MySQL",
            icon="mysql.png",
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
                    default="3306",
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
                    description="Optional SSL mode.",
                    type="string",
                    required=False,
                    value_list=["disabled", "preferred", "required", "verify_ca", "verify_identity"],
                ),
            ],
        )
