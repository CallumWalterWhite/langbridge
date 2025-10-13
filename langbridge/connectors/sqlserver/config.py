from connectors.config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorType,
)


class SQLServerConnectorConfig(BaseConnectorConfig):
    host: str
    port: int = 1433
    database: str
    username: str
    password: str
    encrypt: bool | None = None
    trust_server_certificate: bool | None = None


class SQLServerConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorType.SQLSERVER

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return SQLServerConnectorConfig(**config)


class SQLServerConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorType.SQLSERVER

    @classmethod
    def create(cls, _: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="SQL Server",
            description="Connect to a Microsoft SQL Server instance.",
            version="1.0.0",
            label="SQL Server",
            icon="sqlserver.png",
            connector_type="database",
            config=[
                ConnectorConfigEntrySchema(
                    field="host",
                    label="Host",
                    description="Server hostname or IP address.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="port",
                    label="Port",
                    description="Server port number.",
                    type="number",
                    required=True,
                    default="1433",
                ),
                ConnectorConfigEntrySchema(
                    field="database",
                    label="Database",
                    description="Database name.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="username",
                    label="Username",
                    description="Login username.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="password",
                    label="Password",
                    description="Login password.",
                    type="password",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="encrypt",
                    label="Encrypt connection",
                    description="Enable TLS encryption for the connection.",
                    type="boolean",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="trust_server_certificate",
                    label="Trust server certificate",
                    description="Skip certificate validation when using TLS. Use with caution.",
                    type="boolean",
                    required=False,
                ),
            ],
        )
