import json

from connectors.connection_tester import BaseConnectorTester
from connectors.config import ConnectorType

from .config import BigQueryConnectorConfig


class BigQueryConnectorTester(BaseConnectorTester):
    type = ConnectorType.BIGQUERY

    def test(self, config: BigQueryConnectorConfig):
        if not config.project_id:
            return "Project ID is required."
        if not config.dataset:
            return "Dataset is required."
        if not config.credentials_json:
            return "Service account key is required."

        try:
            parsed = json.loads(config.credentials_json)
        except json.JSONDecodeError:
            return "Service account key must be valid JSON."

        required_keys = {"client_email", "private_key", "project_id"}
        missing = [key for key in required_keys if key not in parsed]
        if missing:
            return f"Service account key missing keys: {', '.join(missing)}"

        return True
