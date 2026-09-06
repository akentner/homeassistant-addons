package auth

import (
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// makeStubAddrFn returns an addrFn closure that returns canned IPs per
// interface name. Interfaces not in the map return (nil, nil) — same
// behavior as a real interface with no addresses.
func makeStubAddrFn(addrs map[string][]net.IP) func(string) ([]net.IP, error) {
	return func(name string) ([]net.IP, error) {
		return addrs[name], nil
	}
}

func TestResolveBindAddressAutoFindsFirstTailscaleIP(t *testing.T) {
	// Create a fake /sys/class/net with tailscale0 entry.
	dir := t.TempDir()
	if err := os.Mkdir(filepath.Join(dir, "tailscale0"), 0o755); err != nil {
		t.Fatalf("mkdir tailscale0: %v", err)
	}
	// Add a non-tailscale interface to prove it's not selected.
	if err := os.Mkdir(filepath.Join(dir, "eth0"), 0o755); err != nil {
		t.Fatalf("mkdir eth0: %v", err)
	}

	addrFn := makeStubAddrFn(map[string][]net.IP{
		"tailscale0": {net.ParseIP("100.64.0.1")},
		"eth0":       {net.ParseIP("192.168.1.5")},
	})

	got, err := ResolveBindAddress("auto", nil, dir, addrFn)
	if err != nil {
		t.Fatalf("ResolveBindAddress(auto, ...): %v", err)
	}
	want := "100.64.0.1"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestResolveBindAddressAutoNoTailscaleIface(t *testing.T) {
	dir := t.TempDir() // empty — no tailscale* entries

	addrFn := makeStubAddrFn(map[string][]net.IP{
		"eth0": {net.ParseIP("192.168.1.5")},
	})

	_, err := ResolveBindAddress("auto", nil, dir, addrFn)
	if err == nil {
		t.Errorf("ResolveBindAddress(auto, empty dir) = nil error, want refusal")
	}
	if !strings.Contains(err.Error(), "tailscale") {
		t.Errorf("error %q does not mention tailscale", err.Error())
	}
}

func TestResolveBindAddressExplicitIPOnTailscale(t *testing.T) {
	dir := t.TempDir()
	if err := os.Mkdir(filepath.Join(dir, "tailscale0"), 0o755); err != nil {
		t.Fatalf("mkdir tailscale0: %v", err)
	}

	addrFn := makeStubAddrFn(map[string][]net.IP{
		"tailscale0": {net.ParseIP("100.64.0.1")},
	})

	got, err := ResolveBindAddress("100.64.0.1", nil, dir, addrFn)
	if err != nil {
		t.Fatalf("ResolveBindAddress(100.64.0.1, ...): %v", err)
	}
	if got != "100.64.0.1" {
		t.Errorf("got %q, want %q", got, "100.64.0.1")
	}
}

func TestResolveBindAddressExplicitIPInAllowedSubnets(t *testing.T) {
	dir := t.TempDir() // empty — no tailscale* entries

	addrFn := makeStubAddrFn(nil) // no interfaces have addresses

	got, err := ResolveBindAddress("10.0.0.5", []string{"10.0.0.0/8"}, dir, addrFn)
	if err != nil {
		t.Fatalf("ResolveBindAddress(10.0.0.5, [10.0.0.0/8]): %v", err)
	}
	if got != "10.0.0.5" {
		t.Errorf("got %q, want %q", got, "10.0.0.5")
	}
}

func TestResolveBindAddressExplicitIPRefused(t *testing.T) {
	dir := t.TempDir() // no tailscale* entries

	addrFn := makeStubAddrFn(nil)

	_, err := ResolveBindAddress("10.0.0.5", []string{"192.168.0.0/16"}, dir, addrFn)
	if err == nil {
		t.Errorf("ResolveBindAddress(10.0.0.5, [192.168.0.0/16]) = nil error, want refusal")
	}
}

func TestResolveBindAddressZeroAlwaysRefused(t *testing.T) {
	dir := t.TempDir()
	addrFn := makeStubAddrFn(nil)

	// Even with allowedSubnets containing 0.0.0.0/0, bind=0.0.0.0 must
	// be refused unconditionally.
	_, err := ResolveBindAddress("0.0.0.0", []string{"0.0.0.0/0"}, dir, addrFn)
	if err == nil {
		t.Errorf("ResolveBindAddress(0.0.0.0, [0.0.0.0/0]) = nil error, want refusal")
	}
	if !strings.Contains(err.Error(), "0.0.0.0") {
		t.Errorf("error %q does not name 0.0.0.0", err.Error())
	}
}

func TestResolveBindAddressInvalidIPString(t *testing.T) {
	dir := t.TempDir()
	addrFn := makeStubAddrFn(nil)

	_, err := ResolveBindAddress("not-an-ip", nil, dir, addrFn)
	if err == nil {
		t.Errorf("ResolveBindAddress(not-an-ip) = nil error, want refusal")
	}
}

func TestResolveBindAddressInvalidCIDR(t *testing.T) {
	dir := t.TempDir()
	addrFn := makeStubAddrFn(nil)

	_, err := ResolveBindAddress("10.0.0.5", []string{"not-a-cidr"}, dir, addrFn)
	if err == nil {
		t.Errorf("ResolveBindAddress with bad CIDR entry = nil error, want refusal")
	}
}

// TestResolveBindAddressNilAddrFnUsesDefault documents that
// production callers (main.go) pass nil to trigger DefaultAddrFn. The
// test exercises the nil-branch by passing nil — but DefaultAddrFn
// wraps net.InterfaceByName, which will fail in the test environment
// (no real "auto" iface). We therefore expect an error from the
// auto-detect path, NOT a nil-pointer dereference. The key invariant
// is: passing nil addrFn does NOT crash.
func TestResolveBindAddressNilAddrFnUsesDefault(t *testing.T) {
	dir := t.TempDir() // empty — no tailscale* entries

	// Passing nil for addrFn must NOT crash. Either path is acceptable:
	// (a) error from no-tailscale-iface, or (b) error from DefaultAddrFn.
	_, err := ResolveBindAddress("auto", nil, dir, nil)
	if err == nil {
		t.Errorf("ResolveBindAddress(auto, nil addrFn) = nil error, want some failure (no real tailscale iface)")
	}
}
