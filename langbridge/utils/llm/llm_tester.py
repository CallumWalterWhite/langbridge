from typing import Dict, Any, Optional
from openai import OpenAI, OpenAIError
from schemas.llm_connections import LLMProvider

class LLMConnectionTester:
    def test_connection(
        self,
        provider: LLMProvider,
        api_key: str,
        model: str,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Test the LLM connection by attempting to make a simple API call.
        Returns a dictionary with 'success' boolean and 'message' string.
        """
        try:
            if provider == LLMProvider.OPENAI:
                return self._test_openai(api_key, model, configuration)
            elif provider == LLMProvider.AZURE:
                return self._test_azure(api_key, model, configuration)
            else:
                return {
                    "success": False,
                    "message": f"Unsupported provider: {provider}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}"
            }

    def _test_openai(
        self,
        api_key: str,
        model: str,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Test OpenAI connection with a simple completion request."""
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return {
                "success": True,
                "message": "Successfully connected to OpenAI API"
            }
        except OpenAIError as e:
            return {
                "success": False,
                "message": f"OpenAI API error: {str(e)}"
            }

    def _test_azure(
        self,
        api_key: str,
        model: str,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Test Azure OpenAI connection."""
        try:
            if not configuration or not configuration.get("api_base"):
                return {
                    "success": False,
                    "message": "Azure OpenAI requires api_base in configuration"
                }

            client = OpenAI(
                api_key=api_key,
                base_url=configuration["api_base"]
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return {
                "success": True,
                "message": "Successfully connected to Azure OpenAI API"
            }
        except OpenAIError as e:
            return {
                "success": False,
                "message": f"Azure OpenAI API error: {str(e)}"
            }