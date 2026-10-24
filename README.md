# Extracción y registro de datos de títulos automotores

Backend para cargar títulos automotores, proponer sus datos principales y registrar ingresos de vehículos. Busca reducir la transcripción manual mediante extracción conservadora y revisión humana.

## Estado del MVP

MVP local con FastAPI, Swagger y persistencia SQLite. La extracción funciona sobre PDF con texto extraíble mediante pypdf y sobre JPG/JPEG/PNG mediante OCR local con Tesseract, pytesseract y Pillow. El OCR de imágenes está implementado y probado con mocks; esto no acredita precisión sobre documentos reales. El fallback OCR para PDF escaneado también está implementado. En PDF se intenta pypdf primero: si el parser no obtiene ningún campo válido del texto directo, se renderizan las páginas con pypdfium2 y se aplica el OCR existente con Tesseract.

## Funcionalidades implementadas

- Carga de un archivo PDF, JPG/JPEG o PNG por solicitud, de hasta 10 MiB, con validación de nombre, extensión y contenido no vacío.
- Almacenamiento en `uploads/` con nombre interno UUID y metadatos JSON.
- Extracción de texto de PDF con `pypdf` primero. Si el parser existente reconoce al menos uno de los seis campos, se usa ese texto sin OCR. Si no reconoce ninguno, incluso cuando hay texto auxiliar de impresión, se renderizan las páginas con `pypdfium2`, se aplica Tesseract y se une el texto en orden. Si el OCR no obtiene texto útil, la respuesta queda vacía con `requiere_ocr = true`. Los PDF inválidos o cifrados producen un error.
- OCR local de JPG/JPEG/PNG cargados, separado de FastAPI. Si no obtiene texto útil, devuelve texto vacío y una respuesta controlada; los campos quedan en `null`. Las imágenes ilegibles y los errores de Tesseract producen un error controlado.
- Propuesta de `patente`, `marca`, `modelo`, `numero_motor`, `numero_chasis` y `anio` mediante el parser existente de etiquetas y reglas, reutilizado para texto directo de PDF y texto de OCR de imágenes o páginas PDF. Campos ausentes, inválidos o sin un candidato válido único quedan en `null`; las propuestas llevan `requiere_revision = true`.
- Confirmación humana mediante `POST /api/v1/documents/{id_documento}/confirm`: recibe los seis campos revisados/corregidos, valida mediante `VehicleRecord`, toma el nombre original del documento como `archivo_origen` y persiste un `VehicleIntake` en SQLite con `requiere_revision = false`. Devuelve el registro creado con HTTP 201. Las correcciones humanas prevalecen sobre OCR; la confirmación no vuelve a ejecutar la extracción.
- Alta y consulta de registros completos en SQLite, con UUID, fecha de ingreso, archivo de origen y marca de revisión.
- Tests unitarios, de integración, de endpoints y de restricciones arquitectónicas.

`extract-fields` propone los seis campos con `requiere_revision = true` y no guarda automáticamente un `VehicleRecord`. El usuario revisa/corrige esos campos y los envía a `/confirm`, que verifica la existencia del documento y obtiene su nombre original como `archivo_origen`; este valor no se recibe del usuario. Documento inexistente devuelve HTTP 404 y datos inválidos HTTP 422. El `VehicleIntake` confirmado se guarda y devuelve con `requiere_revision = false`.

El alta independiente `POST /api/v1/vehicles` conserva su comportamiento: exige los seis campos y `archivo_origen` como referencia textual, no verifica un documento cargado y crea ingresos con `requiere_revision = true`.

## Funcionalidades pendientes

- **Futuras, sin implementación actual:** interfaz dedicada de revisión y controles de autenticación y autorización. La revisión/corrección y confirmación ya pueden realizarse mediante la API o Swagger; todavía no hay frontend dedicado.

## Tecnologías

Python 3.10 o superior, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, python-multipart, pypdf, pypdfium2, pytesseract 0.3.13 y Pillow. El OCR de imágenes y páginas PDF renderizadas utiliza el ejecutable local de Tesseract. Persistencia con `sqlite3` de la biblioteca estándar; aunque la URL predeterminada incluye `sqlite+aiosqlite`, el repositorio actual utiliza `sqlite3` síncrono. Pruebas con pytest, pytest-asyncio y HTTPX; análisis estático con Ruff.

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

