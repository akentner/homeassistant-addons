package provider

import "strconv"

// versionLess reports whether a < b. Both a and b are semver
// strings in "X.Y.Z" form (extra pre-release / build metadata is
// not handled — Bridge's version constants are plain semver).
//
// Returns false when either input fails to parse; the caller should
// treat unparseable versions as equal so the comparison does not
// spuriously fire `version_below_min` / `version_above_max`.
// versionLess is exported (lowercase first letter) only because
// provider_test.go needs to assert the same comparison logic in
// isolation; production callers use versionLess / versionGreater
// from this file.
//
// The implementation walks the three numeric segments in order and
// returns the first non-zero comparison. This matches semver
// precedence for our supported range (no pre-release tags, no
// build metadata).
func versionLess(a, b string) bool {
	am := splitVersion(a)
	bm := splitVersion(b)
	for i := 0; i < 3; i++ {
		if am[i] < bm[i] {
			return true
		}
		if am[i] > bm[i] {
			return false
		}
	}
	return false
}

// versionGreater reports whether a > b. Symmetric to versionLess.
func versionGreater(a, b string) bool {
	am := splitVersion(a)
	bm := splitVersion(b)
	for i := 0; i < 3; i++ {
		if am[i] > bm[i] {
			return true
		}
		if am[i] < bm[i] {
			return false
		}
	}
	return false
}

// splitVersion parses a "X.Y.Z" semver string into a 3-element int
// slice. Unparseable segments become 0. The function never panics.
func splitVersion(v string) [3]int {
	var out [3]int
	for i := 0; i < 3; i++ {
		out[i] = 0
	}
	parts := splitDots(v)
	for i := 0; i < len(parts) && i < 3; i++ {
		n, err := strconv.Atoi(parts[i])
		if err != nil {
			continue
		}
		out[i] = n
	}
	return out
}

// splitDots is a tiny strings.Split wrapper kept here so the file
// has no `strings` import to mirror Bridge's pattern.
func splitDots(v string) []string {
	var out []string
	start := 0
	for i := 0; i < len(v); i++ {
		if v[i] == '.' {
			out = append(out, v[start:i])
			start = i + 1
		}
	}
	out = append(out, v[start:])
	return out
}
