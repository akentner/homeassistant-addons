package runs

import (
	"strings"
	"testing"
)

// r2Key is a Cloudflare R2 access key id shape: 20 uppercase
// alphanumerics (SEC-03).
const r2Key = "A1B2C3D4E5F6G7H8I9J0"

// awsSecret is the canonical AWS documentation secret access key: 40
// characters from the base64-ish alphabet (SEC-03).
const awsSecret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

func TestRedact(t *testing.T) {
	tests := []struct {
		name  string
		line  string
		want  string
		count int
	}{
		{
			name:  "r2 access key alone",
			line:  r2Key,
			want:  redactedMarker,
			count: 1,
		},
		{
			name:  "r2 access key inside a sentence",
			line:  "r2_access_key_id = " + r2Key + " (from options.json)",
			want:  "r2_access_key_id = " + redactedMarker + " (from options.json)",
			count: 1,
		},
		{
			name:  "aws secret access key",
			line:  `AWS_SECRET_ACCESS_KEY="` + awsSecret + `"`,
			want:  `AWS_SECRET_ACCESS_KEY="` + redactedMarker + `"`,
			count: 1,
		},
		{
			name:  "pem header redacts the whole line",
			line:  "-----BEGIN OPENSSH PRIVATE KEY-----",
			want:  redactedMarker,
			count: 1,
		},
		{
			name:  "pem header with leading noise still redacts the whole line",
			line:  `  key = "-----BEGIN RSA PRIVATE KEY-----"`,
			want:  redactedMarker,
			count: 1,
		},
		{
			name:  "ordinary tofu output is untouched",
			line:  "module.storage.cloudflare_r2_bucket.data: Refreshing state... [id=homelab-tfstate]",
			want:  "module.storage.cloudflare_r2_bucket.data: Refreshing state... [id=homelab-tfstate]",
			count: 0,
		},
		{
			name:  "two secrets on one line count twice",
			line:  "key=" + r2Key + " secret=" + awsSecret,
			want:  "key=" + redactedMarker + " secret=" + redactedMarker,
			count: 2,
		},
		{
			name:  "19 char uppercase token is below the r2 boundary",
			line:  strings.Repeat("A", 19),
			want:  strings.Repeat("A", 19),
			count: 0,
		},
		{
			name:  "41 char token is above the aws boundary",
			line:  strings.Repeat("A", 41),
			want:  strings.Repeat("A", 41),
			count: 0,
		},
		{
			name:  "empty line",
			line:  "",
			want:  "",
			count: 0,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, n := Redact(tc.line)
			if got != tc.want {
				t.Errorf("Redact(%q)\n got %q\nwant %q", tc.line, got, tc.want)
			}
			if n != tc.count {
				t.Errorf("Redact(%q) count: got %d want %d", tc.line, n, tc.count)
			}
		})
	}
}

func TestRedactIsLosslessForSecretFreeLines(t *testing.T) {
	lines := []string{
		"Plan: 3 to add, 0 to change, 0 to destroy.",
		`  + bucket = "homelab-tfstate"`,
		"\ttabs\tand   multiple   spaces   preserved",
		"trailing spaces preserved   ",
		"()[]{}:;,'\"=",
	}
	for _, l := range lines {
		got, n := Redact(l)
		if got != l {
			t.Errorf("Redact(%q) mutated a secret-free line: got %q", l, got)
		}
		if n != 0 {
			t.Errorf("Redact(%q) count: got %d want 0", l, n)
		}
	}
}

// r2HexAccessKey / r2HexSecret are the shapes Cloudflare R2 actually
// issues: 32 and 64 lowercase hex characters. Neither matches the two
// AWS patterns, which is how the DEFAULT state backend's credentials
// used to reach the API in the clear (WR-02).
const (
	r2HexAccessKey = "3a1f9c0e7b25d48af6301bc9e2d7845f"
	r2HexSecret    = "9f2c1e4b7a08d35c6e91f4b28d70a5c31e6f9d4b2a87c05e3f1d9b6a48e5d2a7"
)

func TestRedactR2AndURLCredentials(t *testing.T) {
	tests := []struct {
		name  string
		line  string
		want  string
		count int
	}{
		{
			name:  "r2 hex access key id",
			line:  "access_key_id = " + r2HexAccessKey,
			want:  "access_key_id = " + redactedMarker,
			count: 1,
		},
		{
			name:  "r2 hex secret",
			line:  "secret = " + r2HexSecret,
			want:  "secret = " + redactedMarker,
			count: 1,
		},
		{
			name:  "credentials embedded in an https url",
			line:  "endpoint = https://" + r2Key + ":" + awsSecret + "@example.com/bucket",
			want:  "endpoint = https://" + redactedMarker + "@example.com/bucket",
			count: 1,
		},
		{
			name:  "credentials embedded in an ssh url",
			line:  "remote: ssh://deploy:s3cr3t-p4ss@git.example.com/org/repo.git",
			want:  "remote: ssh://" + redactedMarker + "@git.example.com/org/repo.git",
			count: 1,
		},
		{
			name:  "a git remote with no password is not a credential",
			line:  "Cloning into ssh://git@github.com/akentner/homelab-infra.git",
			want:  "Cloning into ssh://git@github.com/akentner/homelab-infra.git",
			count: 0,
		},
		{
			// PRE-EXISTING and unchanged by the R2 patterns: a 40-char
			// git SHA is 40 characters of the base64-ish alphabet, so
			// SC-10's AWS-secret pattern has always masked it. Pinned
			// here so the behaviour is a decision rather than a
			// surprise; the raw log under /data still has the SHA.
			name:  "a 40 char hex git sha is masked by the aws secret pattern",
			line:  "HEAD is now at 0f1e2d3c4b5a69788796a5b4c3d2e1f009182736",
			want:  "HEAD is now at " + redactedMarker,
			count: 1,
		},
		{
			name:  "uppercase hex of r2 length is not an r2 key",
			line:  strings.ToUpper(r2HexAccessKey),
			want:  strings.ToUpper(r2HexAccessKey),
			count: 0,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, n := Redact(tc.line)
			if got != tc.want {
				t.Errorf("Redact(%q)\n got %q\nwant %q", tc.line, got, tc.want)
			}
			if n != tc.count {
				t.Errorf("Redact(%q) count: got %d want %d", tc.line, n, tc.count)
			}
		})
	}
}
