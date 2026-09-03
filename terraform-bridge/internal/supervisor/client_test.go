package supervisor

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
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

func TestClientListAddonsV2Success(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/apps" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data": map[string]any{
				"apps": []map[string]any{
					{"slug": "a", "name": "A", "version": "1.0", "state": "started", "repository": "core"},
					{"slug": "b", "name": "B", "version": "2.0", "state": "stopped", "repository": "core"},
				},
			},
		})
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	items, err := c.ListAddons(context.Background())
	if err != nil {
		t.Fatalf("ListAddons: %v", err)
	}
	if len(items) != 2 {
		t.Fatalf("got %d items, want 2", len(items))
	}
	if items[0].Slug != "a" || !items[0].Started {
		t.Errorf("items[0] = %+v, want slug=a, started=true", items[0])
	}
	if items[1].Slug != "b" || items[1].Started {
		t.Errorf("items[1] = %+v, want slug=b, started=false", items[1])
	}
}

func TestClientListAddonsV2FailsV1Succeeds(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/apps", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusForbidden)
	})
	mux.HandleFunc("/addons", func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data": map[string]any{
				"addons": []map[string]any{
					{"slug": "core_matter_server", "name": "Matter Server", "version": "9.2.0", "state": "started", "repository": "core"},
					{"slug": "core_zigbee2mqtt", "name": "Zigbee2MQTT", "version": "2.0.0", "state": "stopped", "repository": "core"},
				},
			},
		})
	})
	ts := httptest.NewServer(mux)
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	items, err := c.ListAddons(context.Background())
	if err != nil {
		t.Fatalf("ListAddons: %v", err)
	}
	if len(items) != 2 {
		t.Fatalf("got %d items, want 2", len(items))
	}
	if items[0].Slug != "core_matter_server" || !items[0].Started {
		t.Errorf("items[0] = %+v, want slug=core_matter_server, started=true", items[0])
	}
	if items[1].Slug != "core_zigbee2mqtt" || items[1].Started {
		t.Errorf("items[1] = %+v, want slug=core_zigbee2mqtt, started=false", items[1])
	}
}

func TestClientGetAddonInfoV2ToV1Fallback(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/apps/c/info", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	mux.HandleFunc("/addons/c/info", func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data": map[string]any{
				"slug": "c", "name": "C", "version": "3.0",
				"state": "started", "options": map[string]string{"k": "v"},
				"boot": "auto", "repository": "core",
			},
		})
	})
	ts := httptest.NewServer(mux)
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	info, err := c.GetAddonInfo(context.Background(), "c")
	if err != nil {
		t.Fatalf("GetAddonInfo: %v", err)
	}
	if info.Slug != "c" || !info.Started || info.Version != "3.0" {
		t.Errorf("info = %+v, want slug=c, started=true, version=3.0", info)
	}
	if info.Options["k"] != "v" {
		t.Errorf("options[k] = %q, want v", info.Options["k"])
	}
}

func TestClientGetAddonInfoBothNotFound(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/apps/ghost/info", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	mux.HandleFunc("/addons/ghost/info", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	ts := httptest.NewServer(mux)
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	_, err := c.GetAddonInfo(context.Background(), "ghost")
	if err == nil {
		t.Fatalf("expected ErrNotFound, got nil")
	}
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("err = %v, want ErrNotFound", err)
	}
}

func TestClientGetAddonInfoV2ForbiddenV1NotFound(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/apps/ghost/info", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusForbidden)
	})
	mux.HandleFunc("/addons/ghost/info", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	ts := httptest.NewServer(mux)
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	_, err := c.GetAddonInfo(context.Background(), "ghost")
	if err == nil {
		t.Fatalf("expected ErrNotFound, got nil")
	}
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("err = %v, want ErrNotFound (V2 403 + V1 404 should map to ErrNotFound)", err)
	}
}

func TestClientInstallBackgroundTrueReturnsJobID(t *testing.T) {
	var seenBody string
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/store/apps/slug/install" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		seenBody = string(body)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data":   map[string]any{"job_id": "abc123"},
		})
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	jobID, err := c.Install(context.Background(), "slug")
	if err != nil {
		t.Fatalf("Install: %v", err)
	}
	if jobID != "abc123" {
		t.Errorf("job_id = %q, want abc123", jobID)
	}
	// Verify the body is exactly {"background":true} (Pitfall 1).
	if !strings.Contains(seenBody, `"background":true`) {
		t.Errorf("body = %q, must contain background:true", seenBody)
	}
}

