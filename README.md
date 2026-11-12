# Extracción y registro de datos de títulos automotores

Aplicación local con backend FastAPI y SPA React 19 para cargar títulos automotores, proponer sus datos principales, revisarlos y registrar ingresos de vehículos. Busca reducir la transcripción manual mediante extracción conservadora y revisión humana.

## Estado del MVP

MVP local con SPA React 19, TypeScript y Vite, API FastAPI, Swagger y persistencia SQLite. La extracción funciona sobre PDF con texto extraíble mediante pypdf y sobre JPG/JPEG/PNG mediante OCR local con Tesseract, pytesseract y Pillow. El OCR de imágenes está implementado y probado con mocks; esto no acredita precisión sobre documentos reales. El fallback OCR para PDF escaneado también está implementado. En PDF se intenta pypdf primero: si el parser no obtiene ningún campo válido del texto directo, se renderizan las páginas con pypdfium2 y se aplica el OCR existente con Tesseract.

## Funcionalidades implementadas

- Carga de un archivo PDF, JPG/JPEG o PNG por solicitud, de hasta 10 MiB, con validación de nombre, extensión y contenido no vacío.
- Almacenamiento en `uploads/` con nombre interno UUID y metadatos JSON.
- Extracción de texto de PDF con `pypdf` primero. Si el parser existente reconoce al menos uno de los seis campos, se usa ese texto sin OCR. Si no reconoce ninguno, incluso cuando hay texto auxiliar de impresión, se renderizan las páginas con `pypdfium2`, se aplica Tesseract y se une el texto en orden. Si el OCR no obtiene texto útil, la respuesta queda vacía con `requiere_ocr = true`. Los PDF inválidos o cifrados producen un error.
- OCR local de JPG/JPEG/PNG cargados, separado de FastAPI. Si no obtiene texto útil, devuelve texto vacío y una respuesta controlada; los campos quedan en `null`. Las imágenes ilegibles y los errores de Tesseract producen un error controlado.
- Propuesta de `patente`, `marca`, `modelo`, `numero_motor`, `numero_chasis` y `anio` mediante el parser existente de etiquetas y reglas, reutilizado para texto directo de PDF y texto de OCR de imágenes o páginas PDF. Campos ausentes, inválidos o sin un candidato válido único quedan en `null`; las propuestas llevan `requiere_revision = true`.
- Confirmación humana mediante `POST /api/v1/documents/{id_documento}/confirm`: recibe los seis campos revisados/corregidos, valida mediante `VehicleRecord`, toma el nombre original del documento como `archivo_origen` y persiste un `VehicleIntake` en SQLite con `requiere_revision = false`. Devuelve el registro creado con HTTP 201. Las correcciones humanas prevalecen sobre OCR; la confirmación no vuelve a ejecutar la extracción.
- Alta y consulta de registros completos en SQLite, con UUID, fecha de ingreso, archivo de origen y marca de revisión.
- SPA para carga por lote, revisión/corrección, confirmación individual o múltiple, consulta de documentos y vehículos, exportación CSV, historial y métricas calculadas desde datos persistidos. La confirmación múltiple de la SPA solo incluye documentos revisados.
- Estados documentales `pendiente`, `revisado` y `registrado`, con historial transaccional de carga, revisión y registro. El historial no identifica operadores porque no hay autenticación.
- Tests unitarios, de integración, de endpoints y de restricciones arquitectónicas.

`extract-fields` propone los seis campos con `requiere_revision = true` y no guarda automáticamente un `VehicleRecord`. El usuario revisa/corrige esos campos y los envía a `/confirm`, que verifica la existencia del documento y obtiene su nombre original como `archivo_origen`; este valor no se recibe del usuario. Documento inexistente devuelve HTTP 404 y datos inválidos HTTP 422. El `VehicleIntake` confirmado se guarda y devuelve con `requiere_revision = false`.

El alta independiente `POST /api/v1/vehicles` conserva su comportamiento: exige los seis campos y `archivo_origen` como referencia textual, no verifica un documento cargado y crea ingresos con `requiere_revision = true`.

## Funcionalidades pendientes

