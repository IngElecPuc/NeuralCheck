# NeuralCheck

NeuralCheck es una aplicación de ajedrez de escritorio hecha en Python y Tkinter. El proyecto combina una interfaz gráfica de tablero, validación de reglas, historial de partidas, edición manual de posiciones y un módulo de teoría de aperturas basado en grafos persistidos localmente con SQLite.

El proyecto también conserva una extensión C para operaciones rápidas de bitboard. Esa extensión es opcional para el uso actual de la aplicación: si no está compilada, NeuralCheck usa un fallback Python.

## Estado actual

Funcionalidades principales:

* Tablero de ajedrez interactivo con UI Tkinter.
* Validación de movimientos legales.
* Historial de partidas y navegación por posiciones.
* Carga y guardado de partidas YAML.
* Configuración manual de posiciones.
* Conversión FEN parcial para posiciones.
* Reloj configurable:

  * Bala.
  * Blitz.
  * Rápida.
  * FIDE 90/40 + 30 + 30s.
  * Correspondencia.
* Vista de tablero:

  * Vista blancas.
  * Vista negras.
  * Mostrar/ocultar coordenadas.
* Módulo de teoría:

  * Entradas de teoría persistentes.
  * Raíces sincronizadas desde partida.
  * Raíces independientes desde posición custom.
  * Nodos y relaciones de teoría.
  * Navegación gráfica por árbol.
  * Vista fija y contextual.
  * Zoom, pan, rotación y pantalla completa.
  * Posiciones persistentes de nodos.
  * Popup contextual de edición.
  * Flechas de continuación en el tablero.
  * Miniaturas de posición con origen/destino resaltado.

## Requisitos

Recomendado:

* Windows.
* PowerShell.
* Python 3.10 o superior.
* Entorno virtual Python.

Dependencias principales:

* `numpy`
* `Pillow`
* `PyYAML`
* `pytest`
* `prettytable`
* `fastapi`
* `pydantic`

El backend FastAPI existe como base experimental, pero el foco actual del proyecto es la aplicación desktop Tkinter.

## Instalación

Desde la raíz del proyecto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

Para ejecutar código con imports locales:

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
```

## Ejecutar la aplicación

Desde la raíz del proyecto:

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
python .\src\neuralcheck\main.py
```

## Compilar extensión C opcional

La extensión C `bitboardops` es opcional para el uso actual de la app. Si no está compilada, el proyecto usa `bitboardops_fallback.py`.

Para compilarla:

```powershell
Push-Location .\src\c_lib
python .\setup.py build_ext --inplace
Pop-Location
```

Después de compilar, se puede volver a ejecutar la app normalmente:

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
python .\src\neuralcheck\main.py
```

## Validación

Ejecutar todos los tests:

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
python -m pytest -q .\test
```

Smokes no destructivos:

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path

