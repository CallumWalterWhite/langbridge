from connectors.config import (
    BaseConnectorConfigSchemaFactory, 
    BaseConnectorConfigFactory,
    ConnectorConfigSchema, 
    ConnectorConfigEntrySchema, 
    BaseConnectorConfig,
    ConnectorType
)

class SnowflakeConnectorConfig(BaseConnectorConfig):
    account: str
    user: str
    password: str
    database: str
    warehouse: str
    schema: str 
    role: str

    @classmethod
    def create_from_dict(cls, data: dict) -> "SnowflakeConnectorConfig":
        return cls(
            account=data.get("account"),
            user=data.get("user"),
            password=data.get("password"),
            database=data.get("database"),
            warehouse=data.get("warehouse"),
            schema=data.get("schema"),
            role=data.get("role"),
        )
        
class SnowflakeConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorType.SNOWFLAKE

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return SnowflakeConnectorConfig.create_from_dict(config)

class SnowflakeConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorType.SNOWFLAKE

    @classmethod
    def create(cls, config: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="Snowflake",
            description="Snowflake Connector",
            version="1.0.0",
            label="Snowflake",
            icon="snowflake.png",
            connector_type="destination",
            config=[
                ConnectorConfigEntrySchema(
                    field="account",
                    label="Account",
                    description="Snowflake Account",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="user",
                    label="User",
                    description="Snowflake User",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="password",
                    label="Password",
                    description="Snowflake Password",
                    type="password",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="database",
                    label="Database",
                    description="Snowflake Database",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="warehouse",
                    label="Warehouse",
                    description="Snowflake Warehouse",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="schema",
                    label="Schema",
                    description="Snowflake Schema",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="role",
                    label="Role",
                    description="Snowflake Role",
                    type="string",
                    required=True,
                ),
            ],
        )