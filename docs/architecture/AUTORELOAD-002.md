# AUTORELOAD-002 — Gestión de recarga por `manage.py` en `StatReloader`

## Requirement
- `GUID: AUTORELOAD-002`
- `manage.py` editado y persistido debe entrar en la comparación de snapshot y disparar el ciclo normal de recarga del `StatReloader`.
- No se introduce un camino de reinicio nuevo; reutilizar semántica existente (exit code `3` + `restart_with_reloader`).

## Locus de presión de arquitectura (requisito -> estructura)
- `compute_invocation_script_path`  
  Presión: **contrato de entrada/normalización de path** (propietario: capa de utilidad de bootstrap de autoreload).
- `run_with_reloader` (bloque StatReloader con `DJANGO_AUTORELOAD_ENV`)  
  Presión: **registro de dependencia directa al set de watch** (ownership: orquestador de loop de recarga).
- `BaseReloader.watch_file` / `BaseReloader.watched_files`  
  Presión: **frontera de colección de archivos observables** (límite estable para inyección de archivos extra).
- `StatReloader.snapshot_files`  
  Presión: **fuente de estado transaccional de observación** (snapshot persistente por iteración).
- `StatReloader.tick`  
  Presión: **detector de diferencias temporal** (snapshot diff a evento de cambio).
- `BaseReloader.notify_file_changed`  
  Presión: **señal de cambio** (fan-out de cambio sin acoplamiento al tipo de estrategia).
- `restart_with_reloader` + `run_with_reloader` (separación padre/hijo)  
  Presión: **seam de integración padre-hijo y política de reinicio estándar**.

## Mapa de requisitos a arquitectura (archivo/línea funcional)
- `AUTORELOAD-002`  
  - `django/utils/autoreload.py` `compute_invocation_script_path`  
  - `django/utils/autoreload.py` `run_with_reloader` (inscripción de `invoked_script`).
  - `django/utils/autoreload.py` `BaseReloader.watched_files`
  - `django/utils/autoreload.py` `StatReloader.snapshot_files`
  - `django/utils/autoreload.py` `StatReloader.tick`
  - `django/utils/autoreload.py` `BaseReloader.notify_file_changed`
  - `django/utils/autoreload.py` `trigger_reload` / `restart_with_reloader`
- `AUTORELOAD-002`  
  - `tests/utils_tests/test_autoreload.py` `AUTORELOAD_VERIFICATION_MAP`
  - `tests/utils_tests/test_autoreload.py` `AUTORELOADRequirementTraceabilityTests`

## Decisiones de colocación y fronteras
- **Frontera de invocación**:  
  `compute_invocation_script_path` permanece en módulo `django.utils.autoreload` para evitar acoplar parseo de path al loop de recarga.
- **Frontera de observabilidad de archivos**:  
  Registro de `manage.py` en `run_with_reloader` via `reloader.watch_file(...)` para que el mismo contrato de archivos observados alimente el snapshot.
- **Frontera de detección temporal**:  
  `StatReloader.snapshot_files` continúa siendo responsable de producir pares `(path, mtime)` y `tick` de detectar transición de estado.
- **Frontera de activación y reinicio**:  
  Cambios detectados se publican por `notify_file_changed` + `trigger_reload(3)`; el flujo padre sigue en `restart_with_reloader` con retorno estándar.

## Direcciones de dependencia (intencionales)
- `run_with_reloader` depende de `compute_invocation_script_path` para obtener path absoluto canónico.
- `run_with_reloader` depende de `get_reloader` y `restart_with_reloader`; `restart_with_reloader` depende de `get_child_arguments`.
- `StatReloader.tick` depende de `snapshot_files` y emite eventos a `notify_file_changed`.
- `notify_file_changed` depende de `file_changed` signal; el handler predeterminado debe disparar el mismo camino `trigger_reload` usado por otros cambios de archivo.

## Integración y seams (puntos de expansión)
- **Seam 1 — child/process boundary**: cambio de ciclo por variable de entorno `RUN_MAIN` y subprocesso de recarga.
- **Seam 2 — reloader strategy boundary**: soporte future para otros `Reloader`, conservando comportamiento de selección en `get_reloader`.
- **Seam 3 — signal boundary**: `file_changed`/`trigger_reload` como punto de extensión sin tocar flujo de reinicio.

## Estado de completitud arquitectónica
- Presión de requisitos cubierta con estructura existente + artefacto adicional.
- Trazabilidad preservada entre `AUTORELOAD-002` y puntos de cambio en `django/utils/autoreload.py`.
- No se añade ninguna ruta de señalización de reinicio nueva.
- Se añadió el artefacto de arquitectura:
  - `docs/architecture/AUTORELOAD-002.md` (nueva).
