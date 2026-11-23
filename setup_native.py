"""Explicit opt-in mypyc build; normal uv installation remains pure Python."""

from mypyc.build import mypycify
from setuptools import setup

setup(
    name="demographics-native",
    ext_modules=mypycify(["demographics/kernel.py"], opt_level="3"),
)
