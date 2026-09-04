package resource

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework-timeouts/resource/timeouts"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/schema/validator"
)

// timeoutsBlock returns the per-operation timeouts Block used by
// the homeassistant_addon resource. Plan 02 wires the actual
// timeout-driven behaviour (read the configured create / update /
// delete timeout, surface them in Create / Update / Delete) but
// the schema is declared in Plan 01 so the timeouts block is
// already valid in users' *.tf when Plan 02 lands.
//
// Per CF-03, the defaults documented in DOCS.md are:
//
//	create = 10m, update = 2m, delete = 5m
//
// The Block declares all four operation attributes; each is
// optional so users can omit any of them and fall back to the
// Plan 02 hardcoded defaults. The Block keeps the dep on
// terraform-plugin-framework-timeouts live in `go mod tidy`'s
// view (Plan 02's Create / Update / Delete bodies import the
// package directly).
func timeoutsBlock() schema.Block {
	return timeouts.Block(context.Background(), timeouts.Opts{
		Create: true,
		Read:   true,
		Update: true,
		Delete: true,
	})
}

// stringOneOfValidator is the closed-enum string validator used by
// the `boot` attribute on homeassistant_addon (CF-10). The
// framework's schema/validator package exposes stringvalidator.OneOf
// from a separate module — we replicate it inline to keep the
// dependency surface tight (one use-site). Case-sensitive match;
// null / unknown values pass through (the framework treats those
// as "not yet known" and surfaces them as plan-time unknowns).
type stringOneOfValidator []string

func (v stringOneOfValidator) Description(_ context.Context) string {
	return fmt.Sprintf("value must be one of: %v", []string(v))
}

func (v stringOneOfValidator) MarkdownDescription(ctx context.Context) string {
	return v.Description(ctx)
}

func (v stringOneOfValidator) ValidateString(ctx context.Context, req validator.StringRequest, resp *validator.StringResponse) {
	if req.ConfigValue.IsNull() || req.ConfigValue.IsUnknown() {
		return
	}
	got := req.ConfigValue.ValueString()
	for _, allowed := range v {
		if got == allowed {
			return
		}
	}
	resp.Diagnostics.AddAttributeError(
		req.Path,
		"Invalid boot value",
		fmt.Sprintf("boot must be one of %v, got %q", []string(v), got),
	)
}
