package svc

import "net/http"

func newClient() *http.Client {
	c := http.Client{}
	return &c
}
