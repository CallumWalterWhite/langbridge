from abc import ABC, abstractmethod

from connectors.config import BaseConnectorConfig

class BaseConnectorTester(ABC):
    type: str
    
    @abstractmethod
    def test(self, form:BaseConnectorConfig) -> bool:
        pass

def get_connector_tester(type_s: str) -> BaseConnectorTester:
    subclasses = BaseConnectorTester.__subclasses__()
    for subclass in subclasses:
        if subclass.type == type_s:
            return subclass()
    raise ValueError(f"No tester found for type: {type_s}")