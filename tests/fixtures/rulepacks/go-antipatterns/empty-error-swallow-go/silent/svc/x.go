package svc

func f() error {
	if err := do(); err != nil {
		return err
	}
	return nil
}
