from connectors.config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorRuntimeType,
)


class MongoDBConnectorConfig(BaseConnectorConfig):
    connection_uri: str
    database: str
    username: str | None = None
    password: str | None = None
    auth_source: str | None = None


class MongoDBConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorRuntimeType.MONGODB

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return MongoDBConnectorConfig(**config)


class MongoDBConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorRuntimeType.MONGODB

    @classmethod
    def create(cls, _: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="MongoDB",
            description="Connect to a MongoDB cluster using a standard connection string.",
            version="1.0.0",
            label="MongoDB",
            icon="mongodb.png",
            connector_type="database",
            config=[
                ConnectorConfigEntrySchema(
                    field="connection_uri",
                    label="Connection URI",
                    description="For example: mongodb+srv://cluster.example.com",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="database",
                    label="Database",
                    description="Database to use within the cluster.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="username",
                    label="Username",
                    description="Optional username if not supplied within the URI.",
                    type="string",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="password",
                    label="Password",
                    description="Optional password if not supplied within the URI.",
                    type="password",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="auth_source",
                    label="Auth source",
                    description="Authentication database, defaults to admin.",
                    type="string",
                    required=False,
                ),
            ],
        )
