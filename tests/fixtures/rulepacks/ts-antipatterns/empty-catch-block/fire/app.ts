async function load(url: string) {
  try {
    await fetch(url, { signal: AbortSignal.timeout(1000) });
  } catch (err) { }
}
