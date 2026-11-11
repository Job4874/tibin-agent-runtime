from typing import Dict, Any, List

class BaseWorker:
    """Base class for all workers. Workers are tools the agent can call."""

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """Return a JSON-compatible tool schema for LLM function calling.

        Schema format follows the OpenAI / Gemini function declaration spec:
        {
            "name": "tool_name",
            "description": "...",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        return {
            "name": cls.__name__,
            "description": "No description provided.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Worker must implement execute()")
