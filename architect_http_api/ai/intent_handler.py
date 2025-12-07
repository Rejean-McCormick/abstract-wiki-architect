# architect_http_api/ai/intent_handler.py
from __future__ import annotations

import json
from typing import List, Tuple, Any, Dict

from architect_http_api.schemas.ai import (
    AICommandRequest,
    AICommandResponse,
    AIFramePatch,
    AIMessage,
)
from architect_http_api.services.ai_client import AIClient
from architect_http_api.ai.frame_builder import build_frame_patches


class IntentHandler:
    """
    High-level coordinator for the natural-language AI panel.
    """

    def __init__(self, ai_client: AIClient) -> None:
        self._ai_client = ai_client

    async def infer_intent(self, request: AICommandRequest) -> AICommandResponse:
        """
        Alias for handle_command to satisfy Router usage.
        """
        return self.handle_command_sync(request)

    async def handle_command(self, request: AICommandRequest) -> AICommandResponse:
        """
        Async wrapper for handle_command_sync.
        """
        return self.handle_command_sync(request)

    def handle_command_sync(self, request: AICommandRequest) -> AICommandResponse:
        """
        Main logic for interpreting a user command.
        
        1. Calls AIClient (sync).
        2. Parses response.
        3. Builds patches.
        """
        # 1. Construct messages for the LLM
        system_prompt = (
            "You are an AI architect helper. "
            "Analyze the user request and the current frame context. "
            "Return a JSON object with keys: 'intent', 'actions' (list of field updates), 'explanation'."
        )
        
        # Serialize context for the prompt
        context_str = json.dumps(request.context_frame or {}, default=str, ensure_ascii=False)
        user_content = f"User Request: {request.message}\n\nCurrent Frame Context:\n{context_str}"
        
        messages = [{"role": "user", "content": user_content}]

        # 2. Call AI Client
        # Note: AIClient.chat is synchronous in your codebase
        ai_reply_text = self._ai_client.chat(messages, system_prompt=system_prompt)
        
        # 3. Parse LLM output (Mocking parsing logic for robustness)
        # In a real implementation, we would robustly parse JSON from ai_reply_text.
        # Here we assume a simple structure or fallback.
        intent_label = "unknown"
        actions: List[Dict[str, Any]] = []
        explanation = ai_reply_text

        # Basic heuristic parsing if LLM returned JSON
        try:
            # Find first '{' and last '}'
            start = ai_reply_text.find("{")
            end = ai_reply_text.rfind("}")
            if start != -1 and end != -1:
                json_str = ai_reply_text[start : end + 1]
                data = json.loads(json_str)
                intent_label = data.get("intent", intent_label)
                actions = data.get("actions", [])
                explanation = data.get("explanation", ai_reply_text)
        except Exception:
            pass # Fallback to raw text as explanation

        # 4. Build Patches
        patches: List[AIFramePatch] = build_frame_patches(
            model_actions=actions,
            request=request,
        )

        # 5. Construct Response
        return AICommandResponse(
            workspace_slug=request.workspace_slug,
            lang=request.lang,
            user_message=request.message,
            assistant_messages=[AIMessage(role="assistant", content=explanation)],
            intent_label=intent_label,
            patches=patches,
            debug={"raw_llm_response": ai_reply_text} if request.debug else None,
        )


def interpret_command(command: AICommandRequest) -> Tuple[List[AIFramePatch], List[AIMessage]]:
    """
    Standalone entry point used by `architect_http_api.ai.__init__.py`.
    
    This instantiates a default AIClient and runs the handler synchronously.
    Returns: (patches, messages)
    """
    client = AIClient()  # Uses env vars config
    handler = IntentHandler(client)
    
    response = handler.handle_command_sync(command)
    
    return response.patches, response.assistant_messages