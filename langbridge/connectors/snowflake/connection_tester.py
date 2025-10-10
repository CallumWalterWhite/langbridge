from typing import Union
from connectors.connection_tester import BaseConnectorTester

from snowflake.connector import connect, ProgrammingError, OperationalError, DatabaseError

from connectors.config import ConnectorType
from .config import SnowflakeConnectorConfig

class SnowflakeConnectorTester(BaseConnectorTester):
    type: ConnectorType = ConnectorType.SNOWFLAKE
    
    def test(self, config: SnowflakeConnectorConfig) -> Union[bool, str]:
        try:
            conn = connect(
                user=config.user,
                password=config.password,
                account=config.account,
                database=config.database,
                warehouse=config.warehouse,
                schema=config.schema,
                role=config.role,
            )
            conn.close()
        except (ProgrammingError, OperationalError, DatabaseError) as e:
            return str(e)
        
        return True