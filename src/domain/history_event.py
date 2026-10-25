"""src/domain/history_event.py"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

HistoryEventType = Literal["documento_cargado", "documento_revisado", "documento_registrado"]


@dataclass
class HistoryEvent:
    id_documento: str
    tipo_evento: HistoryEventType
    nombre_original: str
    id_evento: str = field(default_factory=lambda: str(uuid4()))
    fecha_evento: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
