from connectors.config import BaseConnectorConfigSchemaFactory, ConnectorConfigSchema, ConnectorConfigEntrySchema

class SnowflakeConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = "snowflake"

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
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="schema",
                    label="Schema",
                    description="Snowflake Schema",
                    type="string",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="role",
                    label="Role",
                    description="Snowflake Role",
                    type="string",
                    required=False,
                ),
            ],
        )