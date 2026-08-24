"""Minimal account primitive for the demo ledger."""

from __future__ import annotations


class Account:
    def __init__(self, name: str, balance_cents: int = 0) -> None:
        self.name = name
        self.balance_cents = balance_cents

    def deposit(self, amount_cents: int) -> None:
        if amount_cents < 0:
            raise ValueError("deposit must be non-negative")
        self.balance_cents += amount_cents

    def withdraw(self, amount_cents: int) -> None:
        if amount_cents > self.balance_cents:
            raise ValueError("insufficient funds")
        self.balance_cents -= amount_cents
