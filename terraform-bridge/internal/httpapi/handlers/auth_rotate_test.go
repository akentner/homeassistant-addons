package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
)

func TestAuthRotateSuccess(t *testing.T) {
	var logBuf bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&logBuf, nil)))
	defer slog.SetDefault(prev)

	dir := t.TempDir()
	store, _ := auth.NewFileTokenStore(dir)
	oldPlain, _ := store.Generate()
	_ = store.Persist(oldPlain)

	req := httptest.NewRequest("POST", "/v1/auth/rotate", nil)
	ctx := context.WithValue(req.Context(), auth.ActorTokenContextKey(), oldPlain)
	req = req.WithContext(ctx)
	rec := httptest.NewRecorder()

	AuthRotate(store)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.RotateResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.NewToken == "" {
		t.Errorf("NewToken empty")
	}
	if body.NewToken == oldPlain {
		t.Errorf("NewToken same as old")
	}
	if body.GraceExpiresAt == "" {
		t.Errorf("GraceExpiresAt empty")
	}
	if body.GraceExpiresAt != body.OldTokenValidUntil {
		t.Errorf("GraceExpiresAt %q != OldTokenValidUntil %q (D-03: same instant)",
			body.GraceExpiresAt, body.OldTokenValidUntil)
	}

	out := logBuf.String()
	if !strings.Contains(out, `"msg":"bridge.token.rotated"`) {
		t.Errorf("expected bridge.token.rotated audit record; got: %s", out)
	}
	if strings.Contains(out, oldPlain) {
		t.Errorf("audit log contains old plaintext; got: %s", out)
	}
	if strings.Contains(out, body.NewToken) {
		t.Errorf("audit log contains new plaintext; got: %s", out)
	}
}
