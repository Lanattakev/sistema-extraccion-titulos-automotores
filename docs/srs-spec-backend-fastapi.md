# SRS-SPECS: Sistema de extracción de títulos automotores — Single Source of Truth (SSOT) & Especificación del Sistema

> **Documento:** `srs-spec-backend-fastapi.md`
> **Versión:** `2.0.0`
> **Estado:** `En revisión mediante el PR del issue #6`
> **Fecha:** `2026-11-12`
> **Autor(es):** `Kevin Lanatta; desarrollo asistido bajo revisión humana`
> **Repositorio / Módulo:** `Lanattakev/sistema-extraccion-titulos-automotores`

> **Acompañamiento pedagógico:** Consultar la [Guía de Andamiaje Pedagógico y Metacognición](guia-andamiaje-proyectos.md) para revisar problemas de negocio, casos de borde y restricciones.

---

## 1. Contexto Estratégico & Propuesta de Valor

### 1.1. Foco Estratégico & Alcance
* **Mercado Objetivo:** Procesos de gestión documental automotor que requieren transcribir, revisar y registrar datos de títulos de vehículos. El MVP se orienta a evaluar esa necesidad en un entorno local; el segmento comercial y la demanda aún no están validados.
* **Buyer Persona (Decisor / Cliente Ideal):** Como hipótesis por validar, responsable de un proceso de gestión documental automotor que evalúa herramientas para asistir la carga y revisión de datos. Se distingue del operador que usa la API; no hay compradores ni contratos documentados.
* **User Persona (Operador / Usuario Final):** Operador que carga un título, revisa/corrige los seis campos propuestos y confirma su guardado mediante la SPA React 19, la API o Swagger.
* **Alcance Geográfico & Modalidad:** MVP local con archivos en disco y SQLite. La extracción reconoce formatos de patentes argentinas; no se declara cobertura internacional ni despliegue cloud.

* **Fuera de Alcance (*Out of Scope*):** Aprobación automática, autenticación, roles e integración con registros oficiales. La SPA de revisión y confirmación ya está implementada. El OCR local de JPG/JPEG/PNG y el fallback OCR para PDF escaneado ya están implementados.

### 1.2. Pilares de Valor de la Solución
| Pilar | Enfoque | Implementación en este Sistema |
| :--- | :--- | :--- |
| **1. Activos & Entorno Operativo** | Infraestructura física, dispositivos, hardware o fuentes de datos base. | Carga de PDF, JPG/JPEG y PNG de hasta 10 MiB por archivo, con UUID interno y metadatos JSON en disco local. Las imágenes JPG/JPEG/PNG se almacenan y pueden procesarse con OCR local mediante Tesseract, pytesseract y Pillow. |
| **2. Software & Lógica de Negocio** | Captura, procesamiento en tiempo real, persistencia y APIs. | FastAPI y Swagger; extracción de PDF con pypdf primero. Si el parser no reconoce ningún campo válido en el texto directo, pypdfium2 renderiza las páginas y se aplica Tesseract. Un solo campo válido basta para usar el texto directo sin OCR. El OCR local de JPG/JPEG/PNG utiliza Tesseract, pytesseract y Pillow. Todos los flujos reutilizan el parser existente para proponer patente, marca, modelo, motor, chasis y año. Campos ausentes, inválidos o contradictorios quedan en null; las propuestas de extract-fields mantienen requiere_revision = true. Confirmación humana mediante POST /api/v1/documents/ID_DOCUMENTO/confirm y consulta de datos completos en SQLite, separadas de la extracción. El ingreso confirmado se persiste con requiere_revision = false. La propuesta no guarda automáticamente VehicleRecord. Si el OCR no obtiene texto útil, devuelve texto vacío y campos null mediante una respuesta controlada. |
| **3. Impacto Económico & ROI** | Optimización de costos, generación de ingresos o eficiencia operativa. | Se busca reducir transcripción manual y facilitar la revisión humana. No hay mediciones documentadas de ahorro, precisión, tiempos ni retorno económico. |

