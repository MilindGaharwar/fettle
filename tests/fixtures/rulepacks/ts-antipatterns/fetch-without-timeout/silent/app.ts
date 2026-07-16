async function load(url: string) {
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  return res.json();
}
