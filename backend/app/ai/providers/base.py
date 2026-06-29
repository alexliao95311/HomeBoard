from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], model: str) -> str:
        """Send messages and return the raw text content of the reply."""