### 1.3. Coordinación Operativa, Roles & Seguridad
* **Liderazgo Técnico / Responsable:** El equipo humano toma las decisiones del proyecto, aprueba los cambios y valida los resultados. Es responsable del mantenimiento y de la revisión de los aportes de las herramientas de desarrollo asistido.
* **Ventanas Operativas & Disponibilidad:** Ejecución local para desarrollo y validación; sin horarios de soporte, ventanas de mantenimiento ni SLA definidos.
* **Habilitaciones, Normativas & Seguridad:** Validación de nombre, extensión, tamaño y contenido no vacío, nombres internos UUID y consultas SQL parametrizadas. La extensión no certifica el contenido del archivo. Sin autenticación, roles ni certificaciones acreditadas. Usar documentos sintéticos y mantener archivos, metadatos, bases de datos y secretos fuera del repositorio. No se declara cumplimiento normativo ni aptitud para exposición pública.

---

## 2. Modelo de Negocio Canvas (BMC de 9 Bloques) & Gobernanza

### 2.1. Matriz del Business Model Canvas
| Bloque Canvas | Definición Estratégica | Componentes Clave en el Software |
| :--- | :--- | :--- |
| **1. Socios Clave (KP)** | Sin alianzas ni proveedores comerciales definidos. | Dependencias de software declaradas; sin integración con registros oficiales ni servicios externos de OCR. |
| **2. Actividades Clave (KA)** | Carga, extracción conservadora, revisión humana y registro. | extract-fields propone los seis campos con requiere_revision = true sin persistir; POST /api/v1/documents/ID_DOCUMENTO/confirm recibe los campos revisados/corregidos y guarda VehicleIntake en SQLite con requiere_revision = false. |
| **3. Recursos Clave (KR)** | Código, reglas de extracción, pruebas y almacenamiento local. | Python, FastAPI, pypdf, pypdfium2, Tesseract, pytesseract, Pillow, modelos de dominio, archivos con UUID y SQLite. |
| **4. Propuesta de Valor (VP)** | Facilitar el registro sin completar automáticamente valores dudosos. | Seis campos propuestos; null cuando no hay un candidato válido único y requiere_revision = true. |
| **5. Relación con Clientes (CR)** | Evaluación técnica del MVP; soporte comercial por definir. | Swagger para probar la API; sin notificaciones, webhooks ni sistema de soporte. |
| **6. Canales de Distribución (CH)** | API HTTP local. | /api/v1/documents, /api/v1/vehicles y Swagger en /api/v1/docs con configuración predeterminada. SPA React 19 con TypeScript y Vite para carga, revisión, confirmación, vehículos, historial y métricas. |
| **7. Segmentos de Clientes (CS)** | Operadores que transcriben títulos automotores; segmentación comercial pendiente. | Validaciones comunes, sin usuarios ni permisos por roles. |
| **8. Estructura de Costos (CS)** | Ejecución local, disco y mantenimiento; costos sin cuantificar. | SQLite y archivos locales, sin infraestructura cloud ni medición de consumo facturable integrada. |
| **9. Fuentes de Ingresos (RS)** | Modelo de ingresos y precios no definidos. | Sin pagos, suscripciones ni facturación. |

