package resource

import (
	"context"

	"github.com/hashicorp/terraform-plugin-framework-timeouts/resource/timeouts"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
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
