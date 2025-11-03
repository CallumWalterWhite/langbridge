from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from errors.application_errors import BusinessValidationError
from services.orchestrator_service import OrchestratorService
from schemas.threads import ThreadChatRequest
from ioc import Container

router = APIRouter(prefix="/thread", tags=["threads"])


@router.post("/", status_code=status.HTTP_201_CREATED)
@inject
async def chat_thread(
    request: ThreadChatRequest,
    orchestrator_service: OrchestratorService = Depends(Provide[Container.orchestrator_service]),
) -> JSONResponse:
    """Handle chat request within a thread."""
    try:
        response = await orchestrator_service.chat(
            msg=request.message,
        )

        content = {
            "result": response.get("result"),
            "visualization": response.get("visualization"),
            "summary": response.get("summary"),
        }

        return JSONResponse(content=content, status_code=status.HTTP_201_CREATED)
    except BusinessValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
