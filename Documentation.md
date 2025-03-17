# Documentación del Juego de Ajedrez

## 1. Introducción

Este programa implementa un juego de ajedrez que combina una interfaz gráfica desarrollada con Tkinter y una lógica de juego basada en representaciones de tablero en NumPy y bitboards. La aplicación permite ejecutar partidas, visualizar el estado del juego, gestionar movimientos (incluyendo reglas especiales como en passant, enroque y promoción) y llevar un registro de la historia de la partida.

El sistema se compone de dos módulos principales:
- **Interfaz de Usuario (UI):** Gestiona la representación gráfica del tablero, piezas, controles (botones, reloj, historial) y la interacción del usuario.
- **Lógica del Juego:** Implementa las reglas de ajedrez, la validación de movimientos y el mantenimiento de la historia de la partida.

Esta documentación está pensada para que un desarrollador pueda comprender el funcionamiento global y sirva como base para integrar la aplicación en una función AWS Lambda conectada a API Gateway, así como para facilitar la generación de un frontend.

---

## 2. Arquitectura General

La arquitectura se divide en dos capas:

- **Capa de Presentación (Frontend / UI):**
  - Desarrollada en Tkinter para mostrar un tablero de ajedrez interactivo.
  - Incluye paneles para visualizar el tablero, piezas capturadas, reloj y el historial de jugadas.
  - Permite interacciones mediante clics y entradas de texto para enviar movimientos.

- **Capa de Lógica (Backend / Juego):**
  - Gestiona la representación interna del tablero utilizando una matriz de NumPy.
  - Emplea bitboards para optimizar ciertas operaciones de búsqueda y validación de movimientos.
  - Incluye métodos para calcular movimientos legales, validar reglas especiales (enroque, en passant, promoción) y generar notación de jugadas.
  - Permite guardar y cargar posiciones y partidas en archivos YAML o PGN.

---

## 3. Componentes Principales

### 3.1. Interfaz de Usuario (Clase `ChessUI`)

- **Objetivo:**  
  Proporcionar la capa gráfica del juego, permitiendo a los usuarios interactuar con la partida a través de una ventana Tkinter.

- **Características y Funcionalidades:**
  - **Configuración inicial:**  
    - Carga parámetros desde el archivo `config/board.yaml`, que define dimensiones, rutas de imágenes y otros parámetros de la UI.
  - **Elementos gráficos:**  
    - **Canvas del tablero:** Representa el tablero de 8x8, dibujando cuadrados alternados y posicionando las imágenes de las piezas.
    - **Canvas para piezas capturadas y reloj:** Muestra el tiempo restante de cada jugador y, en futuras versiones, información sobre piezas capturadas.
    - **Panel de historial:** Visualiza la secuencia de jugadas en un widget de texto con botones de navegación (primer movimiento, anterior, reproducir, siguiente, último).
    - **Controles adicionales:**  
      - Botones para iniciar una nueva partida, cargar y guardar partidas.
      - Entrada para debug (envío de comandos y breakpoint).
  - **Interacción:**  
    - El método `on_click` gestiona la selección y movimiento de piezas.
    - Se implementa la lógica para la promoción de peones mediante una ventana modal.

- **Métodos Clave:**
  - `draw_board()`: Dibuja el tablero y posiciona las piezas.
  - `on_click(event)`: Detecta la casilla clickeada y gestiona la selección/movimiento.
  - `update_clock()`: Actualiza el reloj de cada jugador.
  - `new_game()`, `load_game()` y `save_game()`: Manejan la gestión de partidas.
  - Métodos de navegación en el historial de jugadas: `go_to_first`, `previous_step`, `execute_move`, `next_step` y `go_to_last`.

---

### 3.2. Lógica del Juego (Clase `ChessBoard`)

- **Objetivo:**  
  Administrar la representación interna y las reglas del juego de ajedrez, calculando movimientos legales y actualizando el estado del tablero.

