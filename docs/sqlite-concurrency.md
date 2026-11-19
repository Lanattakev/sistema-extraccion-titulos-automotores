# SQLite concurrente — issue #13

## Conexiones y transacciones

FastAPI crea un `SQLiteConnectionPool` por proceso durante `lifespan`.
`SQLITE_POOL_SIZE` es positivo, por defecto 4. Vehículos, documentos e historial
comparten el pool. Cada operación toma una conexión exclusivamente; puede
devolverla y prestarla a otro hilo, pero nunca usarla simultáneamente.

Todas las conexiones verifican `journal_mode=WAL`, `synchronous=NORMAL`,
`busy_timeout=30000` y `foreign_keys=ON`; `sqlite3.connect` también usa timeout de
30 segundos. El préstamo espera hasta 30 segundos si se agotó el pool. Escrituras
y migraciones toman `BEGIN IMMEDIATE` antes de leer/modificar. La confirmación
conserva ingreso, correlativo, estado y evento en una transacción: un error revierte
los cuatro. Cada operación confirma/revierte antes de devolver la conexión.

El apagado cierra ociosas, despierta esperas con error y cierra préstamos activos
cuando retornan. También libera recursos si falla el arranque. Los constructores
`SQLite*Repository(path)` conservan compatibilidad: sin pool inyectado abren y
cierran una conexión configurada por operación, sin retener handles. FastAPI sí
reutiliza conexiones durante toda la aplicación, sin singleton global.

## Runtime obligatorio

SQLite documenta corrupción **WAL-reset** con escritores/checkpoints concurrentes:
[referencia oficial](https://sqlite.org/wal.html#walreset). Antes de abrir archivos
se exige SQLite >= 3.51.3 o los backports 3.50.7+ de la rama 3.50 / 3.44.6+ de la
rama 3.44. Un motor afectado falla explícitamente sin crear ni modificar la base.
Actualizar un paquete pip no actualiza SQLite de la biblioteca estándar.

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; from src.infrastructure.persistence.sqlite_connections import require_safe_sqlite; print(sqlite3.sqlite_version); require_safe_sqlite()"
```

CI mantiene tres combinaciones Linux/Windows y Python 3.10/3.13. Comprueba hashes
SHA3-256 oficiales e instala SQLite 3.54.1: biblioteca aislada con `LD_LIBRARY_PATH`
en Linux; DLL del Python efímero del runner en Windows. Comprueba el motor realmente
cargado. La aplicación no descarga binarios ni modifica Python al arrancar.

### Windows con Python antiguo: runtime portable separado

Con dependencias instaladas en `.venv` **CPython 3.13 x64**, estos comandos crean un
intérprete aislado que reutiliza esos paquetes. No reemplazan Python instalado ni
bases existentes. Verifican hashes publicados por
[Python](https://www.python.org/downloads/release/python-31317/) y
[SQLite](https://sqlite.org/download.html). Para otra arquitectura/versión, usar un
runtime compatible y comprobar su SQLite. El directorio destino debe ser nuevo.

```powershell
$runtime = Join-Path (Get-Location) '.venv/sqlite-runtime'
if (Test-Path -LiteralPath $runtime) { throw 'Runtime existente: verificar antes de reutilizar.' }
if (-not (Test-Path '.venv/Lib/site-packages')) { throw 'Crear primero .venv CPython 3.13 x64 e instalar requirements-dev.txt.' }
$pythonZip = Join-Path $env:TEMP ('python-portable-' + [guid]::NewGuid() + '.zip')
Invoke-WebRequest 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip' -OutFile $pythonZip
if ((Get-FileHash -Algorithm SHA256 $pythonZip).Hash.ToLowerInvariant() -ne '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38') { throw 'Hash Python incorrecto' }
Expand-Archive -LiteralPath $pythonZip -DestinationPath $runtime
$pth = "python313.zip`n.`n..\..`n..\Lib\site-packages`nimport site`n"
[IO.File]::WriteAllText((Join-Path $runtime 'python313._pth'), $pth, (New-Object Text.UTF8Encoding($false)))
$sqliteZip = Join-Path $env:TEMP ('sqlite-fixed-' + [guid]::NewGuid() + '.zip')
Invoke-WebRequest 'https://sqlite.org/2026/sqlite-dll-win-x64-3540100.zip' -OutFile $sqliteZip
.\.venv\Scripts\python.exe -c "import hashlib,sys; from pathlib import Path; assert hashlib.sha3_256(Path(sys.argv[1]).read_bytes()).hexdigest() == 'c2d09c8babb9399277055c057c97a53f1ffd7c5f11d0c1f2118ffdfa39f2daa4'" $sqliteZip
if ($LASTEXITCODE -ne 0) { throw 'Hash SQLite incorrecto' }
$dllFolder = Join-Path $env:TEMP ('sqlite-dll-' + [guid]::NewGuid())
Expand-Archive -LiteralPath $sqliteZip -DestinationPath $dllFolder
Copy-Item -LiteralPath (Join-Path $runtime 'sqlite3.dll') -Destination (Join-Path $runtime 'sqlite3.original.dll')
Copy-Item -LiteralPath (Join-Path $dllFolder 'sqlite3.dll') -Destination (Join-Path $runtime 'sqlite3.dll')
$python = Join-Path $runtime 'python.exe'
& $python -c "import sqlite3; from src.infrastructure.persistence.sqlite_connections import require_safe_sqlite; require_safe_sqlite(); print(sqlite3.sqlite_version)"
if ($LASTEXITCODE -ne 0) { throw 'Runtime no validado' }
& $python -X utf8 -m pytest -q
& $python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Los ZIP y temporales se conservan para inspección. En usos posteriores definir
`$python` con el ejecutable validado. Las herramientas estáticas pueden usar el
Python original de `.venv/Scripts`.

## Límites y verificación

- WAL permite snapshots lectores mientras escribe otro; SQLite mantiene **un solo
  escritor**. Timeout no garantiza ausencia absoluta de `SQLITE_BUSY` ante
  contención prolongada o acceso externo. El pool es por proceso, no global.
- Base, `-wal` y `-shm` requieren disco local del mismo host, no NFS/SMB. No borrar
  sidecars ni copiar únicamente `.db` mientras está activa. Usar backup SQLite o
  detener ordenadamente para obtener una copia consistente.
- `NORMAL` puede perder transacciones recientes ante pérdida de alimentación;
  no equivale a durabilidad `FULL`. Backups/restauración, checkpoints operativos y
  carga sostenida requieren validación independiente.
- No cambia API/OpenAPI, UUID, numeración, estados, MIME, visor ni extracción.
  No implementa paralelismo interno de lotes (#14), confianza OCR (#15), controles
  adicionales de producción ni certificación de producción.

`tests/integration/test_sqlite_concurrency.py` comprueba pragmas, reutilización,
exclusividad, espera/agotamiento, cierre, arranque fallido, rollback, FK y snapshots.
Combina 40 confirmaciones con 6 lectores de 50 iteraciones: exige correlativos
únicos, tres eventos por documento revisado, integridad y ninguna referencia rota.
Un fallo de historial revierte alta, estado y secuencia con pool. Los motores
inseguros se rechazan antes de crear archivos. Las suites existentes mantienen
migraciones, duplicados, PDF/OCR y HTTP. Es corrección concurrente acotada, sin
acreditar rendimiento bajo carga sostenida ni precisión OCR sobre títulos reales.
