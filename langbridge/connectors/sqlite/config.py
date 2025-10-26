from connectors.config import (
    BaseConnectorConfigSchemaFactory, 
    BaseConnectorConfigFactory,
    ConnectorConfigSchema, 
    ConnectorConfigEntrySchema, 
    BaseConnectorConfig,
    ConnectorRuntimeType
)

class SqliteConnectorConfig(BaseConnectorConfig):
    location: str

    @classmethod
    def create_from_dict(cls, data: dict) -> "SqliteConnectorConfig":
        location = data.get("location")
        if location is None:
            raise ValueError("Both 'location' must be provided and non-None.")
        return cls(
            location=location
        )
        
class SqliteConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorRuntimeType.SQLITE

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return SqliteConnectorConfig.create_from_dict(config)

class SqliteConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorRuntimeType.SQLITE

    @classmethod
    def create(cls, config: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="Sqlite",
            description="Sqlite Connector (SQLite)",
            version="1.0",
            label="SQLite",
            icon="sqlite.png",
            connector_type=ConnectorRuntimeType.SQLITE.value,
            config=[
                ConnectorConfigEntrySchema(field="location", label="Location", description="Sqlite Location", type="string", required=True)
            ]
        )