"""src/domain/repositories.py — Contratos de persistencia independientes del motor."""

from typing import Protocol, runtime_checkable

from src.domain.document_record import DocumentRecord
from src.domain.history_event import HistoryEvent
from src.domain.vehicle_record import VehicleIntake, VehicleRecord


class DocumentNotFoundError(LookupError):
    """El documento no tiene un flujo persistido."""


class DocumentConflictError(ValueError):
    """El documento ya fue registrado o la revision cambio."""


@runtime_checkable
class DocumentRepository(Protocol):
    """Persiste propuestas y transiciones documentales de forma atomica.

    review y confirm pueden lanzar DocumentNotFoundError o DocumentConflictError.
    save_pending conserva las revisiones humanas y los documentos registrados.
    """

    def save_pending(self, document: DocumentRecord) -> None: ...

    def list_all(self) -> list[DocumentRecord]: ...

    def review(self, document_id: str, vehicle: VehicleRecord) -> DocumentRecord: ...

    def confirm(self, document_id: str, vehicle: VehicleRecord) -> VehicleIntake: ...


@runtime_checkable
class VehicleRepository(Protocol):
    """Guarda ingresos y permite consultarlos en orden de insercion."""

    def save(self, intake: VehicleIntake) -> None: ...

    def get_by_id(self, id_interno: str) -> VehicleIntake | None: ...

    def list_all(self) -> list[VehicleIntake]: ...


@runtime_checkable
class HistoryRepository(Protocol):
    """Consulta eventos del mas reciente al mas antiguo.

    La escritura transaccional pertenece a la implementacion de persistencia;
    este contrato no expone conexiones ni transacciones del motor.
    """

    def list_all(self) -> list[HistoryEvent]: ...
