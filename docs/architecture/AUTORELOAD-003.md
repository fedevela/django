# AUTORELOAD-003 — Dedupe y normalización determinista de `manage.py` en
# observación de autoreload

## Requirement
- `GUID: AUTORELOAD-003`
- La colección de archivos observados debe incluir `manage.py` como ruta absoluta
  estable y sin duplicados, sin modificar la lógica de ordenación por módulos,
  glob o file-root no relacionada con el path de invocación.

## Locus de presión de arquitectura (requisito -> estructura)
- `compute_invocation_script_path`
  Presión: **contrato de normalización de frontera de entrada** (propietario: capa de
  bootstrap de autoreload).
- `run_with_reloader` (ruta `DJANGO_AUTORELOAD_ENV == true` + bloque `StatReloader`)
  Presión: **seam de integración padre-hijo hacia el conjunto observado** (ownership:
  orquestador de arranque/reload del proceso hijo).
- `BaseReloader.watch_file`
  Presión: **frontera del dominio de colección observada** (estado canónico y sin
  entradas duplicadas por equivalencia de path real).

## Mapa de requisitos a arquitectura (archivo/lugar funcional)
- `AUTORELOAD-003`
  - `django/utils/autoreload.py` `compute_invocation_script_path`
  - `django/utils/autoreload.py` `run_with_reloader` (bloque StatReloader)
  - `django/utils/autoreload.py` `BaseReloader.watch_file`
  - `tests/utils_tests/test_autoreload.py` `AUTORELOAD_VERIFICATION_MAP`
  - `tests/utils_tests/test_autoreload.py` `AUTORELOADRequirementTraceabilityTests` (2 pruebas placeholder)

## Decisiones de colocación y fronteras
- **Frontera de entrada de ruta**:
  `compute_invocation_script_path` permanece en `django.utils.autoreload` para conservar
  un punto único de normalización y evitar que el contrato de reloader se mezcle con
  parsing de CLI.
- **Frontera de inyección en watchset**:
  `run_with_reloader` conserva el punto de inserción en `reloader.watch_file()` para
  mantener el mismo flujo de recolección de snapshots y detectar cambios con el mismo
  ciclo actual.
- **Frontera de estado observacional**:
  `BaseReloader.watch_file` conserva la autoridad sobre la deduplicación y evita
  que alias/symlinks o formas de invocación distintas introduzcan entradas
  replicadas en `extra_files`.

## Dependencias intencionales
- `run_with_reloader` depende de `compute_invocation_script_path` para transformar
  `sys.argv[0]` en un valor estable antes de llamar a `watch_file`.
- `run_with_reloader` depende de `get_reloader` y de su interfaz `watch_file`.
- `BaseReloader.watch_file` depende de representación canónica de path (`resolve`/`realpath`)
  para preservar invariantes en `extra_files`.

## Integración y seams (puntos de contrato)
- **Seam 1 — canonicalización de entrada**:
  entrada cruda de `sys.argv[0]` -> `compute_invocation_script_path` -> `run_with_reloader`.
- **Seam 2 — contrato de inscripción**:
  `compute_invocation_script_path` -> `BaseReloader.watch_file` (solo valor canónico, no
  ruta textual de invocación).
- **Seam 3 — deduplicación de watchset**:
  `watch_file` debe conservar un dominio de unicidad por ruta real para la colección
  `extra_files` de reloader.

## Estado de completitud arquitectónica
- Presiones de arquitectura cubiertas por ubicación y fronteras explícitas sin cambios
  de comportamiento aún.
- Trazabilidad preservada desde `AUTORELOAD-003` a:
  `django/utils/autoreload.py` y `tests/utils_tests/test_autoreload.py`.
- Artefacto de arquitectura creado:
  - `docs/architecture/AUTORELOAD-003.md`
