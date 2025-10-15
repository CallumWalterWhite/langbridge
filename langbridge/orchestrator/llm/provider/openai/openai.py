from orchestrator.llm.provider.base import LLMProviderName

class OpenAIProvider:
    name = LLMProviderName.OPENAI

    def get_model(self, model_name: str) -> str:
        return model_name