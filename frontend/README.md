# Fast Procedure: interfaz de gestión vehicular

SPA local en React 19, TypeScript 6 y Vite 8. El [README principal](../README.md) describe el backend y el [SRS](../docs/srs-spec-backend-fastapi.md) registra requisitos y límites.

## Ejecutar

Requiere Node 22.12 o superior de la rama 22, o una versión posterior compatible con Vite, y npm. Desde esta carpeta:

```bash
npm ci
npm run dev -- --host 127.0.0.1
```

Abrir la URL informada por Vite (normalmente `http://127.0.0.1:5173`). En otra terminal, desde la raíz y con el entorno Python activado:

```bash
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

`src/services/api.ts` usa `http://127.0.0.1:8000/api/v1` directamente. No existe proxy de Vite ni variable de entorno para esa base. Si se cambia el backend, hay que alinear el cliente y los orígenes CORS permitidos mediante `ALLOWED_HOSTS` del backend.

## Flujo y organización

- `App.tsx`: navegación local en estado React y coordinación de consultas compartidas.
- `views/`: Inicio, Carga, Vehículos, Métricas, Historial, Configuración y Ayuda.
- `components/`: carga de archivos, edición de seis campos, tablas y gráficos.
- `hooks/`: carga de vehículos/historial y control de revisión/confirmación individual y múltiple.
- `services/api.ts` y `types/`: llamadas HTTP, validación de respuestas y contratos TypeScript.
- `utils/`: búsqueda, prioridades, CSV y métricas desde documentos, vehículos e historial reales.
- `tests/`: pruebas con `node:test`, TypeScript y simulaciones; no requieren otro runner.

Carga envía archivos a `/documents/batch`, muestra fallos por archivo, permite corregir los seis campos y guarda la revisión con PATCH antes de confirmar. La confirmación múltiple omite pendientes y éxitos previos. Documentos, vehículos e historial se recuperan de la API; las respuestas antiguas no deben pisar revisiones recientes. Las métricas muestran errores y estados vacíos sin inventar valores. CSV exporta el listado de vehículos recibido.

El tema claro/oscuro dura durante la sesión. Configuración incluye opciones de demostración y notificaciones deshabilitadas; no administra usuarios, permisos ni servicios de notificación.

## Verificar

```bash
npm test
npm run lint
npm run build
npm run preview -- --host 127.0.0.1
```

`npm test` ejecuta `node --test tests/*.test.mjs`; la suite actual contiene 78 tests. Incluye cliente HTTP, control de revisiones, renderizado, métricas, búsquedas y CSV con simulaciones. No equivale a una prueba integral en navegador ni mide precisión del OCR. El build ejecuta TypeScript y Vite; `preview` sirve el resultado para evaluación local. Desde Bash en la raíz también se puede usar `bash run.sh frontend-test` tras `npm ci`.

Usar documentos sintéticos. La API no tiene autenticación/autorización; mantener la evaluación en localhost. No publicar documentos, metadatos, bases de datos ni secretos.