### 2.2. Organigrama Operativo / Gobernanza de Agentes IA (Opcional)
* **Coordinación técnica:** La gobernanza corresponde al equipo humano. Codex se usa como herramienta de desarrollo asistido bajo supervisión humana; sus propuestas están sujetas a revisión, aprobación de cambios y validación de resultados por el equipo. No hay organigrama formal ni agentes IA operativos implementados en el MVP. Las responsabilidades del código se describen a continuación.
* **Dominio y aplicación:** src/domain define registros y validaciones; src/application contiene DTOs, parser de campos, política PDF y casos de uso de carga, extracción, revisión, confirmación y lote; coordina dependencias inyectadas sin importar FastAPI ni SQLite.
* **API e infraestructura:** src/infrastructure contiene routers FastAPI, extracción de PDF con pypdf y fallback con pypdfium2, OCR compartido de imágenes y páginas PDF separado de FastAPI, almacenamiento local, repositorio SQLite y configuración.
* **Calidad:** pytest ejecuta las pruebas unitarias, de integración y de endpoints; Ruff controla las reglas de lint y formato, y los tests arquitectónicos verifican las restricciones de arquitectura. Estas herramientas controlan la calidad y complementan la revisión humana. Sus resultados deben verificarse al ejecutarlas; no equivalen a certificación ni sustituyen la aprobación del equipo.
* **Trazabilidad y colaboración:** Git/GitHub y los commits se usan para la trazabilidad, la colaboración y el registro de la evolución del proyecto.
* **OCR implementado y validación:** OCR local de JPG/JPEG/PNG con Tesseract, pytesseract y Pillow, y fallback OCR para PDF escaneado con pypdfium2 y Tesseract, integrados en extract-text y extract-fields. En PDF se intenta pypdf primero; el parser existente determina si el texto directo aporta al menos un campo válido. Si no aporta ninguno, se renderizan las páginas, se aplica el OCR existente y se une el texto en orden. Reutiliza el parser existente de los seis campos, mantiene requiere_revision = true y no guarda automáticamente VehicleRecord. Las pruebas con OCR simulado cubren imágenes con y sin texto, fallback de PDF, texto auxiliar irrelevante sobre páginas escaneadas, orden de páginas, extracción de campos y errores; también verifican que PDF con texto útil no use OCR; no acreditan precisión sobre documentos reales. La ruta del ejecutable, los idiomas y el tiempo límite se centralizan en Settings.
* **Confirmación humana implementada:** POST /api/v1/documents/ID_DOCUMENTO/confirm recibe patente, marca, modelo, numero_motor, numero_chasis y anio revisados/corregidos por el usuario. Valida mediante VehicleRecord, obtiene el nombre original del documento como archivo_origen y persiste VehicleIntake en SQLite con requiere_revision = false; devuelve el registro creado con HTTP 201. Las correcciones humanas prevalecen sobre OCR, sin volver a ejecutar la extracción. Documento inexistente devuelve HTTP 404; datos inválidos, HTTP 422. extract-fields sigue proponiendo los seis campos con requiere_revision = true sin guardar automáticamente. El alta independiente por /vehicles conserva requiere_revision = true y recibe archivo_origen del usuario.
* **Trabajo pendiente:** Controles de acceso, hash documental, deduplicación, retención y mediciones de rendimiento. La SPA ya permite revisión y confirmación individual o múltiple.

### 2.3. Escalera de Valor / Modelo de Conversión
* **Nivel de Entrada (*Lead Magnet* / Tier Gratuito):** Evaluación local por Swagger con documentos sintéticos; sin demo pública ni plan gratuito comercial definido.
* **Servicio Core (*Core Offering*):** Implementados: carga local, extracción de texto de PDF con pypdf primero y fallback con pypdfium2 y Tesseract cuando el parser no encuentra campos válidos, OCR local de JPG/JPEG/PNG con Tesseract, pytesseract y Pillow, y propuesta conservadora de los seis campos mediante el parser existente y alta/consulta de registros completos en SQLite. La propuesta de extract-fields mantiene requiere_revision = true, no guarda automáticamente VehicleRecord y requiere revisión humana. La confirmación por POST /api/v1/documents/ID_DOCUMENTO/confirm persiste los seis campos revisados/corregidos en un VehicleIntake con requiere_revision = false y usa el nombre original del documento como archivo_origen.
* **Nivel Avanzado (*Enterprise* / Retención):** Sin oferta empresarial ni SLA definidos. El OCR local de JPG/JPEG/PNG y el fallback para PDF escaneado están implementados y probados con OCR simulado. Ya existen lote, revisión/confirmación en la SPA, historial y métricas. Como evolución futura se contemplan paralelismo interno del lote, controles de acceso y validación de rendimiento y precisión.

