from typing import Protocol

class LLM(Protocol):
    def complete(self, prompt: str) -> str: ...


class OpenAIClient:
    """
    Minimal adapter for the new OpenAI Responses API.
    Compatible with 'gpt-4.1', 'gpt-4o', 'gpt-5', etc.
    """

    def __init__(self, client):
        self._client = client

    def complete(self, prompt: str) -> str:
        # New responses API doesn’t support `temperature`
        resp = self._client.responses.create(
            model="gpt-5",
            input=prompt,
        )
        # .output_text gives the concatenated text output
        return resp.output_text.strip()