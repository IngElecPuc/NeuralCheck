#ifndef BITBOARD_EXTENSION
#define BITBOARD_EXTENSION

#include <Python.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

void visualize(int64_t bitboard);
int64_t getBitboardPosition(const char *position);

static PyObject* pyVisualize(PyObject *self, PyObject *args);
static PyObject* pyGetBitboardPosition(PyObject *self, PyObject *args);

#endif // BITBOARD_EXTENSION