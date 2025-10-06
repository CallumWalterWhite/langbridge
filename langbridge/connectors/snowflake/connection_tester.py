from abc import ABC, abstractmethod
from connectors.connection_tester import BaseConnectorTester

class SnowflakeConnectorTester(BaseConnectorTester):
    type: str = "snowflake"
    def test(self, form:dict[any]) -> bool:
        # Implement Snowflake-specific connection testing logic here
        return True