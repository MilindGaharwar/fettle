// Fettle test fixture: fetch without timeout/abort signal
async function getData() {
  const response = await fetch("https://api.example.com/data");
  return response.json();
}
