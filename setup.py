"""Build hook: cythonize the massless C-native pipeline sources into extensions.

The request pipeline is written in Cython (``.pyx``/``.pxd``). setuptools cannot
yet read ``ext_modules`` from ``pyproject.toml``, so the extension build lives
here. Module names are derived from the ``src`` layout so a source in a
subpackage compiles to the correct dotted name (``src/massless/pipeline/_core.pyx``
becomes ``massless.pipeline._core``) instead of being flattened to a top-level
extension. Per-file ``# distutils: language = c++`` headers opt individual modules
into C++ (for ``libcpp`` containers). Until Phase 1 lands the first ``.pyx``
sources the list is empty and this builds a pure-Python package.
"""

from __future__ import annotations

from pathlib import Path

from setuptools import Extension, setup

SRC = Path("src")
extensions = [
    Extension(pyx.relative_to(SRC).with_suffix("").as_posix().replace("/", "."), [str(pyx)])
    for pyx in (SRC / "massless").rglob("*.pyx")
]

ext_modules = []
if extensions:
    from Cython.Build import cythonize

    ext_modules = cythonize(extensions, compiler_directives={"language_level": "3str"})

setup(ext_modules=ext_modules)