---

## 3. Especificación de Requisitos de Software (SRS)

Este documento describe el MVP implementado y separa explícitamente los objetivos pendientes. Las decisiones comerciales no validadas de las secciones 1 y 2 son hipótesis. La API y las pruebas son la evidencia del comportamiento; este documento no acredita precisión OCR, rendimiento ni preparación para producción. En las rutas, ID_DOCUMENTO e ID_VEHICULO representan el UUID correspondiente, no texto literal.

### 3.1. Requisitos funcionales y evidencia

#### RF-01 — Carga y hash documental

**Implementado:** POST `/api/v1/documents` acepta exactamente un archivo en `file`, PDF/JPG/JPEG/PNG de hasta 10 MiB inclusive. Rechaza nombre vacío, rutas en el nombre, extensión no admitida, contenido vacío y exceso de tamaño. Almacena los bytes con UUID y extensión, metadatos JSON y registro SQLite pendiente. La extensión determina MIME; no certifica el contenido. La copia se hace en bloques de 64 KiB, con creación exclusiva y limpieza de archivos parciales ante fallos de almacenamiento. Disco y SQLite no forman una única transacción distribuida.

**Hash pendiente:** el código no calcula ni persiste SHA-256, ni deduplica contenido. UUID identifica una carga; no demuestra integridad ni igualdad de archivos. El objetivo futuro es calcular SHA-256 de los bytes originales y persistirlo en los metadatos antes de definir una política de duplicados. Su aceptación requerirá comprobar igualdad de hash para bytes idénticos, diferencia al modificar contenido y conservación del hash tras reinicio. Este PR documental no implementa ese objetivo.

**Verificación actual:** `tests/test_documents.py`, `tests/unit/test_document_use_cases.py` y `tests/unit/test_document_http_contracts.py` cubren carga, límites, nombres inválidos y contratos HTTP. Campos multipart incorrectos devuelven 422; tamaño excedido, 413; extensión no admitida en carga, archivo vacío o nombre inválido, 400. MIME sin estrategia durante extracción devuelve 415.

#### RF-02 — Extracción híbrida y propuesta conservadora

POST `/api/v1/documents/ID_DOCUMENTO/extract-text` y `/extract-fields` trabajan sobre los originales guardados. PDF usa pypdf primero: un solo campo válido reconocido por el parser basta para omitir OCR. Sin campos válidos, incluso con texto auxiliar, pypdfium2 renderiza cada página y Tesseract realiza OCR en orden. JPG/JPEG/PNG usan Pillow y Tesseract. Las estrategias concretas se resuelven por MIME mediante `TextExtractorFactory`; el protocolo y la política PDF pertenecen a aplicación.

Se proponen patente, marca, modelo, número de motor, número de chasis y año. Ausencia, invalidez o candidatos contradictorios producen null. Las propuestas llevan `requiere_revision=true`; extraer no crea un ingreso vehicular. Una propuesta exitosa se guarda como documento pendiente sin pisar revisiones humanas. OCR sin texto útil devuelve texto vacío/campos nulos; PDF inválido/cifrado, imagen ilegible o fallo OCR producen un error controlado. Un documento inexistente devuelve 404.

**Verificación:** `tests/unit/test_text_extraction_strategies.py`, `tests/unit/test_title_field_extraction.py` y `tests/test_documents.py`. OCR está simulado: no hay corpus real ni porcentaje de exactitud acreditado.

#### RF-03 — Revisión y confirmación humana

