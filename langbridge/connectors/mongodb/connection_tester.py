from urllib.parse import urlparse

from connectors.connection_tester import BaseConnectorTester
from connectors.config import ConnectorType

from .config import MongoDBConnectorConfig


class MongoDBConnectorTester(BaseConnectorTester):
    type = ConnectorType.MONGODB

    def test(self, config: MongoDBConnectorConfig):
        if not config.connection_uri:
            return "Connection URI is required."

        parsed = urlparse(config.connection_uri)
        if parsed.scheme not in {"mongodb", "mongodb+srv"}:
            return "Connection URI must start with mongodb:// or mongodb+srv://."

        if not config.database:
            return "Database is required."

        return True
