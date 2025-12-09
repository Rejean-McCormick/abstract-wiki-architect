# architect_http_api/ai/intent_handler.py
from __future__ import annotations

import json
import re
import logging
from typing import List, Tuple, Any, Dict, Optional

from architect_http_api.schemas.ai import (
    AICommandRequest,
    AICommandResponse,
    AIFramePatch,
    AIMessage,
)
from architect_http_api.services.ai_client import AIClient
from architect_http_api.ai.frame_builder import build_frame_patches

logger = logging.getLogger(__name__)

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

    def _extract_json_block(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extracts the first valid JSON object from a string.
        Handles markdown fences (```json ... ```) and mixed text.
        """
        if not text:
            return None

        # 1. Try finding a markdown block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass  # Fallback to brute force

        # 2. Brute force: find the outer-most balanced braces
        # This handles cases where the LLM says "Sure! { ... } works."
        stack = 0
        start_index = -1
        
        for i, char in enumerate(text):
            if char == "{":
                if stack == 0:
                    start_index = i
                stack += 1
            elif char == "}":
                stack -= 1
                if stack == 0 and start_index != -1:
                    # Found a complete block
                    candidate = text[start_index : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # Continue searching if this block was invalid
                        # (e.g. inside a comment or string, though unlikely for outer block)
                        start_index = -1
                        continue
        
        return None

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
            "Return a JSON object with keys: 'intent', 'actions' (list of field updates), 'explanation'. "
            "Ensure the output is valid JSON."
        )
        
        # Serialize context for the prompt
        context_str = json.dumps(request.context_frame or {}, default=str, ensure_ascii=False)
        user_content = f"User Request: {request.message}\n\nCurrent Frame Context:\n{context_str}"
        
        messages = [{"role": "user", "content": user_content}]

        # 2. Call AI Client
        # Note: AIClient.chat is synchronous in your codebase
        ai_reply_text = self._ai_client.chat(messages, system_prompt=system_prompt)
        
        # 3. Parse LLM output (Robust)
        intent_label = "unknown"
        actions: List[Dict[str, Any]] = []
        explanation = ai_reply_text

        extracted_data = self._extract_json_block(ai_reply_text)
        
        if extracted_data:
            intent_label = extracted_data.get("intent", intent_label)
            actions = extracted_data.get("actions", [])
            explanation = extracted_data.get("explanation", explanation)
        else:
            logger.warning("Failed to extract JSON from AI response. Fallback to raw text.")

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