python .\scripts\smoke\check_startup.py
python .\scripts\smoke\check_controller.py
python .\scripts\smoke\check_rules.py
python .\scripts\smoke\check_position_setup.py
python .\scripts\smoke\check_legacy_history_navigation.py
python .\scripts\smoke\check_theory_store.py
python .\scripts\smoke\check_theory_sync_and_clock.py
python .\scripts\smoke\check_clock_controls.py
python .\scripts\smoke\check_theory_crud_navigation.py
python .\scripts\smoke\check_theory_map_and_board_draft.py
python .\scripts\smoke\check_theory_map_advanced.py
```

Estado validado al cierre de la etapa 8:

```text
66 passed
Startup smoke passed
Controller smoke passed
Rules smoke passed
Position setup smoke passed
Legacy history navigation smoke passed
Theory store smoke passed
Theory sync and clock smoke passed
Clock controls smoke passed
Theory CRUD navigation smoke passed
Theory map and board draft smoke passed
Theory advanced map smoke passed
```

## Estructura del proyecto

```text
.
├── config/
│   ├── board.yaml
│   ├── config.yaml
│   └── initial_position.yaml
│
├── data/
│   └── theory/
│       └── neuralcheck_theory.db        # Base local generada por la app
│
├── resources/
│   └── images/
│       └── pieces/
│           └── pieces-basic-png/        # Sprites de piezas
│
├── scripts/
│   └── smoke/
│       ├── check_startup.py
│       ├── check_controller.py
│       ├── check_rules.py
│       ├── check_position_setup.py
│       ├── check_legacy_history_navigation.py
│       ├── check_theory_store.py
│       ├── check_theory_sync_and_clock.py
│       ├── check_clock_controls.py
│       ├── check_theory_crud_navigation.py
│       ├── check_theory_map_and_board_draft.py
│       └── check_theory_map_advanced.py
│
├── src/
│   ├── c_lib/
│   │   ├── bitboardops.c
│   │   ├── bitboardops.h
│   │   ├── py_bitboardops.c
│   │   └── setup.py
│   │
│   └── neuralcheck/
│       ├── __init__.py
│       ├── main.py
│       ├── ui.py
│       ├── ui_position_editor.py
│       ├── ui_theory.py
│       ├── ui_theory_map.py
│       ├── logic.py
│       ├── bitboard.py
│       ├── bitboardops_fallback.py
│       ├── back_end.py
│       │
│       ├── application/
│       │   ├── __init__.py
│       │   ├── clock.py
│       │   ├── game_controller.py
│       │   └── theory_controller.py
│       │
│       ├── theory/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── store.py
│       │   ├── service.py
│       │   ├── sqlite_store.py
│       │   └── move_visuals.py
│       │
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── minimax.py
│       │   └── deep_q.py
│       │
│       └── utils/
│           ├── class_explorer.py
│           └── logger.py
│
├── test/
│   ├── test_bitboard.py
│   ├── test_clock.py
│   ├── test_game_controller.py
│   ├── test_logic.py
│   ├── test_minimax.py
│   ├── test_position_setup.py
│   ├── test_rule_pipeline.py
│   ├── test_theory_store.py
│   └── test_theory_map_and_board_draft.py
│
├── requirements.txt
└── README.md
```

## Componentes principales

### `src/neuralcheck/main.py`

Punto de entrada de la aplicación desktop.

### `src/neuralcheck/ui.py`

Ventana principal Tkinter. Renderiza tablero, historial, menús, reloj, flechas de continuación y coordinación general de UI.

### `src/neuralcheck/logic.py`

Motor principal de reglas de ajedrez. Maneja tablero, movimientos legales, historial, lectura de jugadas y conversión básica de posiciones.

### `src/neuralcheck/application/game_controller.py`

Capa de aplicación entre UI y motor de ajedrez. Evita que la UI dependa directamente de detalles internos de `ChessBoard`.

### `src/neuralcheck/application/clock.py`

Modelo de reloj. Soporta controles de tiempo, pausa, señal de inicio, correspondencia y control FIDE.

### `src/neuralcheck/ui_position_editor.py`

Editor gráfico de posiciones. Permite configurar tablero manualmente usando paleta visual de piezas.

### `src/neuralcheck/theory/`

Capa de dominio y persistencia del módulo de teoría.

* `models.py`: DTOs y modelos de teoría.
* `store.py`: contrato `TheoryGraphStore`.
* `service.py`: casos de uso de teoría.
* `sqlite_store.py`: implementación local SQLite.
* `move_visuals.py`: cálculo visual de origen/destino de jugadas entre nodos.

### `src/neuralcheck/application/theory_controller.py`

Controlador de aplicación para teoría. Une el tablero, la teoría y la UI sin acoplar Tkinter a SQLite.

### `src/neuralcheck/ui_theory.py`

Panel de teoría. Maneja entradas, creación de raíces, agregado de continuaciones y coordinación del mapa visual.

### `src/neuralcheck/ui_theory_map.py`

Mapa gráfico navegable de teoría. Incluye:

* cámara explícita;
* zoom centrado;
* pan;
* rotación;
* pantalla completa;
* vista fija/contextual;
* posiciones persistentes;
* popup contextual de edición;
* miniaturas con resaltado de jugada previa;
* etiquetas de jugada con contraste según color que movió.

### `src/c_lib/`

Código C opcional para operaciones rápidas de bitboard. Se conserva para futuras funcionalidades de IA/RL.

## Base de teoría

La base local se crea automáticamente en:

```text
data/theory/neuralcheck_theory.db
```

Esta base contiene entradas de teoría, nodos, relaciones y layout persistente del mapa.

No se recomienda versionar bases personales de teoría salvo que se quieran compartir explícitamente.

## Módulo de teoría

El módulo de teoría trabaja con árboles de posiciones.

Conceptos:

* Entrada de teoría: colección de posiciones relacionadas.
* Nodo: posición codificada en FEN.
* Relación: jugada que conecta un nodo padre con un nodo hijo.
* Línea sincronizada: teoría que puede reconstruirse desde la posición inicial mediante una secuencia legal.
* Posición independiente: teoría creada desde FEN o posición custom.

El mapa visual permite dos modos:

```text
Vista fija:
- conserva posiciones persistentes de nodos;
- no recalcula automáticamente al navegar;
- permite ajuste manual de nodos.

Contextual:
- recalcula la vista alrededor del nodo seleccionado;
- útil para árboles grandes o navegación profunda.
```

## Controles principales del mapa de teoría

* `Atrás`: cantidad de niveles visibles hacia ancestros.
* `Adelante`: cantidad de niveles visibles hacia descendientes.
* `Aplicar profundidad`: guarda/aplica esos niveles en la entrada actual.
* `Zoom +` / `Zoom -`: zoom con cámara.
* `Ajustar a vista`: encaja el subgrafo visible.
* `Centrar seleccionado`: centra la cámara en el nodo seleccionado.
* `↺` / `↻`: rota la vista.
* `Reordenar mapa`: recalcula layout de forma manual.
* `Pantalla completa`: abre el mapa a pantalla completa.

Controles de mouse:

* Click izquierdo sostenido: desplazar mapa.
* Click derecho sostenido: rotar mapa.
* Rueda del mouse: zoom alrededor del cursor.
* Botón central sostenido y movimiento vertical: zoom.
* Doble click izquierdo sostenido sobre nodo: mover nodo.
* Ctrl + click izquierdo sostenido sobre nodo: mover subárbol visible.
* Ctrl + click derecho sostenido sobre nodo: rotar subárbol visible.
* Doble click derecho sobre nodo: abrir popup de edición.

## Notas de desarrollo

* El backend FastAPI existe como base experimental. No es todavía la vía principal de uso.
* La capa de teoría está separada mediante `TheoryGraphStore`, para permitir que en el futuro se pueda implementar otro backend de grafos o una API remota.
* La extensión C no debe eliminarse. Aunque no sea obligatoria para el uso actual, queda reservada para aceleración futura.
* Los archivos generados como `build/`, `dist/`, `*.egg-info`, `__pycache__/`, `.pytest_cache/` y bases locales personales no deberían tratarse como fuente principal del proyecto.
