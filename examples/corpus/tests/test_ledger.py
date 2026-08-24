"""Corpus tests double as P77 benchmark seeds via trace markers."""

from __future__ import annotations

from fettle_demo.accounts import Account
from fettle_demo.ledger import transfer


def test_transfer_moves_funds():
    # traces: ledger-core/S1
    src, dst = Account("a", 500), Account("b", 0)
    transfer(src, dst, 200)
    assert src.balance_cents == 300 and dst.balance_cents == 200


def test_overdraw_rejected():
    # traces: ledger-core/S2
    acct = Account("a", 10)
    try:
        acct.withdraw(20)
        raised = False
    except ValueError:
        raised = True
    assert raised
