package runs

// RED-phase stub for SEC-03 read-time redaction.

// redactedMarker is the replacement for every redacted token.
const redactedMarker = "<redacted>"

// Redact returns the line with credential-shaped tokens replaced and
// the number of replacements made.
func Redact(line string) (string, int) { return line, 0 }
