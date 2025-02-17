# NeuralCheck
Juego y engine de ajedrez 

Este es un juego de ajedrez bastante simple que utiliza TKinter como módulo principal para la UI. Las imágenes las descargué de [GreenChess](https://greenchess.net/).
El motor está en diseño en la etapa actual. Contará con dos etapas, una deductiva clásica con algoritmo MinMax, y otra inductiva potenciada por Machine Learning.
Actualmente el juego está en la etapa más básica de desarrollo. 

# Dependencias
Tiene un módulo para trabajo en C que se puede instalar en el ambiente virtual haciendo
```bash
python src/setup.py build
```
Para compilarlo y 
```bash
python src/setup.py install
```
para instalarlo. Luego de esto, por supuesto que es necesario instalar

```bash
pip install -r requirements.txt
```


# Estructura

NeuralCheck/
├── config/               # Archivos de configuración (board.yaml, config.yaml)
├── dist/                 # (Si generas paquetes distribuidos, esto es útil)
├── resources/            # (Sprites, imágenes o archivos externos)
├── src/
│   ├── c_lib/            # Código en C (mantenido aparte)
│   │   ├── bitboardops.c
│   │   ├── bitboardops.h
│   │   ├── py_bitboardops.c
│   │   └── setup.py
│   ├── neuralchess/      # Convertimos esto en un paquete principal de Python
│   │   ├── engine/       # Subpaquete para motores de IA
│   │   │   ├── __init__.py
│   │   │   ├── minimax.py  # Motor deductivo MinMax
│   │   │   └── deep_q.py   # Motor inductivo con Machine Learning
│   │   ├── __init__.py   # Indica que esto es un paquete
│   │   ├── bitboard.py   # Operaciones de bitboard en alto nivel
│   │   ├── logic.py      # Lógica del juego de ajedrez en alto nivel
│   │   ├── ui.py         # Interfaz gráfica con Tkinter
├── test/                 # Pruebas unitarias
│   ├── test_logic.py     # Pruebas para logic.py
│   ├── test_bitboard.py  # Pruebas para bitboard.py
│   └── test_minimax.py   # Pruebas para el motor MinMax
├── venv/                 # Entorno virtual (excluido en .gitignore)
├── .gitignore
├── README.md
└── requirements.txt