- **Futuras, sin implementación actual:** autenticación/autorización, hash y deduplicación de documentos, notificaciones y políticas automatizadas de retención. Configuración conserva opciones visuales de demostración; no administra usuarios ni habilita notificaciones reales.

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

## SPA: instalación, ejecución y arquitectura

Frontend: React 19, TypeScript 6 y Vite 8. Requiere Node 22.12 o superior de la rama 22, o una versión posterior compatible con Vite, y npm. Con el backend en `http://127.0.0.1:8000`, abrir otra terminal desde la raíz:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Abrir la URL informada por Vite (normalmente `http://127.0.0.1:5173`). `npm run dev` también inicia el servidor de desarrollo. `npm ci` instala las versiones de `frontend/package-lock.json`.

El cliente tiene la base `http://127.0.0.1:8000/api/v1` definida en `frontend/src/services/api.ts`; no utiliza proxy de Vite ni una variable `VITE_API_URL`. Si se cambia el puerto o el prefijo de la API, hay que alinear ese cliente. CORS debe permitir el origen del frontend; `ALLOWED_HOSTS` configura los orígenes CORS pese a su nombre y su valor predeterminado es permisivo.

`App.tsx` coordina las vistas y comparte los hooks `useVehicles`, `useHistory` y `useDocumentConfirmation`. `views/` contiene Inicio, Carga, Vehículos, Métricas, Historial, Configuración y Ayuda; `components/` contiene carga, revisión, tablas y gráficos; `services/api.ts` valida las respuestas HTTP; `types/` declara contratos y `utils/` calcula búsquedas, CSV y métricas. La navegación es estado React local, sin router de URLs. Las vistas operativas consultan la API; no sustituyen errores o listas vacías con datos de ejemplo. Configuración conserva opciones de demostración y el tema vive durante la sesión.

Para usar el flujo: cargar archivos, procesar el lote, revisar/corregir los seis campos, guardar la revisión y confirmar. La SPA recupera los estados persistidos al volver a abrirse y bloquea confirmaciones duplicadas. La API mantiene la confirmación directa compatible de un pendiente con seis campos revisados explícitamente.

```bash
npm test
npm run lint
npm run build
npm run preview -- --host 127.0.0.1
```

`npm test` ejecuta `node --test tests/*.test.mjs`: actualmente son 78 tests de lógica, cliente HTTP, controladores y renderizado con simulaciones; no son pruebas de navegador ni OCR real. `preview` requiere el build y sirve para evaluarlo localmente. Desde Bash en la raíz, `bash run.sh frontend-test` ejecuta la misma suite sin crear un entorno Python. Más detalles en [frontend/README.md](frontend/README.md).

## Uso por Swagger

| Método y ruta predeterminada | Operación |
| --- | --- |
| `POST /api/v1/documents` | Cargar un documento en el campo multipart `file` |
| `GET /api/v1/documents` | Recuperar documentos y sus estados persistidos |
| `PATCH /api/v1/documents/{id_documento}/review` | Guardar los seis campos revisados |
| `POST /api/v1/documents/batch` | Cargar y extraer un lote sin confirmar ingresos |
| `POST /api/v1/documents/{id_documento}/extract-text` | Extraer texto de PDF con pypdf primero y fallback OCR, o de JPG/JPEG/PNG con OCR local |
| `POST /api/v1/documents/{id_documento}/extract-fields` | Proponer los seis campos desde texto directo de PDF o texto de OCR de imágenes y PDF |
| `POST /api/v1/documents/{id_documento}/confirm` | Confirmar los seis campos revisados/corregidos y guardar el ingreso con `requiere_revision = false` |
| `POST /api/v1/vehicles` | Alta independiente con `archivo_origen` enviado por el usuario y `requiere_revision = true` |
| `GET /api/v1/vehicles` | Listar ingresos |
| `GET /api/v1/vehicles/{id}` | Consultar un ingreso por su identificador |
| `GET /api/v1/history` | Consultar eventos de carga, revisión y registro |

