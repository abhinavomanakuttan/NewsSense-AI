from abc import ABC, abstractmethod
from typing import Any


class AIModule(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def process(self, data: Any, **kwargs) -> Any:
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        pass