GET `/api/v1/documents` recupera estados persistidos. PATCH `/api/v1/documents/ID_DOCUMENTO/review` valida los seis campos completos y guarda estado revisado. Repetir una revisión idéntica no duplica el evento; editar campos requiere volver a guardar. POST `/api/v1/documents/ID_DOCUMENTO/confirm` crea un `VehicleIntake` con HTTP 201, UUID interno, número de registro positivo, fecha de ingreso, nombre original como `archivo_origen` y `requiere_revision=false`. El nombre de origen lo obtiene el servidor; no se admite como corrección del usuario. La confirmación no ejecuta OCR de nuevo.

La transacción SQLite engloba ingreso, cambio a registrado y evento de historial. Documento registrado devuelve 409 ante nueva revisión/confirmación; si los campos enviados difieren de una revisión guardada, confirmar devuelve 409. Inexistente devuelve 404 y datos inválidos, 422. Por compatibilidad, la API acepta confirmar un pendiente enviando explícitamente sus seis campos completos; la SPA exige guardar revisión y su confirmación múltiple omite pendientes, continúa tras fallos y no reenvía éxitos.

POST `/api/v1/vehicles` conserva el alta independiente: recibe los seis campos y `archivo_origen`, sin verificar una carga, y crea un ingreso con `requiere_revision=true`. GET `/api/v1/vehicles` y `/api/v1/vehicles/ID_VEHICULO` consultan ingresos.

**Verificación:** `tests/e2e/test_document_workflow.py`, `tests/e2e/test_vehicles.py`, contratos de repositorios e integración SQLite; `frontend/tests/document-workflow.test.mjs` y `document-controller.test.mjs` cubren revisión, conflictos de respuestas antiguas y confirmación múltiple con simulaciones.

#### RF-04 — Historial de auditoría operativa

GET `/api/v1/history` devuelve eventos persistidos, del más reciente al más antiguo, con UUID de evento/documento, tipo, fecha UTC y nombre original. Los tipos son `documento_cargado`, `documento_revisado` y `documento_registrado`. La escritura participa en la misma transacción SQLite que la operación documental; el protocolo de historial expone solo lectura. Sin usuarios autenticados, el evento no identifica operador. No existen firma, hash encadenado ni garantía contra manipulación administrativa de la base.

La SPA comparte una consulta de historial entre las vistas y deriva métricas de fechas reales: primera revisión, antigüedad de pendientes, estados y actividad diaria/semanal/mensual. Distingue carga, error y conjunto vacío; no inventa eventos ni datos faltantes. Exportación CSV utiliza los vehículos recibidos.

**Verificación:** `tests/e2e/test_history.py`, `tests/integration/test_sqlite_history_repository.py` y suites frontend de historial, métricas, tiempos y CSV.

#### RF-05 — Lote y concurrencia

POST `/api/v1/documents/batch` acepta entre 1 y 100 archivos en el campo repetido `files`, con límite individual de 10 MiB. Solicitud vacía o con campos distintos de `files` se rechaza; más de 100 archivos rechaza la solicitud completa. Cada resultado conserva el orden de entrada e incluye nombre, ID si se llegó a almacenar, seis campos, `requiere_revision`, `fallo` y `error`.

Un fallo por archivo no interrumpe los siguientes: los campos quedan nulos, `fallo=true`, `requiere_revision=false` y error explícito. Si falla la extracción después de guardar, el resultado conserva el ID del original, pero no agrega el pendiente SQLite. El lote devuelve HTTP 200 con resultados mixtos y no confirma vehículos.

**Concurrencia real:** `ProcessBatchDocumentsUseCase.execute` espera cada `asyncio.to_thread` antes de procesar el siguiente archivo: hay un archivo en proceso por lote, fuera del event loop. Esto permite atender otras solicitudes, pero no paraleliza archivos del mismo lote. Paralelismo interno y límites globales de trabajo quedan pendientes. Cambiarlos requerirá preservar orden, aislamiento por archivo, memoria acotada y atomicidad de confirmación.

**Verificación:** pruebas de lote en `tests/test_documents.py` y `tests/unit/test_document_use_cases.py`; cliente HTTP y flujo en `frontend/tests/`.

### 3.2. Requisitos no funcionales

