from pathlib import Path

from setuptools import Extension, setup

ROOT = Path(__file__).resolve().parent

module = Extension(
    "bitboardops",
    sources=[
        str(ROOT / "bitboardops.c"),
        str(ROOT / "py_bitboardops.c"),
    ],
    include_dirs=[str(ROOT)],
)

setup(
    name="bitboardops",
    version="1.0.1",
    description="Bitboard mapper of chess board in C for Python",
    ext_modules=[module],
)
