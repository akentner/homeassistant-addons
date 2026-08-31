package auth

import (
	"errors"
	"fmt"
	"net"
	"path/filepath"
	"strings"
)

// ResolveBindAddress decides which interface IP the Bridge should
// listen on. The decision tree (D-04..D-06):
//
//   bindAddress == "auto"           -> first Tailscale IP found in /sys/class/net
//   bindAddress == "0.0.0.0"        -> ALWAYS refused (regardless of allowedSubnets)
//   bindAddress == <explicit IP>    -> accepted only if on a Tailscale iface
//                                       OR inside one of allowedSubnets
//
// On refusal (no Tailscale iface for "auto", refused IP, 0.0.0.0,
// invalid IP, etc.) the function returns an error and main.go exits
// with status 1 — no degraded mode (AGENTS.md "Live Systems" rule).
//
// The function takes the `sysClassNet` root as a parameter so tests
// can inject a fixture directory; production calls pass the
// constant "/sys/class/net".
func ResolveBindAddress(bindAddress string, allowedSubnets []string, sysClassNet string) (string, error) {
	if bindAddress == "0.0.0.0" {
		return "", errors.New(
			"auth: bind_address=0.0.0.0 is always refused (PITFALLS S-4); use bind_allowed_subnets to enumerate explicit subnets",
		)
	}

	if bindAddress == "auto" || bindAddress == "" {
		ip, err := firstTailscaleIP(sysClassNet)
		if err != nil {
			return "", fmt.Errorf("auth: auto-detect Tailscale interface: %w", err)
		}
		return ip, nil
	}

	// Explicit IP path.
	ip := net.ParseIP(bindAddress)
	if ip == nil {
		return "", fmt.Errorf("auth: bind_address %q is not a valid IP", bindAddress)
	}

	// Check Tailscale membership first.
	if onTailscaleInterface(ip, sysClassNet) {
		return ip.String(), nil
	}

	// Then check allowed_subnets.
	for _, cidr := range allowedSubnets {
		_, n, err := net.ParseCIDR(cidr)
		if err != nil {
			return "", fmt.Errorf("auth: bind_allowed_subnets entry %q is not valid CIDR: %w", cidr, err)
		}
		if n.Contains(ip) {
			return ip.String(), nil
		}
	}

	return "", fmt.Errorf(
		"auth: bind_address %s is not on any Tailscale interface and not in bind_allowed_subnets",
		ip,
	)
}

// firstTailscaleIP globs /sys/class/net for entries whose name starts
// with "tailscale" and returns the first IPv4 address it finds via
// that interface's address list.
func firstTailscaleIP(sysClassNet string) (string, error) {
	matches, err := filepath.Glob(filepath.Join(sysClassNet, "tailscale*"))
	if err != nil {
		return "", err
	}
	if len(matches) == 0 {
		return "", errors.New("no tailscale* interface found in /sys/class/net")
	}
	ifaceName := filepath.Base(matches[0])

	iface, err := net.InterfaceByName(ifaceName)
	if err != nil {
		return "", fmt.Errorf("lookup interface %s: %w", ifaceName, err)
	}
	addrs, err := iface.Addrs()
	if err != nil {
		return "", fmt.Errorf("interface %s addresses: %w", ifaceName, err)
	}
	for _, addr := range addrs {
		var ip net.IP
		switch v := addr.(type) {
		case *net.IPNet:
			ip = v.IP
		case *net.IPAddr:
			ip = v.IP
		}
		if ip == nil {
			continue
		}
		if ip4 := ip.To4(); ip4 != nil {
			return ip4.String(), nil
		}
	}
	return "", fmt.Errorf("tailscale interface %s has no IPv4 address", ifaceName)
}

// onTailscaleInterface returns true if ip is bound to a tailscale*
// interface. Used by the explicit-IP branch above.
func onTailscaleInterface(ip net.IP, sysClassNet string) bool {
	matches, err := filepath.Glob(filepath.Join(sysClassNet, "tailscale*"))
	if err != nil {
		return false
	}
	for _, m := range matches {
		ifaceName := filepath.Base(m)
		iface, err := net.InterfaceByName(ifaceName)
		if err != nil {
			continue
		}
		addrs, _ := iface.Addrs()
		for _, addr := range addrs {
			var a net.IP
			switch v := addr.(type) {
			case *net.IPNet:
				a = v.IP
			case *net.IPAddr:
				a = v.IP
			}
			if a == nil {
				continue
			}
			if a.Equal(ip) {
				return true
			}
		}
	}
	return false
}

// ensure strings is referenced; the import is kept for the natural
// future use of strings.HasPrefix / strings.HasSuffix on interface
// names. The linter would otherwise flag it as unused.
var _ = strings.HasPrefix
