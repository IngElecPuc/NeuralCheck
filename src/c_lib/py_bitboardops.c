#include "bitboardops.h"

// Definition of the module's methods
static PyMethodDef MiExtensionMethods[] = {
    {"visualize", pyVisualize, METH_VARARGS, "Prints the bitboard in binary format"},
    {"getBitboardPosition", pyGetBitboardPosition, METH_VARARGS, "Gets the bitboard corresponding to a position (e.g., 'e4')"},
    {NULL, NULL, 0, NULL}
};

static PyObject* pyVisualize(PyObject *self, PyObject *args) {
    int64_t bitboard;
    if (!PyArg_ParseTuple(args, "L", &bitboard)) {
        return NULL;
    }
    
    visualize(bitboard);  
    Py_RETURN_NONE;
}

static PyObject* pyGetBitboardPosition(PyObject *self, PyObject *args) {
    const char *position;
    if (!PyArg_ParseTuple(args, "s", &position)) {
        return NULL;
    }
    int64_t result = getBitboardPosition(position);
    return PyLong_FromLongLong(result);
}

static struct PyModuleDef bitboard_module = {
    PyModuleDef_HEAD_INIT,
    "bitboardops",            // Module name
    "Bit-level board management module",  // Module documentation
    -1,                    // Global state size (always -1 in simple modules)
    MiExtensionMethods
};

PyMODINIT_FUNC PyInit_bitboardops(void) { 
    return PyModule_Create(&bitboard_module);
}
