// Fettle test fixture: empty catch block
async function fetchData() {
  try {
    const res = await fetch("/api/data");
    return res.json();
  } catch (e) { }
}
