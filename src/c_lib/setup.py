from setuptools import setup, Extension

module = Extension(
    "bitboardops", 
    sources=['src/c/bitboardops.c', 'src/c/py_bitboardops.c']  # Ambos archivos se compilan juntos
)

setup(
    name='bitboardops',
    version='1.0.1',
    description='Bitboard mapper of chess board in C for Python',
    ext_modules=[module],
)