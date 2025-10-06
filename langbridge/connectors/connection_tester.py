from abc import ABC, abstractmethod

class BaseConnectorTester(ABC):
    type: str
    
    @abstractmethod
    def test(self, form:dict[any]) -> bool:
        pass
