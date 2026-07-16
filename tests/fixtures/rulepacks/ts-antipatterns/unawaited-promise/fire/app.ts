function fire(url: string) {
  fetch(url, { signal: AbortSignal.timeout(1000) });
}
