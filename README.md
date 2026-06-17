# NeuralCheck

Juego y engine de ajedrez en Python con interfaz Tkinter.

## Estado actual

La aplicación principal es de escritorio. El código C de `src/c_lib` se mantiene para trabajo futuro de bitboards, IA y entrenamiento rápido, pero la aplicación puede arrancar sin compilar la extensión C gracias a un fallback Python compatible en `src/neuralcheck/bitboardops_fallback.py`.

## Requisitos

- Python 3.10 o superior.
- Windows con PowerShell para los comandos locales recomendados.
- Compilador C solo si se quiere compilar la extensión opcional `bitboardops`.

## Instalación Python

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

Para imports locales:

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
```

## Ejecutar la app desktop

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
python -m neuralcheck.main
```

## Tests

El runner real del proyecto en este estado es `pytest` sobre la carpeta `test`.

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
python -m pytest -q .\test
```

## Smoke test no destructivo

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
python .\scripts\smoke\check_startup.py
```

## Extensión C opcional

No es necesaria para la etapa actual. Se conserva para features futuras de IA/RL.

Compilar en desarrollo:

```powershell
Push-Location .\src\c_lib
python .\setup.py build_ext --inplace
Pop-Location
```

Instalar en el entorno activo:

```powershell
Push-Location .\src\c_lib
python .\setup.py install
Pop-Location
```

Si no se compila la extensión, `src/neuralcheck/bitboardops_fallback.py` entrega las mismas funciones públicas mínimas que usa el proyecto actualmente.

## Estructura principal

```text
NeuralCheck/
├── config/
│   ├── board.yaml
│   ├── config.yaml
│   └── initial_position.yaml
├── resources/
│   └── images/
├── scripts/
│   └── smoke/
│       └── check_startup.py
├── src/
│   ├── c_lib/
│   │   ├── bitboardops.c
│   │   ├── bitboardops.h
│   │   ├── py_bitboardops.c
│   │   └── setup.py
│   └── neuralcheck/
│       ├── engine/
│       ├── bitboard.py
│       ├── bitboardops_fallback.py
│       ├── logic.py
│       ├── main.py
│       └── ui.py
├── test/
│   ├── test_bitboard.py
│   └── test_logic.py
├── README.md
└── requirements.txt
```
