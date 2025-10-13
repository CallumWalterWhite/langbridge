from typing import Union
from connectors.connection_tester import BaseConnectorTester
from sqlite3 import connect, OperationalError, DatabaseError, ProgrammingError
from connectors.config import ConnectorType
from .config import SqliteConnectorConfig

class SqliteConnectorTester(BaseConnectorTester):
    type: ConnectorType = ConnectorType.SQLITE
    
    def test(self, config: SqliteConnectorConfig) -> Union[bool, str]:
        try:
            conn = connect(config.location)
            conn.close()
        except (ProgrammingError, OperationalError, DatabaseError) as e:
            return str(e)
        
        return True