"""src/infrastructure/fastapi/routers/history.py"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from src.domain.history_event import HistoryEvent
from src.domain.repositories import HistoryRepository

router = APIRouter(prefix="/history", tags=["History"])


def get_history_repository(request: Request) -> HistoryRepository:
    return request.app.state.history_repository


@router.get("", response_model=list[HistoryEvent])
def list_history(repository: Annotated[HistoryRepository, Depends(get_history_repository)]) -> list[HistoryEvent]:
    return repository.list_all()
