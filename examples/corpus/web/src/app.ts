// Demo web surface entry: renders balances from the ledger API.
export function renderBalances(balances: Record<string, number>): string {
  return Object.entries(balances)
    .map(([name, cents]) => `${name}: ${(cents / 100).toFixed(2)}`)
    .join("\n");
}
