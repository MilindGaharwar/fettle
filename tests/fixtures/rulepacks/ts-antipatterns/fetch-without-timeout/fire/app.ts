async function load(url: string) {
  const res = await fetch(url);
  return res.json();
}
