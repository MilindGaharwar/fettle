package svc

import (
	"net/http"
	"time"
)

func newClient() *http.Client {
	c := http.Client{Timeout: 30 * time.Second}
	return &c
}
