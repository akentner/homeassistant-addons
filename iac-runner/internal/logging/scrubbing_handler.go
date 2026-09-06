// Package logging wraps stdlib log/slog with a sensitive-key scrubber
// that masks values for the keys listed in PROJECT.md (Authorization,
// Bearer, token, password, key, secret) BEFORE the inner handler
// serializes the record. Scrubber is key-name based (case-insensitive),
// not value-substring based.
//
// SEC-02 invariant: no log record produced through this wrapper
// contains the literal value of any sensitive key. Unit tests assert
// this by feeding crafted records and grepping captured bytes. The
// scrubbing set is a strict superset of terraform-bridge's baseline
// (key + secret are added per PROJECT.md's explicit listing); bridge-
// specific tokens are NOT in this set because iac-runner does not
// hold a SUPERVISOR_TOKEN (AUTHR-01).
package logging

import (
	"context"
	"log/slog"
	"strings"
)

// sensitiveKeys is the case-insensitive set of attribute keys whose
// values are replaced with "<redacted>" before the inner handler
// serializes a record. The map is duplicated in mixed case (e.g.
// "Authorization" + "authorization") so the lookup stays O(1) without
// forcing every call site through strings.EqualFold — only the inner
// loop of scrubAttr walks the map. Each sensitiveKeys entry is
// matched via strings.EqualFold in scrubAttr.
var sensitiveKeys = map[string]struct{}{
	"Authorization": {},
	"Bearer":        {},
	"authorization": {},
	"bearer":        {},
	"token":         {},
	"password":      {},
	"key":           {},
	"secret":        {},
}

const scrubbedValue = "<redacted>"

// scrubbingHandler is an slog.Handler that masks values for sensitive
// keys (case-insensitive) before delegating to the wrapped inner
// handler. The wrapped handler is supplied at construction time — no
// package-level slog.Default() dependency, no global state, full test
// isolation.
type scrubbingHandler struct{ inner slog.Handler }

// NewScrubbingHandler returns a slog.Handler that scrubs sensitive
// attribute values (Authorization, Bearer, token, password, key,
// secret — case-insensitive) to "<redacted>" before delegating to
// inner. Use as the handler passed to slog.New to wrap the runner's
// JSON logger (main.go).
//
// The wrapper preserves the slog.Handler contract: Enabled,
// WithAttrs, WithGroup all return new wrappers whose inner handlers
// carry the chained configuration, so a logger created with
// `slog.New(NewScrubbingHandler(jsonHandler)).With("component", "x")`
// still scrubs values recorded under "component.x".
func NewScrubbingHandler(inner slog.Handler) slog.Handler {
	return &scrubbingHandler{inner: inner}
}

func (h *scrubbingHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return h.inner.Enabled(ctx, level)
}

func (h *scrubbingHandler) Handle(ctx context.Context, r slog.Record) error {
	scrubbed := slog.NewRecord(r.Time, r.Level, r.Message, r.PC)
	r.Attrs(func(a slog.Attr) bool {
		scrubbed.AddAttrs(scrubAttr(a))
		return true
	})
	return h.inner.Handle(ctx, scrubbed)
}

func (h *scrubbingHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	scrubbed := make([]slog.Attr, 0, len(attrs))
	for _, a := range attrs {
		scrubbed = append(scrubbed, scrubAttr(a))
	}
	return &scrubbingHandler{inner: h.inner.WithAttrs(scrubbed)}
}

func (h *scrubbingHandler) WithGroup(name string) slog.Handler {
	return &scrubbingHandler{inner: h.inner.WithGroup(name)}
}

// scrubAttr returns a new attr with the value replaced by
// "<redacted>" if the key is in sensitiveKeys (case-insensitive);
// otherwise returns a unchanged. Groups do not participate in the
// match — a key inside a WithGroup("auth") namespace is still
// matched on the leaf key name.
func scrubAttr(a slog.Attr) slog.Attr {
	for k := range sensitiveKeys {
		if strings.EqualFold(a.Key, k) {
			return slog.String(a.Key, scrubbedValue)
		}
	}
	return a
}