| ID | Contrato actual y condición verificable | Limitación u objetivo pendiente |
| --- | --- | --- |
| NFR-01 Latencia | OCR usa `TESSERACT_TIMEOUT`, entero positivo, 30 s por invocación de Tesseract por defecto. No es un timeout total de solicitud; varias páginas pueden sumar varias invocaciones. | No hay medición p95 ni SLO aprobado para lectura/extracción. Antes de fijarlos, medir p50/p95, errores y memoria sobre documentos sintéticos, registrando hardware, versiones, volumen, tamaño y concurrencia; separar PDF nativo, imagen y PDF escaneado. No prometer milisegundos sin esa evidencia. |
| NFR-02 Concurrencia | Un archivo activo por lote; trabajo bloqueante fuera del event loop. Confirmaciones usan transacciones `BEGIN IMMEDIATE` para serializar escrituras. | No hay tasa de RPS, número de usuarios simultáneos ni capacidad global acreditada. Ensayar solicitudes paralelas y confirmaciones simultáneas sobre el mismo documento; exigir un solo ingreso y 409 para duplicados. Registrar throughput y errores SQLite antes de aprobar un objetivo de capacidad. |
| NFR-03 Límites de carga | 10 MiB por archivo y hasta 100 archivos por lote. Copia de bytes en bloques y renderizado OCR de una página por vez. | No hay límite propio de páginas, píxeles, tiempo total del lote o tasa global de solicitudes. Los límites de bytes no equivalen a un presupuesto de memoria o CPU del OCR. |
| NFR-04 Integridad y recuperación | SQLite guarda documento, ingreso e historial transaccionalmente en revisión/confirmación. Los estados persisten tras reinicio. La SPA informa errores, evita doble envío y consulta el estado tras una confirmación incierta. | Sin SLA de disponibilidad, backups/restauración automatizados, retención ni transacción única entre disco y SQLite. |
| NFR-05 Seguridad y privacidad | Nombres internos UUID, validación de rutas/nombres y consultas parametrizadas; secretos fuera de Git. Evaluación local con documentos sintéticos. | Sin autenticación/autorización, rate limiting, antivirus, TLS propio, cifrado en reposo ni certificación normativa. CORS permisivo por defecto. No declarar preparación para producción. |
| NFR-06 Calidad y compatibilidad | Ruff y Pyright estricto, 11 baterías AST, auditorías estrictas y suites completas aprobadas antes de integrar. CI prueba Linux/Python 3.10/pypdf 6.20.1, Linux/Python 3.13/pypdf 7.0.0 y Windows/Python 3.13/pypdf 7.0.0. | Los mocks de OCR y las pruebas de renderizado no acreditan precisión real ni interacción integral en navegador. |

## 4. Stack, arquitectura y configuración

### 4.1. Stack implementado

- Python 3.10+, FastAPI/Uvicorn, Pydantic v2 y pydantic-settings.
- Carga multipart: `python-multipart>=0.0.18`; PDF: `pypdf>=6.20.1`, con verificación explícita de pypdf 6.20.1 y 7.0.0 en CI.
- OCR: pytesseract 0.3.13, Pillow, pypdfium2 y ejecutable externo Tesseract con idiomas `spa+eng` por defecto.
- Persistencia: `sqlite3` síncrono de la biblioteca estándar. No hay ORM, broker, cola distribuida ni servicio externo de OCR.
- SPA React 19, TypeScript 6, Vite 8 y CSS. Pruebas con runner nativo de Node, TypeScript y simulaciones; ESLint y TypeScript/Vite para calidad y build.
- Desarrollo backend: pytest/pytest-asyncio/HTTPX, Ruff 0.16.8, Pyright 1.1.414 y hooks pre-commit. El runner pre-commit se instala aparte si no está disponible.

### 4.2. Estructura existente y regla de dependencias

