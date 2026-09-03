package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"terraform-bridge/contract"
	"terraform-bridge/internal/version"
)

func TestVersionHandler(t *testing.T) {
	const bridgeVersion = "0.1.0"
	h := Version(bridgeVersion)

	rec := httptest.NewRecorder()
	h(rec, httptest.NewRequest("GET", "/v1/version", nil))

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.VersionHandshake
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.BridgeVersion != bridgeVersion {
		t.Errorf("BridgeVersion = %q, want %q", body.BridgeVersion, bridgeVersion)
	}
	if body.SchemaVersion != version.SchemaVersion {
		t.Errorf("SchemaVersion = %q, want %q", body.SchemaVersion, version.SchemaVersion)
	}
	if body.MinProviderVersion != version.MinProviderVersion {
		t.Errorf("MinProviderVersion = %q, want %q", body.MinProviderVersion, version.MinProviderVersion)
	}
	if body.MaxProviderVersion != version.MaxProviderVersion {
		t.Errorf("MaxProviderVersion = %q, want %q", body.MaxProviderVersion, version.MaxProviderVersion)
	}
}
