"""Explicit opt-in mypyc build; normal uv installation remains pure Python."""

from collections.abc import Sequence
from typing import cast

from mypyc.build import mypycify
from setuptools import Extension, setup

# On Python 3.11 mypyc also annotates stdlib distutils extensions as possible.
# With setuptools imported above, mypyc always selects setuptools.Extension.
extensions = cast(Sequence[Extension], mypycify(["demographics/kernel.py"], opt_level="3"))

setup(
    name="demographics-native",
    ext_modules=extensions,
)