```text
src/
  domain/                 Registros, validaciones, eventos y protocolos Repository
  application/
    dtos/                 Entradas y resultados independientes de HTTP
    use_cases/            Carga, extracción, revisión, confirmación, alta y lote
    text_extraction.py    Protocolo TextExtractor y política de fallback PDF
    title_field_extraction.py  Parser puro de los seis campos
  adapters/               Paquete vacío, reservado; no hay controladores propios
  infrastructure/
    fastapi/routers/      Transporte HTTP delgado
    fastapi/              Composición de dependencias y traducción de errores
    extraction/           Estrategias PDF/OCR y fábrica por MIME
    persistence/          Archivos, metadatos y repositorios SQLite
    settings/             Configuración y logging
  main.py                 Composition root ASGI y ciclo de vida
frontend/
  src/App.tsx             Vistas y estado compartido
  src/views/              Inicio, carga, vehículos, métricas, historial, ayuda y ajustes
  src/components/         Controles, revisión, tablas y gráficos
  src/hooks/              Consultas y flujo de revisión/confirmación
  src/services/api.ts     Cliente HTTP y validación de respuestas
  src/types/              Contratos TypeScript
  src/utils/              Métricas, prioridades, búsqueda y CSV
  tests/                  Suites node:test
tests/                    Unitarias, integración, endpoints y auditorías AST
docs/                     SRS y guía pedagógica
```

Dominio no importa aplicación ni infraestructura; aplicación coordina protocolos y funciones inyectadas sin importar FastAPI, SQLite ni motores externos. Infraestructura implementa los puertos y selecciona estrategias. Los routers delegan casos de uso; `src/main.py` compone repositorios. La SPA consume HTTP y no tiene acceso directo a SQLite o archivos del servidor. No se crean carpetas de plantilla ni abstracciones sin uso.

### 4.3. Configuración y ejecución local

`src/infrastructure/settings/config.py` centraliza Settings, variables de entorno y `.env` UTF-8, con caché de `get_settings`. `.env.example` es orientativo; `.env` y variantes se ignoran salvo el ejemplo. SECRET_KEY y ACCESS_TOKEN_EXPIRE_MINUTES existen como configuración, pero no implementan autenticación. `logger.py` emite logs de texto a stdout con nivel configurable; no hay logging JSON implementado.

| Parámetro | Predeterminado y efecto |
| --- | --- |
| ENVIRONMENT / DEBUG / LOG_LEVEL | development / false / INFO |
| PROJECT_NAME / VERSION | backend-api / 1.0.0, metadatos OpenAPI |
| API_V1_PREFIX | /api/v1; prefijo API y documentación |
| ALLOWED_HOSTS | Lista con asterisco; se usa para orígenes CORS, no como filtro de Host |
| DATABASE_URL | sqlite+aiosqlite:///./app.db; también acepta sqlite:///; usa sqlite3 síncrono |
| TESSERACT_CMD | Ruta estándar de Windows; en Linux/macOS busca tesseract con shutil.which y conserva el nombre si no está instalado |
| TESSERACT_LANG | spa+eng; instalar ambos idiomas por separado |
| TESSERACT_TIMEOUT | 30 segundos, entero mayor que cero |

Variables de entorno y `.env` prevalecen sobre valores predeterminados. Los originales y metadatos se guardan en `uploads/` desde la raíz del repositorio. Las tablas se inicializan al iniciar la API; `app.db` se resuelve desde el directorio de ejecución. No publicar estos archivos ni usar títulos reales en ejemplos.

Desde la raíz, crear/activar `.venv` e instalar `requirements-dev.txt`; para ejecución sin herramientas usar `requirements.txt`. Iniciar con `python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000`. En otra terminal, `cd frontend`, `npm ci` y `npm run dev -- --host 127.0.0.1`. Frontend requiere Node 22.12 o superior de la rama 22, o una versión posterior compatible con Vite.

