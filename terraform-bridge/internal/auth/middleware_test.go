package auth

import (
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestResolveBindAddressRejectsAllInterfaces locks in the S-4
// invariant: bind_address=0.0.0.0 is always refused regardless of
// any allowed_subnets configuration.
func TestResolveBindAddressRejectsAllInterfaces(t *testing.T) {
	cases := [][]string{
		nil,
		{},
		{"0.0.0.0/0"},
		{"10.0.0.0/8"},
		{"192.168.0.0/16"},
	}
	for _, subnets := range cases {
		_, err := ResolveBindAddress("0.0.0.0", subnets, t.TempDir())
		if err == nil {
			t.Errorf("ResolveBindAddress(0.0.0.0, %v) = nil error, want refusal", subnets)
			continue
		}
		if !strings.Contains(err.Error(), "0.0.0.0") {
			t.Errorf("ResolveBindAddress(0.0.0.0, %v) error %q does not name the refused address", subnets, err)
		}
	}
}

func TestResolveBindAddressRejectsInvalidIP(t *testing.T) {
	cases := []string{
		"not-an-ip",
		"999.999.999.999",
		"::garbage::",
		"hostname.example.com",
	}
	for _, addr := range cases {
		_, err := ResolveBindAddress(addr, nil, t.TempDir())
		if err == nil {
			t.Errorf("ResolveBindAddress(%q, nil) = nil error, want refusal", addr)
		}
	}
}

// TestResolveBindAddressAcceptsCIDR exercises the allowed_subnets
// branch without depending on real /sys/class/net. With no
// Tailscale interfaces present, an explicit IP inside an
// allowed CIDR must succeed; an IP outside every CIDR must fail.
func TestResolveBindAddressAcceptsCIDR(t *testing.T) {
	dir := t.TempDir() // empty -> no tailscale* matches
	ip := net.ParseIP("192.168.5.10").String()

	got, err := ResolveBindAddress(ip, []string{"192.168.0.0/16"}, dir)
	if err != nil {
		t.Fatalf("ResolveBindAddress(%q, [%q], %q) unexpected error: %v", ip, "192.168.0.0/16", dir, err)
	}
	if got != ip {
		t.Errorf("ResolveBindAddress = %q, want %q", got, ip)
	}

	// Outside the CIDR.
	if _, err := ResolveBindAddress("10.0.0.1", []string{"192.168.0.0/16"}, dir); err == nil {
		t.Errorf("ResolveBindAddress(10.0.0.1, [192.168.0.0/16]) = nil error, want refusal")
	}
}

func TestResolveBindAddressRejectsBadCIDR(t *testing.T) {
	if _, err := ResolveBindAddress("192.168.1.1", []string{"not-a-cidr"}, t.TempDir()); err == nil {
		t.Errorf("ResolveBindAddress with bad CIDR entry = nil error, want refusal")
	}
}

// TestRequireBearerEnforcesAuth exercises the chi middleware via
// httptest: missing header → 401, wrong token → 401, correct
// token → 200 with stashed plaintext in context.
func TestRequireBearerEnforcesAuth(t *testing.T) {
	dir := t.TempDir()
	store, err := NewFileTokenStore(dir)
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	token, _ := store.Generate()
	if err := store.Persist(token); err != nil {
		t.Fatalf("Persist: %v", err)
	}

	var seen string
	handler := RequireBearer(store)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		v, _ := r.Context().Value(ActorTokenContextKey()).(string)
		seen = v
		w.WriteHeader(http.StatusOK)
	}))

	cases := []struct {
		name   string
		header string
		want   int
	}{
		{"missing", "", http.StatusUnauthorized},
		{"wrong scheme", "Basic " + token, http.StatusUnauthorized},
		{"empty bearer", "Bearer ", http.StatusUnauthorized},
		{"wrong token", "Bearer " + strings.Repeat("a", 43), http.StatusUnauthorized},
		{"correct", "Bearer " + token, http.StatusOK},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			seen = ""
			req := httptest.NewRequest(http.MethodGet, "/v1/whoami", nil)
			if tc.header != "" {
				req.Header.Set("Authorization", tc.header)
			}
			rr := httptest.NewRecorder()
			handler.ServeHTTP(rr, req)
			if rr.Code != tc.want {
				t.Errorf("status = %d, want %d (body=%q)", rr.Code, tc.want, rr.Body.String())
			}
		})
	}

	// Confirm context stashing happened on the success path.
	if seen != token {
		t.Errorf("context plaintext = %q, want %q", seen, token)
	}
}
