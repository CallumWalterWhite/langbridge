from abc import ABC, abstractmethod
from typing import Type

from connectors.config import BaseConnectorConfig, ConnectorType

class BaseConnectorTester(ABC):
    type: ConnectorType
    
    @abstractmethod
    def test(self, form:BaseConnectorConfig) -> bool:
        pass

def get_connector_tester(type_s: ConnectorType) -> Type[BaseConnectorTester]:
    subclasses = BaseConnectorTester.__subclasses__()
    for subclass in subclasses:
        if subclass.type == type_s:
            return subclass
    raise ValueError(f"No tester found for type: {type_s}")