La base HTTP de la SPA está fijada en `frontend/src/services/api.ts` a `http://127.0.0.1:8000/api/v1`; no hay proxy ni variable Vite para cambiarla. Un cambio de puerto/prefijo exige alinear el cliente y CORS. Navegación de SPA mediante estado React local, sin router de URLs. Configuración contiene controles de demostración; no ofrece administración real de usuarios/notificaciones.

### 4.4. Convenciones efectivamente verificadas

Archivos `__init__.py` de src y tests vacíos, imports Python absolutos, anotaciones de parámetros/retornos de dominio y aplicación, cabecera con ruta relativa en archivos Python, sin print en producción ni acceso al entorno fuera de Settings. Las once baterías AST definen el alcance comprobado; no sustituyen auditoría integral de seguridad. Pyright comprueba todo `src/` en modo estricto según `pyrightconfig.json`; tests quedan fuera del alcance de tipado, pero se ejecutan. `.vscode/settings.json` versionado alinea el editor y `.venv`. Stubs locales en `typings/` cubren la superficie usada de pytesseract/pypdfium2 y requieren revisión al cambiar esas APIs.

## 5. Calidad, trazabilidad y aceptación

### 5.1. Matriz reproducible

Desde la raíz con `.venv` activado:

```bash
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m pyright src/
python -X utf8 tests/test_architecture.py
python -X utf8 tests/test_clean_design.py --strict
python -X utf8 tests/test_god_components.py --strict
python -X utf8 -m pytest -q
```

Para hooks: instalar `python -m pip install pre-commit` y ejecutar `python -m pre_commit run --all-files` con el entorno activado, de modo que los hooks locales usen su Python. Los hooks pueden modificar archivos; revisar el diff y repetir verificaciones antes de crear/publicar el commit definitivo. En un entorno que no permita escribir la caché pytest puede ejecutarse con `-p no:cacheprovider`, sin excluir pruebas.

Desde `frontend/`, ejecutar `npm ci`, `npm test`, `npm run lint` y `npm run build`. Desde Bash en la raíz, `bash run.sh frontend-test` invoca la suite frontend sin crear un entorno Python. `npm run preview -- --host 127.0.0.1` permite evaluar el build. Las pruebas Node existentes son 78 al elaborar esta revisión; no agregar pruebas artificiales para alcanzar el conteo histórico de 41 mencionado en #6.

CI de backend está en `.github/workflows/quality.yml` y se ejecuta en PR y push a main con la matriz indicada en NFR-06. Actualmente no ejecuta frontend: sus pruebas/lint/build se verifican localmente y se informan en el PR. La advertencia conocida de Starlette/HTTPX no se oculta ni se considera prueba de fallo funcional.

### 5.2. Procedimiento de cambios

Analizar el issue y el código vigente, preservar cambios locales y trabajar en rama propia. Separar commits por unidad lógica con Conventional Commits; mantener pruebas y auditorías aprobadas. Publicar el PR con problema, alcance, resultados y limitaciones; comprobar directamente en GitHub SHA, CI y conflictos. La fusión del PR de #6 requiere autorización humana explícita para el resultado revisado. Después de integrar, verificar main, ejecutar las pruebas posteriores, informar en el issue y cerrar como completed solo con evidencia satisfactoria. Mantener abierto el EPIC #1 conforme a la instrucción del responsable.

### 5.3. Aceptación documental de #6

- SRS sin marcadores de plantilla, con RF-01 a RF-05, NFR, arquitectura y configuración contrastados con código.
- README raíz y frontend describen la SPA existente, instalación y contratos reales.
- Identidad del paquete `sistema-extraccion-titulos-automotores`; dependencias de runtime sincronizadas entre pyproject.toml y requirements.txt, incluidos pypdf y python-multipart.
- Conservar el script frontend test ya existente; agregar su invocación a run.sh y aprobar la suite actual completa.
- No presentar hash, paralelismo interno, SLO, autenticación ni precisión OCR real como capacidades implementadas. Su definición o implementación requiere una etapa específica; completar este documento no las crea.
