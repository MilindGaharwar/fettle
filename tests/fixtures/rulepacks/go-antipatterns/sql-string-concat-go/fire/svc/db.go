package svc

func q(db DB, id string) error {
	_, err := db.Query("SELECT * FROM t WHERE id = " + id)
	return err
}
