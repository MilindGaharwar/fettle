// Fettle test fixture: SQL injection via template literal
function getUser(userId: string) {
  const query = `SELECT * FROM users WHERE id = ${userId}`;
  return db.execute(query);
}