func TestClientInstallAlreadyInstalledReturnsErr(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusConflict)
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	_, err := c.Install(context.Background(), "slug")
	if err == nil {
		t.Fatal("expected error on 409, got nil")
	}
	if !errors.Is(err, ErrAlreadyInstalled) {
		t.Errorf("err = %v, want ErrAlreadyInstalled", err)
	}
}

func TestClientUninstallV2Success(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/apps/slug/uninstall" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	if err := c.Uninstall(context.Background(), "slug"); err != nil {
		t.Errorf("Uninstall: %v", err)
	}
}

func TestClientUninstallV2FailsV1Succeeds(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/apps/slug/uninstall", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	mux.HandleFunc("/addons/slug/uninstall", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	ts := httptest.NewServer(mux)
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	if err := c.Uninstall(context.Background(), "slug"); err != nil {
		t.Errorf("Uninstall: %v", err)
	}
}

func TestClientStartV2Success(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/apps/slug/start" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	if err := c.Start(context.Background(), "slug"); err != nil {
		t.Errorf("Start: %v", err)
	}
}

func TestClientStopV2Success(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/apps/slug/stop" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	if err := c.Stop(context.Background(), "slug"); err != nil {
		t.Errorf("Stop: %v", err)
	}
}

func TestClientOptionsV2Success(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/apps/slug/options" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), `"log_level"`) {
			t.Errorf("body must carry options payload, got %s", body)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	err := c.Options(context.Background(), "slug", map[string]any{"log_level": "debug"})
	if err != nil {
		t.Errorf("Options: %v", err)
	}
}

func TestClientValidateOptionsV2Success(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"message": "ok",
			"valid":   true,
			"pwned":   false,
		})
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	diag, err := c.ValidateOptions(context.Background(), "slug", map[string]any{"x": "y"})
	if err != nil {
		t.Fatalf("ValidateOptions: %v", err)
	}
	if diag.Message != "ok" {
		t.Errorf("Message = %q, want ok", diag.Message)
	}
	if !diag.Valid {
		t.Errorf("Valid = false, want true")
	}
	if diag.Pwned == nil {
		t.Fatalf("Pwned = nil, want &false")
	}
	if *diag.Pwned {
		t.Errorf("Pwned = true, want false")
	}
}

func TestClientGetJobStatusDoneTrue(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Bare job dict per supervisor/api/jobs.py:job_info (no
		// {result, data} envelope; see 12-CONTEXT Pitfall A3).
		_ = json.NewEncoder(w).Encode(map[string]any{
			"job_id": "abc",
			"done":   true,
			"result": map[string]any{"ok": true},
		})
	}))
	defer ts.Close()

	c := NewClient(func() string { return "stub" })
	c = c.WithBaseURLForTest(ts.URL)

	job, err := c.GetJobStatus(context.Background(), "abc")
	if err != nil {
		t.Fatalf("GetJobStatus: %v", err)
	}
	if job.JobID != "abc" {
		t.Errorf("JobID = %q, want abc", job.JobID)
	}
	if !job.Done {
		t.Errorf("Done = false, want true")
	}
}

func TestMapError(t *testing.T) {
	cases := []struct {
		name     string
		err      error
		wantCode int
		wantErr  string
	}{
		{"ErrNotFound", ErrNotFound, 404, "not_found"},
		{"ErrAlreadyInstalled", ErrAlreadyInstalled, 409, "already_installed"},
		{"ErrCriticalAddon", ErrCriticalAddon, 403, "critical_addon_protected"},
		{"ErrPreventedDestroy", ErrPreventedDestroy, 403, "prevented_destroy"},
		{"ErrLocked", ErrLocked, 423, "locked"},
		{"ErrTransient", ErrTransient, 502, "upstream_error"},
		{"default (wrapped transient)", fmt.Errorf("random: %w", ErrTransient), 502, "upstream_error"},
		{"unknown error", errors.New("who knows"), 502, "upstream_error"},
		{"nil", nil, 200, ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			code, ec := MapError(tc.err)
			if code != tc.wantCode {
				t.Errorf("status = %d, want %d", code, tc.wantCode)
			}
			if ec != tc.wantErr {
				t.Errorf("error_code = %q, want %q", ec, tc.wantErr)
			}
		})
	}
}