`requirements-dev.txt` incluye las dependencias de ejecución y las herramientas de calidad. Para instalar únicamente las de ejecución, usar `python -m pip install -r requirements.txt`. Estos archivos incluyen las dependencias de carga, extracción y renderizado de PDF y OCR de imágenes necesarias para el MVP. El ejecutable de Tesseract y sus idiomas deben estar instalados por separado.

No hace falta un archivo `.env` para la ejecución predeterminada. La configuración se carga desde variables de entorno o un `.env` local mediante `src/infrastructure/settings/config.py`. Para OCR, `TESSERACT_CMD` tiene como valor predeterminado `C:\Program Files\Tesseract-OCR\tesseract.exe`, `TESSERACT_LANG` es `spa+eng` y `TESSERACT_TIMEOUT` es 30 segundos. La ruta debe ajustarse si Tesseract está instalado en otra ubicación; los idiomas configurados deben estar disponibles localmente.

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
| `POST /api/v1/documents/{id_documento}/extract-text` | Extraer texto de PDF con pypdf primero y fallback OCR, o de JPG/JPEG/PNG con OCR local |
| `POST /api/v1/documents/{id_documento}/extract-fields` | Proponer los seis campos desde texto directo de PDF o texto de OCR de imágenes y PDF |
| `POST /api/v1/documents/{id_documento}/confirm` | Confirmar los seis campos revisados/corregidos y guardar el ingreso con `requiere_revision = false` |
| `POST /api/v1/vehicles` | Alta independiente con `archivo_origen` enviado por el usuario y `requiere_revision = true` |
| `GET /api/v1/vehicles` | Listar ingresos |
| `GET /api/v1/vehicles/{id}` | Consultar un ingreso por su identificador |

Para probar el flujo, usar un PDF sintético con texto, un PDF escaneado sintético o una imagen sintética JPG/JPEG/PNG: cargar el archivo, conservar su `id_documento`, solicitar la propuesta con `extract-fields`, revisar/corregir los seis campos y enviarlos a `POST /api/v1/documents/{id_documento}/confirm`. Las propuestas mantienen `requiere_revision = true`; el ingreso confirmado queda persistido con `requiere_revision = false`. Si el texto directo del PDF no aporta ningún campo válido al parser, se activa el fallback OCR. Un solo campo válido basta para conservar la extracción directa sin OCR; no se exige completar los seis campos.

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
    pdf_text_extraction.py         # pypdf primero; fallback pypdfium2 + OCR
    extracted_text.py              # Resultado compartido de extracción
    image_text_extraction.py       # OCR local con pytesseract y Pillow
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

## Procesamiento por lote

`POST /api/v1/documents/batch` recibe hasta 100 archivos PDF/JPG/JPEG/PNG en el campo multipart repetido `files`, con el mismo limite de 10 MiB por archivo del flujo individual.

Devuelve HTTP 200 con una lista en el orden de carga. Cada elemento incluye `id_documento`, `nombre_original`, los seis campos propuestos, `requiere_revision`, `fallo` y `error`. Las propuestas tienen `requiere_revision = true`, `fallo = false` y `error = null`. Si un archivo falla, su elemento incluye `fallo = true`, el motivo en `error`, campos nulos y `requiere_revision = false`; los siguientes archivos se siguen procesando. `id_documento` es nulo si fallo el almacenamiento; si fallo la extraccion, conserva el identificador del documento almacenado.

El lote almacena documentos y propone datos, sin guardar vehiculos. Cada propuesta se revisa y se confirma mediante `POST /api/v1/documents/{id_documento}/confirm`, como en el flujo individual. Una solicitud vacia o con campos distintos de `files` se rechaza; superar el limite de archivos rechaza la solicitud completa.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents/batch -F "files=@titulo.pdf" -F "files=@foto.png"
```

## Roadmap breve

1. Incorporar una interfaz dedicada de revisión y confirmación sobre el flujo ya disponible en la API.
2. Definir controles de acceso, retención de documentos y condiciones de despliegue antes de habilitar uso compartido.
