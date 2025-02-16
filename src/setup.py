from setuptools import setup, Extension

module = Extension(
    "bitboard", 
    sources=['bitboard.c', 'py_bitboard.c']  # Ambos archivos se compilan juntos
)

setup(
    name='bitboard',
    version='1.0',
    description='Bitboard mapper of chess board in C for Python',
    ext_modules=[module],
)