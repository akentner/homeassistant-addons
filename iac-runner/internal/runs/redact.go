package runs

// SEC-03 / CONTEXT D-08: credential-pattern redaction of captured tofu
// output.
//
// This is the sibling — not the replacement — of the SEC-02 scrubbing
// handler in internal/logging. That handler masks log ATTRIBUTE VALUES
// by attribute NAME (it knows "token" is sensitive because of the key).
// Here there are no keys: the input is an opaque line of process
// output, so the decision has to be made from the VALUE's shape. Both
// mechanisms must exist; neither covers the other's case.

import (
	"regexp"
	"strings"
)

// redactedMarker is the replacement for every redacted token. Same
// spelling as internal/logging's SEC-02 handler so an operator sees one
// consistent marker in logs and in API responses.
const redactedMarker = "<redacted>"

// SEC-03 patterns. They are anchored on purpose: REQUIREMENTS.md
// specifies the ^…$ forms, so matching is per whitespace/delimiter-
// separated TOKEN rather than per substring. That keeps ordinary tofu
// output (resource addresses, plan diffs, ids) untouched while still
// catching a credential that leaked into a log line.
var (
	// r2AccessKeyRe matches a Cloudflare R2 access key id.
	r2AccessKeyRe = regexp.MustCompile(`^[A-Z0-9]{20}$`)
	// awsSecretKeyRe matches an AWS-style secret access key.
	awsSecretKeyRe = regexp.MustCompile(`^[A-Za-z0-9/+=]{40}$`)
)

// pemHeaderPrefix triggers whole-line redaction: a PEM header means the
// following bytes are key material, and a partially-redacted private
// key is still a leak.
const pemHeaderPrefix = "-----BEGIN"

// tokenDelimiters are the characters that end a token. They are the
// punctuation tofu and shell-style output put around values —
// `key = "VALUE"`, `[id=VALUE]`, `{VALUE, VALUE}` — so a credential
// embedded in any of those shapes is still isolated as its own token.
//
// '=' is included even though it is a member of the AWS secret-key
// character class: `AWS_SECRET_ACCESS_KEY=<key>` is by far the more
// common shape, and splitting there is what exposes the key as a
// token. A key carrying base64 padding is handled by re-testing a
// token together with its trailing '=' run (see Redact).
const tokenDelimiters = " \t\"'=,()[]{}:;"

// Redact returns the line with credential-shaped tokens replaced and
// the number of replacements made. It is applied at READ time
// (CONTEXT D-08): /data/runs/{id}/output.log keeps the raw bytes so an
// operator can debug with `cat … | jq`, while nothing credential-shaped
// crosses the API boundary.
//
// The caller is expected to surface the returned count in the
// `redaction.audit` slog record required by SEC-03. This package does
// no logging of its own — the HTTP handler owns the request-scoped
// logger.
//
// Reassembly is lossless: a line with no credential-shaped token is
// returned byte-identical, delimiters and runs of whitespace included.
func Redact(line string) (string, int) {
	// A PEM header means everything around it is key material. There
	// is no safe partial redaction of a private key, so the line goes
	// as a whole.
	if strings.Contains(line, pemHeaderPrefix) {
		return redactedMarker, 1
	}

	segs := splitTokens(line)
	count := 0
	var b strings.Builder
	b.Grow(len(line))

	for i := 0; i < len(segs); i++ {
		seg := segs[i]
		if seg.delim {
			b.WriteString(seg.text)
			continue
		}
		// A base64-padded secret keeps its '=' run, which the
		// tokenizer split off as a delimiter. Re-test the token with
		// that run attached before falling back to the bare token.
		if i+1 < len(segs) && segs[i+1].delim && isEqualsRun(segs[i+1].text) {
			if awsSecretKeyRe.MatchString(seg.text + segs[i+1].text) {
				b.WriteString(redactedMarker)
				count++
				i++ // the '=' run is part of the redacted value
				continue
			}
		}
		if r2AccessKeyRe.MatchString(seg.text) || awsSecretKeyRe.MatchString(seg.text) {
			b.WriteString(redactedMarker)
			count++
			continue
		}
		b.WriteString(seg.text)
	}
	return b.String(), count
}

// segment is one run of the input: either a delimiter run or a token.
type segment struct {
	text  string
	delim bool
}

// splitTokens walks line once and returns alternating delimiter and
// token runs. Concatenating every segment's text reproduces line
// exactly — that is what makes Redact lossless for secret-free input.
func splitTokens(line string) []segment {
	var segs []segment
	start := 0
	inDelim := false
	if len(line) > 0 {
		inDelim = strings.IndexByte(tokenDelimiters, line[0]) >= 0
	}
	for i := 0; i < len(line); i++ {
		isDelim := strings.IndexByte(tokenDelimiters, line[i]) >= 0
		if isDelim != inDelim {
			segs = append(segs, segment{text: line[start:i], delim: inDelim})
			start = i
			inDelim = isDelim
		}
	}
	if start < len(line) {
		segs = append(segs, segment{text: line[start:], delim: inDelim})
	}
	return segs
}

// isEqualsRun reports whether s consists only of '=' characters.
func isEqualsRun(s string) bool {
	if s == "" {
		return false
	}
	return strings.Trim(s, "=") == ""
}
