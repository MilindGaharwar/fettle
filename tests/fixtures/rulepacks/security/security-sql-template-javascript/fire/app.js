const userId = request.params.id;
const query = `SELECT * FROM users WHERE id = ${userId}`;
