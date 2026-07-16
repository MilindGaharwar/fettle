async function ok(url: string) {
  const res = await fetch(url, { signal: AbortSignal.timeout(1000) });
  return res;
}

function chained(url: string) {
  fetch(url, { signal: AbortSignal.timeout(1000) }).then((r) => r.json()).catch(() => {});
}
