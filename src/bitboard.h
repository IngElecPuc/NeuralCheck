#ifndef BITBOARD_EXTENSION
#define BITBOARD_EXTENSION

#include <Python.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

static void* visualize(int64_t bitboard);
static int64_t getBitboardPosition(char position[]);

#endif // BITBOARD_EXTENSION