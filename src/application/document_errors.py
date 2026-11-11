"""src/application/document_errors.py - Errores independientes del transporte."""


class InvalidDocument(ValueError):
    """Nombre, extension o contenido vacio no admitidos."""


class DocumentTooLarge(ValueError):
    """El documento supera el limite permitido."""


class UnsupportedDocument(ValueError):
    """El formato no tiene un motor de extraccion disponible."""


class InvalidUpload(ValueError):
    """La entrada de carga no contiene un archivo con nombre."""