- **Características y Funcionalidades:**
  - **Representación del tablero:**  
    - Utiliza una matriz de NumPy de 8x8 para almacenar el estado de cada casilla.  
    - Cada pieza se codifica numéricamente: valores positivos representan piezas blancas y negativos, piezas negras.
  - **Inicialización y configuración:**  
    - Se inicializan recursos internos, como mapeos de columnas, piezas y banderas de enroque.
    - Se carga la posición inicial desde el archivo `config/initial_position.yaml`.
  - **Cálculo de movimientos legales:**  
    - Métodos como `allowed_movements`, `raycast` y `remove_illegal` calculan los movimientos permitidos para cada pieza, considerando reglas especiales y restricciones (como jaque).
  - **Ejecución de movimientos:**  
    - El método `make_move` valida y ejecuta un movimiento, actualizando el estado interno (incluyendo la historia de jugadas) y aplicando movimientos especiales (en passant, enroque, promoción).
  - **Notación de jugadas:**  
    - Convierte los movimientos realizados en notación estándar de ajedrez mediante el método `notation_from_move`.
  - **Gestión de partidas:**  
    - Permite guardar y cargar posiciones y partidas completas en archivos YAML o PGN.
  - **Sincronización con bitboards:**  
    - Se mantiene una representación en bitboard (a través de la clase `ChessBitboard`) para optimizar ciertos cálculos, sincronizada con la representación en NumPy.

- **Métodos Clave:**
  - `set_piece()`, `what_in()`: Gestionan la colocación y consulta de piezas en el tablero.
  - `allowed_movements()`, `raycast()`, `remove_illegal()`: Calculan y filtran movimientos según las reglas.
  - `make_move()`: Ejecuta un movimiento si es legal, actualizando banderas de enroque y otros estados.
  - `read_move()`: Parsea una jugada en notación estándar para determinar origen y destino.
  - Métodos para conversión de formatos: `fen2numpy()` y `numpy2fen()`.
  - `calculate_possible_moves()`: Recalcula los movimientos legales para todas las piezas.
  - Gestión de la historia y navegación entre turnos: `go2()` y otros métodos relacionados.

---

## 4. Flujo de Ejecución

1. **Inicialización:**  
   - Se crea una instancia de `ChessUI`, que carga la configuración y crea un objeto `ChessBoard` para gestionar la lógica del juego.
   - Se dibuja el tablero y se inician los relojes.

2. **Interacción del Usuario:**  
   - El usuario selecciona una pieza mediante un clic.
   - Al hacer clic en una casilla destino, se valida el movimiento utilizando la lógica de `ChessBoard`.
   - Si el movimiento es válido, se actualiza el estado interno y se redibuja el tablero.
   - Se gestionan movimientos especiales (como la promoción) mediante ventanas emergentes modales.

3. **Gestión del Juego:**  
   - La historia de jugadas se actualiza y permite la navegación a través de ella.
   - Los botones de cargar y guardar permiten persistir el estado de la partida en archivos YAML o PGN.

4. **Actualización del Reloj:**  
   - El reloj de cada jugador se actualiza cada segundo, decrementando el tiempo y mostrando el resultado en la interfaz.

---

## 5. Configuración y Archivos Externos

- **Archivos YAML:**  
  - `config/board.yaml`: Define parámetros visuales (tamaño de celdas, dimensiones de la ventana, rutas de imágenes para las piezas, etc.).
  - `config/initial_position.yaml`: Especifica la posición inicial de las piezas en el tablero.
  
- **Archivos de Partida:**  
  - Se pueden guardar y cargar partidas completas (incluyendo la historia de jugadas) en formato YAML o PGN.

---

## 6. Integración con AWS Lambda y API Gateway

Para integrar este sistema en AWS Lambda:

- **AWS Lambda:**
  - Empaquetar la aplicación junto con sus dependencias (por ejemplo, PIL, NumPy y PyYAML).
  - Exponer funciones que reciban solicitudes HTTP para obtener el estado actual del juego, ejecutar movimientos o cargar/guardar partidas.

- **API Gateway:**
  - Configurar rutas para los distintos endpoints (por ejemplo, `/new_game`, `/move`, `/state`, etc.) que invocarán la función Lambda.

- **Frontend:**
  - El desarrollador del frontend consumirá estos endpoints para mostrar el estado del juego, enviar movimientos y obtener actualizaciones en tiempo real.
  - La documentación de la API (endpoints, parámetros y respuestas) debe generarse a partir de los métodos expuestos para facilitar la interacción.

---

## 7. Conclusión

Este proyecto integra de manera robusta una interfaz gráfica interactiva con una lógica de ajedrez completa, permitiendo la ejecución y validación de partidas con reglas estándar y excepciones. La separación en módulos facilita la extensión y el mantenimiento del código, y la documentación detallada junto con la modularidad permiten su integración en entornos modernos como AWS Lambda, conectándolo con API Gateway y facilitando la creación de un frontend interactivo.

Esta documentación sirve como base para que un tercero pueda comprender, mantener y ampliar el sistema, así como para integrarlo en servicios en la nube.
