package main

func loadUser(db Database, userID string) {
	db.Query("SELECT * FROM users WHERE id = " + userID)
}
