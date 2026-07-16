async function byId(db: Db, id: string) {
  return db.query(`SELECT * FROM cases WHERE id = ${id}`);
}