Para probar el flujo, usar un PDF sintético con texto, un PDF escaneado sintético o una imagen sintética JPG/JPEG/PNG: cargar el archivo, conservar su `id_documento`, solicitar la propuesta con `extract-fields`, revisar/corregir los seis campos y enviarlos a `POST /api/v1/documents/{id_documento}/confirm`. Las propuestas mantienen `requiere_revision = true`; el ingreso confirmado queda persistido con `requiere_revision = false`. Si el texto directo del PDF no aporta ningún campo válido al parser, se activa el fallback OCR. Un solo campo válido basta para conservar la extracción directa sin OCR; no se exige completar los seis campos.

## Verificaciones

Con el entorno activado y desde la raíz:

```bash
pytest -q
ruff check .
ruff format --check .
pyright src/
```

`pytest` ejecuta la suite configurada en `tests/`; `ruff check .` informa problemas de lint sin corregir archivos. La existencia de estas verificaciones no garantiza precisión de extracción sobre cualquier formato de título.

## Estructura del proyecto

```text
src/
  main.py                          # Aplicación ASGI e inicialización
  domain/vehicle_record.py         # Registros y validaciones
  application/dtos/                # Datos de entrada, carga y resultados
  application/use_cases/           # Carga, extraccion, revision, confirmacion y lotes
  application/text_extraction.py   # Contrato de estrategias y politica de fallback PDF
  application/title_field_extraction.py
                                   # Propuesta de campos sin I/O
  adapters/                        # Paquete sin adaptadores implementados
  infrastructure/
    fastapi/routers/               # Documentos y vehículos
    persistence/                   # Archivos locales y SQLite
    extraction/                    # Motores PDF/OCR y fabrica por MIME
    pdf_text_extraction.py         # Funciones PDF compatibles con versiones previas
    extracted_text.py              # Resultado compartido de extracción
    image_text_extraction.py       # Funciones OCR compatibles con versiones previas
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
frontend/
  src/App.tsx                      # Coordinación de vistas y estado compartido
  src/views/                       # Vistas de la SPA
  src/components/                  # Componentes reutilizables
  src/hooks/                       # Consultas y flujo de revisión/confirmación
  src/services/api.ts              # Cliente HTTP y validación de respuestas
  src/types/                       # Contratos TypeScript
  src/utils/                       # Métricas, búsqueda y CSV
  tests/                           # Runner nativo de Node
  package-lock.json                # Dependencias reproducibles de frontend
```

El [SRS canónico](docs/srs-spec-backend-fastapi.md) describe requisitos, arquitectura, límites y verificaciones. Distingue comportamiento implementado de objetivos pendientes: no se han acreditado SLO de latencia/concurrencia, hash documental ni precisión de OCR real.

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

1. Definir y medir objetivos de latencia/concurrencia; evaluar hash documental, deduplicación y paralelismo interno del lote.
2. Definir controles de acceso, retención de documentos y condiciones de despliegue antes de habilitar uso compartido.

## Contratos de repositorios (issue #2)

`src/domain/repositories.py` define `DocumentRepository`, `VehicleRepository` y
`HistoryRepository` mediante `typing.Protocol`, sin dependencias de FastAPI ni SQLite.
Los routers consumen estos contratos; `src/main.py` conserva la composicion de las
implementaciones SQLite. Estas declaran explicitamente sus protocolos y mantienen
las consultas, migraciones y transacciones existentes.

Los errores `DocumentNotFoundError` y `DocumentConflictError` pertenecen al contrato
de dominio. Sus imports anteriores desde `sqlite_document_repository` siguen siendo
validos y conservan la misma identidad. La API mantiene las respuestas HTTP 404/409.
El contrato de historial solo expone lectura: la escritura con conexion SQLite sigue
siendo un detalle interno para preservar la atomicidad de documento, ingreso e historial.

