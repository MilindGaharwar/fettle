"""Demo ledger: transfers between accounts."""

from __future__ import annotations

from fettle_demo.accounts import Account


def transfer(source: Account, target: Account, amount_cents: int) -> None:
    source.withdraw(amount_cents)
    target.deposit(amount_cents)


def total(accounts: list[Account]) -> int:
    return sum(a.balance_cents for a in accounts)
