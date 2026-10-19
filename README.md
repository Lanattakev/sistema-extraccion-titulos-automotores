# Extracción y registro de datos de títulos automotores

Backend para cargar títulos automotores, proponer sus datos principales y registrar ingresos de vehículos. Busca reducir la transcripción manual mediante extracción conservadora y revisión humana.

## Estado del MVP

MVP local con FastAPI, Swagger y persistencia SQLite. La extracción funciona sobre PDF con texto extraíble. **El OCR con Tesseract está en preparación y no está terminado ni integrado en la API.** Cargar una imagen no implica extraer su texto.

## Funcionalidades implementadas

- Carga de un archivo PDF, JPG/JPEG o PNG por solicitud, de hasta 10 MiB, con validación de nombre, extensión y contenido no vacío.
- Almacenamiento en `uploads/` con nombre interno UUID y metadatos JSON.
- Extracción de texto de PDF con `pypdf`. Un PDF sin texto devuelve `requiere_ocr = true`; no ejecuta OCR. Los PDF inválidos o cifrados producen un error.
- Propuesta de `patente`, `marca`, `modelo`, `numero_motor`, `numero_chasis` y `anio` mediante etiquetas y reglas. Campos ausentes, inválidos o sin un candidato válido único quedan en `null`; las propuestas llevan `requiere_revision = true`.
- Alta y consulta de registros completos en SQLite, con UUID, fecha de ingreso, archivo de origen y marca de revisión.
- Tests unitarios, de integración, de endpoints y de restricciones arquitectónicas.

La propuesta de campos no guarda automáticamente un vehículo. El operador debe revisar y completar los datos antes del alta; esta exige los seis campos y `archivo_origen`. Este último es una referencia textual: el alta no comprueba que corresponda a un documento cargado. Los ingresos se crean con `requiere_revision = true`; todavía no hay endpoint de aprobación.

## Funcionalidades pendientes

- **En preparación:** OCR con Tesseract para imágenes y PDF escaneados.
- **Futuras, sin implementación actual:** flujo de corrección y aprobación, vinculación verificada entre documento y registro, interfaz dedicada de revisión y controles de autenticación y autorización.

## Tecnologías

Python 3.10 o superior, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, python-multipart y pypdf. Persistencia con `sqlite3` de la biblioteca estándar; aunque la URL predeterminada incluye `sqlite+aiosqlite`, el repositorio actual utiliza `sqlite3` síncrono. Pruebas con pytest, pytest-asyncio y HTTPX; análisis estático con Ruff.

## Instalación y ejecución local

Desde la raíz del proyecto, crear y activar un entorno virtual. En PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

En Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` incluye las dependencias de ejecución y las herramientas de calidad. Para instalar únicamente las de ejecución, usar `python -m pip install -r requirements.txt`. Estos archivos incluyen las dependencias de carga y extracción de PDF necesarias para el MVP.

No hace falta un archivo `.env` para la ejecución predeterminada. La configuración se carga desde variables de entorno o un `.env` local mediante `src/infrastructure/settings/config.py`.

```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

Con los valores predeterminados:

- Swagger: http://127.0.0.1:8000/api/v1/docs
- OpenAPI: http://127.0.0.1:8000/api/v1/openapi.json
- Salud: http://127.0.0.1:8000/health

SQLite crea la tabla al iniciar la aplicación y usa `app.db` en el directorio de ejecución (`DATABASE_URL` predeterminada: `sqlite+aiosqlite:///./app.db`). Los documentos y sus metadatos se guardan en `uploads/` en la raíz del proyecto. Cambiar `API_V1_PREFIX` modifica las rutas de la API y Swagger.

## Uso por Swagger

| Método y ruta predeterminada | Operación |
| --- | --- |
| `POST /api/v1/documents` | Cargar un documento en el campo multipart `file` |
| `POST /api/v1/documents/{id_documento}/extract-text` | Extraer texto de un PDF cargado |
| `POST /api/v1/documents/{id_documento}/extract-fields` | Proponer los seis campos desde el texto del PDF |
| `POST /api/v1/vehicles` | Registrar datos completos revisados por el operador |
| `GET /api/v1/vehicles` | Listar ingresos |
| `GET /api/v1/vehicles/{id}` | Consultar un ingreso por su identificador |

Para probar el flujo, usar únicamente un PDF sintético con texto: cargarlo, conservar su `id_documento`, solicitar la propuesta, revisar los campos y realizar el alta por separado. La extracción sobre imágenes devuelve HTTP 415 en el estado actual.

## Verificaciones

Con el entorno activado y desde la raíz:

```bash
pytest -q
ruff check .
```

`pytest` ejecuta la suite configurada en `tests/`; `ruff check .` informa problemas de lint sin corregir archivos. La existencia de estas verificaciones no garantiza precisión de extracción sobre cualquier formato de título.

## Estructura del proyecto

```text
src/
  main.py                          # Aplicación ASGI e inicialización
  domain/vehicle_record.py         # Registros y validaciones
  application/title_field_extraction.py
                                   # Propuesta de campos sin I/O
  adapters/                        # Paquete sin adaptadores implementados
  infrastructure/
    fastapi/routers/               # Documentos y vehículos
    persistence/                   # Archivos locales y SQLite
    pdf_text_extraction.py         # Extracción con pypdf
    settings/                      # Configuración y logging
tests/
  unit/
  integration/
  e2e/
  test_*.py                        # Documentos y controles de arquitectura
docs/
  srs-spec-backend-fastapi.md
  guia-andamiaje-proyectos.md
requirements.txt
requirements-dev.txt
pyproject.toml
run.sh                             # Utilidades para Bash
```

El SRS se está completando por etapas: las secciones 1.1 a 2.3 describen el contexto actual; el resto conserva contenido de plantilla que requiere revisión y no acredita funcionalidades implementadas.

## Seguridad y privacidad

Usar documentos sintéticos para desarrollo, pruebas y ejemplos. No publicar títulos reales, datos personales, uploads, metadatos, bases SQLite ni secretos. `.gitignore` excluye `uploads/`, `*.db`, `*.sqlite3`, `.env` y `.env.*`, salvo `.env.example`.

Los UUID evitan usar el nombre original como ruta, pero los metadatos conservan ese nombre. La carga valida extensión y tamaño; no incorpora análisis antivirus ni certifica el contenido por su extensión. La API actual carece de autenticación y autorización; su configuración predeterminada de CORS es permisiva. Mantener la ejecución de evaluación en localhost. No se declara cifrado de archivos o SQLite, política automatizada de retención ni preparación para producción.

## Roadmap breve

1. Completar e integrar OCR con Tesseract, validándolo con documentos sintéticos.
2. Incorporar revisión, corrección y aprobación explícitas, junto con vinculación documental verificada.
3. Definir controles de acceso, retención de documentos y condiciones de despliegue antes de habilitar uso compartido.