Las pruebas `tests/unit/test_repository_contracts.py` ejercitan los routers con
repositorios en memoria; `tests/integration/test_repository_contracts.py` verifica
los contratos con SQLite y la compatibilidad de los errores. Desde la raiz, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
.\.venv\Scripts\python.exe -X utf8 tests/test_architecture.py
.\.venv\Scripts\python.exe -X utf8 tests/test_clean_design.py --strict
.\.venv\Scripts\python.exe -X utf8 tests/test_god_components.py --strict
```

La etapa #2 agrego contratos sin mover los DTOs ni los casos de uso. La separacion
de estos componentes se describe a continuacion para el issue #3.


## Casos de uso y DTOs (issue #3)

Los DTOs se definen en `src/application/dtos/`: entradas vehiculares estrictas,
metadatos de documento, texto extraido, campos propuestos y resultados de lote.
Los imports anteriores de los DTOs se conservan como reexportaciones de las mismas
clases. La comparacion de OpenAPI anterior y posterior a esta etapa no presenta cambios.

`src/application/use_cases/` coordina la carga, extraccion de texto y campos,
revision, confirmacion, alta independiente y procesamiento por lote. Recibe
repositorios de dominio y funciones inyectadas para el almacenamiento y los motores;
no importa FastAPI, Starlette, SQLite, lectores PDF ni Tesseract. Los errores de
carga y extraccion son independientes del transporte en `application/document_errors.py`.

La capa HTTP valida el multipart, mantiene los limites existentes y delega en los
casos de uso. `infrastructure/fastapi/document_dependencies.py` compone los casos
con las implementaciones actuales y `document_http.py` traduce los errores a los
mismos estados HTTP 400/404/409/413/415/422. Los endpoints no coordinan persistencia
ni seleccionan motores de extraccion y no superan 20 lineas.

El lote procesa un archivo por vez, en orden, ejecutando el trabajo bloqueante
fuera del event loop mediante `asyncio.to_thread`. Cada fallo se devuelve por archivo
y permite continuar; conserva el ID si el archivo se almaceno antes del error de
extraccion. Una extraccion fallida no agrega un pendiente a SQLite, como antes.
La API individual mantiene el registro pendiente despues de una carga correcta.
La confirmacion y el historial conservan las transacciones SQLite existentes.

La etapa #3 traslado la seleccion de PDF/JPEG/PNG a infraestructura conservando
los motores y el fallback OCR. La evolucion de estrategias del issue #4 se describe
a continuacion. Las herramientas (#5) y el SRS (#6) son etapas independientes.

Desde la raiz, las nuevas verificaciones aisladas pueden ejecutarse en PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/unit/test_document_use_cases.py tests/unit/test_document_http_contracts.py
```

La suite completa y las auditorias se ejecutan con los comandos de la seccion anterior.
Las pruebas usan documentos sinteticos y OCR simulado; no certifican precision de
Tesseract con titulos reales. La ejecucion del servidor sigue siendo
`python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000`.


## Estrategias de extraccion y fabrica (issue #4)

`application/text_extraction.py` define el protocolo `TextExtractor` y la politica
`PdfTextExtractor`. El contrato recibe los metadatos `Document` y la ruta local,
y devuelve el DTO `ExtractedText`; evita cargar todos los bytes del archivo y
conserva los contratos existentes. Aplicacion no importa lectores PDF, OCR ni FastAPI.

Las estrategias concretas estan en `infrastructure/extraction/`:

- `NativePdfExtractor` lee texto digital con pypdf y rechaza PDF invalidos o cifrados.
- `ScannedPdfOcrExtractor` renderiza con pypdfium2 y aplica OCR pagina por pagina;
  libera explicitamente imagen, bitmap, pagina y documento, incluso ante un error.
- `ImageOcrExtractor` procesa JPEG/PNG con Pillow y el OCR local configurado.

`TextExtractorFactory` registra y resuelve las estrategias por MIME. Su registro
puede ampliarse o reemplazarse con `register(mime_type, extractor)` o con un mapa
inyectado, sin agregar condicionales a la seleccion. `document_processing.py`
conecta la fabrica con los originales almacenados; la capa web no crea motores.
La API conserva los formatos admitidos y sus validaciones de carga.

La politica PDF intenta texto directo primero: un solo campo valido reconocido
por el parser basta para omitir OCR. Texto vacio, auxiliar o sin campos validos
activa el OCR; sus paginas se unen en orden. Se conservan los mensajes, errores,
campos propuestos, reglas de revision humana y procesamiento por lotes.

Las funciones anteriores `extract_pdf_text`, `extract_scanned_pdf_text`,
`extract_image_text` y `recognize_image_text` siguen disponibles como puntos de
compatibilidad. Los motores de imagen y PDF escaneado aceptan una funcion OCR
inyectada, y el pipeline PDF acepta extractores simulados; las pruebas no requieren
el ejecutable de Tesseract.

