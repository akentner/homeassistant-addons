// Package datasource holds the Provider's DataSource implementations.
// Plan 01 ships both data sources as thin stubs (PROV-11 +
// PROV-12) — the schemas and Read bodies are filled in by Plan 03.
// The stubs exist in Plan 01 so the Provider's DataSources() method
// can return the expected list of constructors and the
// TestProvider_DataSources_ReturnsBothDataSources test passes.
//
// File layout:
//
//   - homeassistant_addon.go        — stub for the homeassistant_addon
//     data source (PROV-11).
//   - homeassistant_supervisor_info.go — stub for the
//     homeassistant_supervisor_info
//     data source (PROV-12).
package datasource

import (
	"context"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/datasource/schema"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

// addonDataSource is the stub implementation of the
// homeassistant_addon data source (PROV-11). Plan 03 fills in the
// schema (full info payload, same shape as the resource's Computed
// attributes) and Read (call Client.GetAddonInfo by slug).
type addonDataSource struct{}

// NewAddonDataSource returns a fresh instance suitable for use as
// a `func() datasource.DataSource` element in the Provider's
// DataSources() slice.
func NewAddonDataSource() datasource.DataSource {
	return &addonDataSource{}
}

// Metadata returns the data source's type name (the second segment
// of the resource address; e.g. `data "homeassistant_addon"`).
func (d *addonDataSource) Metadata(_ context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_addon"
}

// Schema returns the Plan 01 stub schema (no attributes, no
// blocks). Plan 03 expands this to the full PROV-11 schema with a
// `slug` Required attribute and the full Computed AddOnInfo
// payload.
func (d *addonDataSource) Schema(_ context.Context, _ datasource.SchemaRequest, resp *datasource.SchemaResponse) {
	resp.Schema = schema.Schema{
		// Empty for Plan 01 — Plan 03 declares slug + Computed
		// attributes mirroring the resource.
		Attributes: map[string]schema.Attribute{},
	}
}

// Read is a no-op stub. Plan 03 wires the real Read (lookup by
// slug via Client.GetAddonInfo) and populates the data source state
// from the AddOnInfo payload.
func (d *addonDataSource) Read(ctx context.Context, req datasource.ReadRequest, resp *datasource.ReadResponse) {
	// Plan 01 placeholder — Read on a stub data source with no
	// attributes is a no-op; the framework reports "no schema"
	// diagnostics only when the user actually references
	// `data "homeassistant_addon"` in their *.tf, which Plan 01
	// does not exercise.
	_ = ctx
	_ = req
	_ = resp.State
	// Use types.String to keep an import alive without actually
	// needing it in Plan 01 (avoids a lint warning for unused
	// import after Plan 03 expands the schema).
	_ = types.StringNull
}
