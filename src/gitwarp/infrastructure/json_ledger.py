from __future__ import annotations

from typing import Any, Callable

from .ledger import load_ledger, mutate_ledger, write_ledger
from .runtime import RepoContext


class JsonLedgerRepository:
    def load(self, ctx: RepoContext) -> dict[str, Any]:
        return load_ledger(ctx)

    def mutate(self, ctx: RepoContext, callback: Callable[[dict[str, Any]], Any]) -> Any:
        return mutate_ledger(ctx, callback)

    def write(self, ctx: RepoContext, ledger: dict[str, Any]) -> None:
        write_ledger(ctx, ledger)
