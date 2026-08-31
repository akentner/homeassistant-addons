// Package logging wraps stdlib log/slog with a sensitive-key scrubber
// that masks values for the keys listed in CONTEXT.md D-10 BEFORE the
// inner handler serializes the record. Scrubber is key-name based
// (case-insensitive), not value-substring based.
//
// AUTH-05 invariant: no log record produced through this wrapper
// contains the literal value of any sensitive key. TestScrubbingHandler
// asserts this by feeding crafted records and grepping captured bytes.
package logging

import (
	"context"
	"log/slog"
	"strings"
)

var sensitiveKeys = map[string]struct{}{
	"Authorization":    {},
	"Bearer":           {},
	"bridge_token":     {},
	"SUPERVISOR_TOKEN": {},
	"supervisor_token": {},
	"bearer":           {},
	"token":            {},
	"password":         {},
}

const scrubbedValue = "<redacted>"

type scrubbingHandler struct{ inner slog.Handler }

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

func scrubAttr(a slog.Attr) slog.Attr {
	for k := range sensitiveKeys {
		if strings.EqualFold(a.Key, k) {
			return slog.String(a.Key, scrubbedValue)
		}
	}
	return a
}
