"""Pure Python compatibility layer for the optional C extension ``bitboardops``.

The project keeps the C extension for future high-throughput features, but the
Tkinter application and the unit tests should still import and run when that
extension has not been compiled for the current Python/OS combination.

This module intentionally mirrors the tiny public API exposed by
``src/c_lib/py_bitboardops.c``:

- ``visualize(bitboard)``
- ``getBitboardPosition(position)``
"""

from __future__ import annotations

BOARD_SIZE = 8
_MASK_64 = (1 << 64) - 1


def _validate_position(position: str) -> None:
    if not isinstance(position, str) or len(position) != 2:
        raise ValueError("position must be a chess square like 'e4'")

    file_, rank = position[0], position[1]
    if file_ not in "abcdefgh" or rank not in "12345678":
        raise ValueError("position must be inside the board, from a1 to h8")


def visualize(bitboard: int) -> None:
    """Print a 64-bit bitboard using the same orientation as the C helper."""
    value = int(bitboard) & _MASK_64
    for bit_index in range(63, -1, -1):
        print("1" if value & (1 << bit_index) else "0", end="")
        if bit_index % BOARD_SIZE == 0:
            print()
    print()


def getBitboardPosition(position: str) -> int:
    """Return the bit mask for a square using the C extension's mapping."""
    _validate_position(position)
    cols_to_int = "hgfedcba"
    rows_to_int = "12345678"
    col = cols_to_int.index(position[0])
    row = rows_to_int.index(position[1])
    return (1 << col) << (row * BOARD_SIZE)
