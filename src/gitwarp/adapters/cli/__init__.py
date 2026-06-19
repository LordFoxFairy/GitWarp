from __future__ import annotations

from .parser import build_parser

__all__ = ["build_parser", "main"]


def __getattr__(name: str) -> object:
    if name == "main":
        from .entrypoint import main

        return main
    raise AttributeError(name)
