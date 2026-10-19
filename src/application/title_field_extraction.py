"""src/application/title_field_extraction.py

Propuestas conservadoras a partir del texto de un titulo, sin I/O.
"""

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class ProposedVehicleFields:
    id_documento: str
    patente: str | None = None
    marca: str | None = None
    modelo: str | None = None
    numero_motor: str | None = None
    numero_chasis: str | None = None
    anio: int | None = None
    requiere_revision: Literal[True] = True


_NUMBER = r"(?:n[uú]mero\s*(?:de\s+)?|nro\.?\s*|n[°ºo.]\s*(?:de\s+)?)"
_YEAR = r"a(?:[nñ]|ni)o"
_LABELS = {
    # Delimitan valores sin aportar candidatos a los seis campos.
    "auxiliar": (
        rf"(?:mca\.?|marca)\s+(?:chasis|motor)|fabricaci[oó]n\s+{_YEAR}"
        r"|fecha\s+(?:de\s+)?(?:adquisici[oó]n|inscripci[oó]n|emisi[oó]n|nacimiento|vencimiento)"
    ),
    # La expresion completa debe preceder a 'modelo' para no perder su valor.
    "anio": rf"modelo\s+{_YEAR}|{_YEAR}(?:\s+(?:del?\s+)?(?:modelo|fabricaci[oó]n))?",
    "patente": rf"(?:{_NUMBER})?dominio|patente",
    "marca": r"marca",
    "modelo": r"modelo",
    "numero_motor": rf"(?:{_NUMBER})?motor(?:\s+{_NUMBER})?",
    "numero_chasis": rf"(?:{_NUMBER})?chasis(?:\s*/\s*cuadro)?|vin",
}
_LABEL_PATTERN = re.compile(
    r"(?<!\S)(?:" + "|".join(f"(?P<{key}>{label})" for key, label in _LABELS.items())
    + r")(?!\w)(?:[^\S\n]*[:=][^\S\n]*|(?=\s|$))",
    re.IGNORECASE,
)


def _clean_value(field: str, raw: str) -> str | int | None:
    """Acepta un solo valor legible; no completa identificadores incompletos."""
    lines = raw.strip(" \t\r\n:;|=").splitlines()
    value = " ".join(lines[0].split()).strip(" ;|") if lines else ""
    if not value or value.upper() in {"NO CONSTA", "SIN DATOS", "S/D", "N/A"}:
        return None
    if field == "patente":
        value = re.sub(r"[\s-]", "", value).upper()
        return value if re.fullmatch(r"(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})", value) else None
    if field == "anio":
        return int(value) if re.fullmatch(r"(?:18|19|20)\d{2}", value) else None
    return _clean_identifier_or_name(field, value)


def _clean_identifier_or_name(field: str, value: str) -> str | None:
    if field in {"numero_motor", "numero_chasis"}:
        return value.upper() if re.fullmatch(r"[A-Za-z0-9]+(?:[-./][A-Za-z0-9]+)*", value) else None
    value = re.sub(r"^\d+\s*-\s*", "", value)
    return value if re.fullmatch(r"[^\W_][\w .,/()+-]*", value) else None


def extract_title_fields(id_documento: str, text: str) -> ProposedVehicleFields:
    """Busca etiquetas sin asumir su orden; valores contradictorios quedan vacios.

    El valor puede estar en la linea siguiente. No se unen lineas de valores
    libres porque podrian pertenecer a otra seccion del documento.
    """
    proposal = ProposedVehicleFields(id_documento=id_documento)
    matches = list(_LABEL_PATTERN.finditer(text))
    candidates: dict[str, dict[str, str | int]] = {}
    for index, match in enumerate(matches):
        field = match.lastgroup
        if field is None or field == "auxiliar":
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = _clean_value(field, text[match.end():end])
        if value is not None:
            candidates.setdefault(field, {}).setdefault(str(value).casefold(), value)
    for field, values in candidates.items():
        if len(values) == 1:
            setattr(proposal, field, next(iter(values.values())))
    return proposal
