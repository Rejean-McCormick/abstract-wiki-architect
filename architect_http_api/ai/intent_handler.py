# architect_http_api/ai/intent_handler.py
from __future__ import annotations

from typing import List

from architect_http_api.schemas.ai import (
    AICommandRequest,
    AICommandResponse,
    AIFramePatch,
    AIIntentModelResponse,
)
from architect_http_api.services.ai_client import AIClient
from architect_http_api.ai.frame_builder import build_frame_patches


class IntentHandler:
    """
    High-level coordinator for the natural-language AI panel.

    Responsibility:
      1. Take an AICommandRequest (user message + current frames/context).
      2. Ask the LLM (via AIClient) to produce a structured "intent model".
      3. Convert that model into concrete frame patches using frame_builder.
      4. Return an AICommandResponse suitable for the /ai/intent HTTP route.

    All LLM-specific prompting and vendor details live in AIClient.
    All mapping from generic "actions" to concrete FramePatch objects
    lives in frame_builder.
    """

    def __init__(self, ai_client: AIClient) -> None:
        self._ai_client = ai_client

    async def handle_command(self, request: AICommandRequest) -> AICommandResponse:
        """
        Main entry point used by the /ai/intent router.

        The basic flow is:

          request (Pydantic model)  →  AIClient.infer_intent(...)
                                    →  AIIntentModelResponse (generic actions)
                                    →  build_frame_patches(...)
                                    →  AICommandResponse (patches + messages)
        """
        # 1. Let the AI backend interpret the user's natural-language command.
        model_response: AIIntentModelResponse = await self._ai_client.infer_intent(
            request=request
        )

        # 2. Turn generic "actions" from the model into concrete FramePatch objects.
        patches: List[AIFramePatch] = build_frame_patches(
            model_actions=model_response.actions,
            request=request,
        )

        # 3. Build the high-level response for the HTTP API.
        #    The exact fields here should mirror architect_http_api/schemas/ai.py
        #    (AICommandResponse).
        return AICommandResponse(
            workspace_slug=request.workspace_slug,
            lang=request.lang,
            user_message=request.message,
            assistant_messages=model_response.assistant_messages,
            intent_label=model_response.intent_label,
            patches=patches,
            # Optional debug field – only populated when caller requested it.
            debug=model_response.debug if request.debug else None,
        )
