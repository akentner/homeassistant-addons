package datasource

import (
	"context"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/datasource/schema"
)

// supervisorInfoDataSource is the stub implementation of the
// homeassistant_supervisor_info data source (PROV-12). Plan 03 fills
// in the schema (bridge_version, supervisor_version, uptime_seconds,
// state_file_path — mirroring /v1/info per CF-11) and the Read body
// (call Client.GetInfo).
type supervisorInfoDataSource struct{}

// NewSupervisorInfoDataSource returns a fresh instance suitable for
// use as a `func() datasource.DataSource` element in the Provider's
// DataSources() slice.
func NewSupervisorInfoDataSource() datasource.DataSource {
	return &supervisorInfoDataSource{}
}

// Metadata returns the data source's type name.
func (d *supervisorInfoDataSource) Metadata(_ context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_supervisor_info"
}

// Schema returns the Plan 01 stub schema (no attributes). Plan 03
// expands this to mirror the contract.BridgeInfo fields so the data
// source can be used inside lifecycle.precondition blocks (PROV-12
// use case per CF-11).
func (d *supervisorInfoDataSource) Schema(_ context.Context, _ datasource.SchemaRequest, resp *datasource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Attributes: map[string]schema.Attribute{},
	}
}

// Read is a no-op stub. Plan 03 wires the real Read (call
// Client.GetInfo) and populates the data source state with the
// bridge_info body.
func (d *supervisorInfoDataSource) Read(ctx context.Context, req datasource.ReadRequest, resp *datasource.ReadResponse) {
	_ = ctx
	_ = req
	_ = resp.State
}
