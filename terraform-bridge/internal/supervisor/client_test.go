package supervisor

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestClientGetSupervisorInfoSuccess(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/supervisor/info" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data": map[string]any{
				"supervisor":    "2026.08.0",
				"homeassistant": "2026.8.3",
			},
		})
	}))
	defer ts.Close()

	c := &Client{
		httpClient: &http.Client{Transport: &tokenInjectingTransport{tokenFn: func() string { return "fake-supervisor-token" }}},
		baseURL:    ts.URL,
		tokenFn:    func() string { return "fake-supervisor-token" },
	}

	info, err := c.GetSupervisorInfo(context.Background())
	if err != nil {
		t.Fatalf("GetSupervisorInfo: %v", err)
	}
	if info.Version != "2026.08.0" {
		t.Errorf("Version = %q, want %q", info.Version, "2026.08.0")
	}
}

func TestClientGetSupervisorInfoSendsBearer(t *testing.T) {
	var seenAuth string
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seenAuth = r.Header.Get("Authorization")
		_, _ = io.ReadAll(r.Body)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"result": "ok", "data": map[string]any{"supervisor": "x"}})
	}))
	defer ts.Close()

	c := &Client{
		httpClient: &http.Client{Transport: &tokenInjectingTransport{tokenFn: func() string { return "fake-supervisor-token" }}},
		baseURL:    ts.URL,
		tokenFn:    func() string { return "fake-supervisor-token" },
	}

	if _, err := c.GetSupervisorInfo(context.Background()); err != nil {
		t.Fatalf("GetSupervisorInfo: %v", err)
	}
	if seenAuth != "Bearer fake-supervisor-token" {
		t.Errorf("Authorization = %q, want %q", seenAuth, "Bearer fake-supervisor-token")
	}
}
