from langbridge.packages.connectors.langbridge_connectors.api.config import (
    BaseConnectorConfigSchemaFactory, 
    BaseConnectorConfigFactory,
    ConnectorConfigSchema, 
    ConnectorConfigEntrySchema, 
    BaseConnectorConfig,
    ConnectorRuntimeType
)

class FaissConnectorConfig(BaseConnectorConfig):
    location: str

    @classmethod
    def create_from_dict(cls, data: dict) -> "FaissConnectorConfig":
        location = data.get("location")
        if location is None:
            raise ValueError("Both 'location' must be provided and non-None.")
        return cls(
            location=location
        )
        
class FaissConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorRuntimeType.FAISS

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return FaissConnectorConfig.create_from_dict(config)

class FaissConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorRuntimeType.FAISS

    @classmethod
    def create(cls, config: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="Faiss",
            description="Faiss Connector (Faiss)",
            version="1.0",
            label="Faiss",
            icon="Faiss.png",
            connector_type=ConnectorRuntimeType.FAISS.value,
            config=[
                ConnectorConfigEntrySchema(field="location", label="Location", description="Faiss Location", type="string", required=True)
            ]
        )