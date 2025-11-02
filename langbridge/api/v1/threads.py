import json
from typing import Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from errors.application_errors import BusinessValidationError
from services.orchestrator_service import OrchestratorService
from schemas.threads import ThreadChatRequest
from services.semantic_model_service import SemanticModelService
from ioc import Container

router = APIRouter(prefix="/thread", tags=["threads"])


@router.post("/", status_code=status.HTTP_201_CREATED)
@inject
async def chat_thread(
    request: ThreadChatRequest,
    orchestrator_service: OrchestratorService = Depends(Provide[Container.orchestrator_service]),
) -> PlainTextResponse:
    """Handle chat request within a thread."""
    try:
        response = await orchestrator_service.chat(
            msg=request.message,
        )

        content = {
            "result": response['result'],
            "visualization": response['visualization']
        }
        content_json = json.dumps(content)
        
        return PlainTextResponse(content=content_json, status_code=status.HTTP_201_CREATED)
    except BusinessValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e