Desde la raiz del proyecto, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/unit/test_text_extraction_strategies.py tests/test_documents.py
```

La suite completa y las auditorias siguen usando los comandos anteriores.
Esta etapa no actualiza dependencias ni herramientas (#5), no agrega formatos,
servicios externos o nuevos endpoints y no completa el SRS (#6). Las verificaciones
con documentos sinteticos y OCR simulado no certifican precision sobre titulos reales.


## Calidad y robustez (issue #5)

La construccion de los PDF sinteticos incorpora cada pagina al `PdfWriter` antes
de combinar contenido, compatible con pypdf 6.20.1 y 7.0.0. Se mantiene el minimo
`pypdf>=6.20.1`; el workflow de calidad comprueba ambas versiones.

`TESSERACT_TIMEOUT` es un entero positivo (segundos); valores fraccionarios,
no numericos o no positivos se rechazan. `TESSERACT_CMD` conserva el valor por
defecto de Windows. En Linux/macOS se busca `tesseract` con `shutil.which` y se usa
el nombre del comando si no esta instalado; las variables de entorno y el `.env`
siguen teniendo precedencia. Esta deteccion no instala Tesseract ni sus idiomas.

`BatchDocumentResult` y `ProposedVehicleFields` son DTOs independientes: un resultado
de lote fallido admite ID nulo y `requiere_revision=false`, mientras que una propuesta
requiere ID y revision humana. Separarlos evita herencia mutable incompatible sin
ampliar los tipos publicos de una propuesta ni alterar sus respuestas JSON/OpenAPI.
Las validaciones de dominio para llamadas Python siguen rechazando tipos invalidos.

`pyrightconfig.json` activa comprobacion estricta sobre todo `src/`, con sintaxis
Python 3.10 y el entorno `.venv`. No desactiva diagnosticos. `typings/` contiene
stubs locales de la superficie utilizada de pytesseract y pypdfium2, bibliotecas
sin stubs publicados para estos imports. Se contrastaron con pytesseract 0.3.13
y pypdfium2 5.14.0; deben revisarse al cambiar sus APIs. No sustituyen codigo en
runtime ni certifican toda la API de esas bibliotecas.

Ruff 0.16.8 y Pyright 1.1.414 estan fijados en las dependencias de desarrollo.
Pre-commit usa la misma version de Ruff y ejecuta las auditorias con UTF-8.
`.vscode/settings.json` comparte el entorno, el modo estricto y el formato; los
demas ajustes personales del editor siguen ignorados. `.pytest_tmp/` se ignora
como directorio generado y Ruff no intenta recorrerlo; no se excluye codigo fuente.
El formato global tambien normalizo espacios en ejemplos Python del SRS, sin
completar ni cambiar su contenido funcional, reservado para #6.

El workflow `.github/workflows/quality.yml` ejecuta lint, formato, Pyright, las tres
auditorias y pytest en PRs y pushes a main. Incluye Linux con Python 3.10/pypdf 6.20.1,
Linux con Python 3.13/pypdf 7.0.0 y Windows con Python 3.13/pypdf 7.0.0. Usa permisos
de lectura y no necesita el binario OCR porque las pruebas usan simulaciones.
El resultado de CI se confirma en GitHub para cada commit; el archivo de workflow
por si solo no constituye una ejecucion aprobada.

Desde la raiz del repositorio en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pyright src/
.\.venv\Scripts\python.exe -X utf8 tests/test_architecture.py
.\.venv\Scripts\python.exe -X utf8 tests/test_clean_design.py --strict
.\.venv\Scripts\python.exe -X utf8 tests/test_god_components.py --strict
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

Para comprobar especificamente pypdf 7.0.0 en un entorno de desarrollo, instalar
`python -m pip install "pypdf==7.0.0"` antes de ejecutar la suite. La advertencia
de compatibilidad Starlette/HTTPX sigue visible; no se modifica ni se oculta.
El OCR con documentos reales, autenticacion y preparacion para produccion no
quedan certificados por estas herramientas.
