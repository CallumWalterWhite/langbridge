from connectors.connection_tester import BaseConnectorTester
from connectors.config import ConnectorType

from .config import OracleConnectorConfig


class OracleConnectorTester(BaseConnectorTester):
    type = ConnectorType.ORACLE

    def test(self, config: OracleConnectorConfig):
        missing = [
            field
            for field in ["host", "port", "service_name", "username", "password"]
            if not getattr(config, field)
        ]
        if missing:
            return f"Missing required fields: {', '.join(missing)}"

        try:
            port_value = int(config.port)
        except (TypeError, ValueError):
            return "Port must be a valid integer."

        if port_value <= 0 or port_value > 65535:
            return "Port must be between 1 and 65535."

        return True
