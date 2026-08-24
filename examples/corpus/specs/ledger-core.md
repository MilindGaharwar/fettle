---
fettle-spec: v1
id: ledger-core
status: active
scope:
  - "src/fettle_demo/**"
---

## Requirements

- R1. Transfers move funds atomically between accounts.
- R2. Accounts reject overdrafts.

## Scenarios

### S1. Transfer moves funds (traces R1)
Given two funded accounts
When a transfer executes
Then balances reflect the move exactly

### S2. Overdraft is rejected (traces R2)
Given an account with insufficient funds
When a withdrawal exceeds balance
Then a ValueError is raised and balance is unchanged
