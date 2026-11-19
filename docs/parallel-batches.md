# Procesamiento paralelo de lotes — issue #14

## Diseño y compatibilidad

`ProcessBatchDocumentsUseCase` consume las entradas con un número acotado de
consumidores y devuelve resultados por índice original, aunque terminen en otro
orden. Cada archivo conserva su resultado y sus errores: un fallo no interrumpe
los restantes ni inventa campos. Se mantienen el endpoint, DTO y OpenAPI.

FastAPI crea un `BatchDocumentProcessor` por lifespan, compartido entre solicitudes.
Guarda los originales por streaming en el padre; envía a `ProcessPoolExecutor`
únicamente metadatos, ruta y configuración OCR (comando, idiomas y timeout). El
hijo extrae texto con las mismas estrategias PDF digital/PDF escaneado/imagen.
Parser, persistencia pendiente e historial permanecen en el proceso web, usando
el pool SQLite WAL existente. Nunca se envían uploads, conexiones o repositorios
a los procesos. Un reintento de extracción no repite la carga ni sus escrituras.

Se usa explícitamente `spawn` tanto en Windows como Linux para evitar heredar
conexiones SQLite o estado de hilos. Las funciones del worker son importables;
no se crea un pool al importar módulos. Véanse las
[reglas de Python para ProcessPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor)
y los [contextos de multiprocessing](https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods).

El pool se crea al primer trabajo paralelo y se reutiliza hasta el apagado.
Con un trabajador se ejecuta secuencialmente fuera del event loop. Si falla la
creación/envío al pool o un proceso rompe el pool, se registra una advertencia y
la extracción pendiente se reintenta secuencialmente; el pool queda degradado
hasta reiniciar la aplicación. Los errores normales de documento no degradan el
pool: conservan el tratamiento por archivo. El fallback usa una exclusión global
para evitar que varias solicitudes disparen OCR secuencial simultáneamente.

Cancelar una solicitud deja terminar los archivos ya activos antes de cerrar sus
streams multipart y no comienza otros. El préstamo al procesador también drena
el trabajo antes de liberar su cupo ante cancelación. El apagado espera a los
procesos y libera el pool; no implementa una cola durable ni trabajos en background.

## CPU, memoria y límites

El límite de CPU es `max(1, min(4, (cpu_count or 1) - 1))`, reducido por
`process_cpu_count` cuando está disponible y por `sched_getaffinity` en sistemas
compatibles. Si no hay afinidad consultable se conserva la cuenta disponible.
Es una reserva por concurrencia lógica; no fija afinidad física de procesos.

| Variable | Defecto | Restricción |
| --- | --- | --- |
| `BATCH_MAX_WORKERS` | Límite CPU calculado | Entero 1–4; no supera el límite CPU efectivo |
| `BATCH_MEMORY_BUDGET_MB` | 1024 | Entero >=256; reserva estimada de 256 MiB por trabajador |

El número efectivo es el mínimo de ambos límites y `budget // 256`. Un semáforo
compartido impide enviar más de ese número de extracciones al executor, incluso
con varias solicitudes. No se acumula todo un lote en la cola de procesos ni se
serializan imágenes/bitmaps por IPC. Cada PDF escaneado renderiza una página por
vez y cierra imagen, bitmap y página antes de comenzar la siguiente, también si
falla OCR. Los hijos limitan OpenMP de Tesseract a un hilo para evitar multiplicar
hilos internos por trabajador; no alteran el entorno del proceso web.

**La reserva no es un límite RSS impuesto por el sistema operativo ni garantiza
ausencia de OOM para documentos arbitrarios.** Tamaño/resolución de páginas,
bibliotecas nativas, Tesseract y concurrencia de endpoints individuales pueden
consumir memoria adicional. Los límites son por proceso web; múltiples workers de
Uvicorn multiplican pools y presupuesto. Este cambio no agrega cgroups, medición
automática de RAM libre, límites globales entre procesos web, colas persistentes
ni capacidad productiva acreditada. Los endpoints individuales conservan su flujo.

## Verificación y benchmark reproducible

Las pruebas existentes de `tests/test_documents.py` mantienen sus mocks OCR en el
proceso padre con configuración de un trabajador; no omiten casos. Las pruebas
de integración adicionales ejecutan spawn real en todas las plataformas de CI,
comprueban dos PID y solapamiento, admisión global, orden HTTP, errores mixtos,
persistencia, integridad SQLite, fallback sin duplicar originales/eventos y cierre
de hijos. Pruebas unitarias cubren afinidad, presupuesto, cancelación y cierre
explícito de imágenes/bitmaps/páginas ante éxito y fallo.

Con el runtime SQLite corregido de la [guía SQLite](sqlite-concurrency.md), Tesseract
instalado e idiomas configurados, desde la raíz en PowerShell:

```powershell
$python = '.\.venv\sqlite-safe-python-31317\python.exe' # O tu intérprete validado.
& $python -X utf8 -m pytest -q tests/unit/test_parallel_batch.py tests/unit/test_batch_pdf_resources.py tests/integration/test_parallel_batch_processing.py tests/test_documents.py
& $python -X utf8 -m scripts.benchmark_batch_processing --documents 6 --pages 2 --repeat 2 --workers 3
```

El benchmark crea una carpeta nueva `.venv/batch-benchmark-*`, conserva todos sus
artefactos y `results.json`, y compara lotes secuenciales y paralelos contra la API
real, con PDF escaneados sintéticos y Tesseract real. Comprueba orden, campos,
ausencia de fallback, revisión humana e integridad de cada base aislada. Informa
tiempo frío, muestras calientes, mediana, aceleración y, en Windows, pico de
working set por proceso. Los picos individuales no representan una suma simultánea.

Una medición de desarrollo en Windows, cuatro CPU lógicas y tres trabajadores,
dio mediana caliente de **10,09 s secuencial frente a 6,66 s paralelo** (1,51×,
aproximadamente 34% menos tiempo) para seis PDF de dos páginas. Los hijos tuvieron
picos individuales de aproximadamente 108 MiB. El primer lote paralelo tardó
12,02 s frente a 10,68 s secuencial: spawn e imports tienen coste de arranque.
Estos valores son una observación del entorno, no una promesa de aceleración para
todo documento, rendimiento bajo carga sostenida o precisión con títulos reales.
