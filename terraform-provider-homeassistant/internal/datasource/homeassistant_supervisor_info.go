package datasource

import (
	"context"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/datasource/schema"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"terraform-provider-homeassistant/internal/client"
	"terraform-provider-homeassistant/internal/diagnostics"
)

// supervisorInfoDataSourceModel is the typed view of the
// homeassistant_supervisor_info data source schema. The body shape
// mirrors contract.BridgeInfo exactly per CF-11 so the data source
// is drop-in usable inside `lifecycle.precondition` blocks
// (PROV-12).
type supervisorInfoDataSourceModel struct {
	BridgeVersion     types.String `tfsdk:"bridge_version"`
	SupervisorVersion types.String `tfsdk:"supervisor_version"`
	UptimeSeconds     types.Int64  `tfsdk:"uptime_seconds"`
	StateFilePath     types.String `tfsdk:"state_file_path"`
}

// supervisorInfoDataSource implements the
// homeassistant_supervisor_info data source (PROV-12). The data
// source takes no arguments — it is a single read of the Bridge's
// GET /v1/info endpoint.
type supervisorInfoDataSource struct {
	client *client.Client
}

// NewSupervisorInfoDataSource returns a fresh instance suitable for
// use as a `func() datasource.DataSource` element in the Provider's
// DataSources() slice.
func NewSupervisorInfoDataSource() datasource.DataSource {
	return &supervisorInfoDataSource{}
}

// Compile-time assertions that supervisorInfoDataSource satisfies
// the framework's DataSource interface and the Configure extension.
var (
	_ datasource.DataSource              = (*supervisorInfoDataSource)(nil)
	_ datasource.DataSourceWithConfigure = (*supervisorInfoDataSource)(nil)
)

// Metadata returns the data source's type name.
func (d *supervisorInfoDataSource) Metadata(_ context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_supervisor_info"
}

// Schema declares zero Required attributes (the data source takes
// no arguments) and the four Computed attributes mirroring
// contract.BridgeInfo per CF-11. `uptime_seconds` is Int64 so
// Terraform parses it without coercion inside
// `lifecycle.precondition` comparisons.
func (d *supervisorInfoDataSource) Schema(_ context.Context, _ datasource.SchemaRequest, resp *datasource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Reads the Bridge's GET /v1/info endpoint. Takes no arguments. Intended for use in lifecycle.precondition blocks to assert Bridge/Supervisor versions before an apply proceeds (PROV-12).",
		Attributes: map[string]schema.Attribute{
			"bridge_version": schema.StringAttribute{
				Computed:    true,
				Description: "Version of the terraform-bridge add-on serving this endpoint.",
			},
			"supervisor_version": schema.StringAttribute{
				Computed:    true,
				Description: "Version of the Home Assistant Supervisor the Bridge is talking to.",
			},
			"uptime_seconds": schema.Int64Attribute{
				Computed:    true,
				Description: "Seconds since the Bridge process started.",
			},
			"state_file_path": schema.StringAttribute{
				Computed:    true,
				Description: "Absolute path of the Bridge's OpenTofu state file on the Home Assistant host (Phase 1: /data/terraform.tfstate).",
			},
		},
	}
}

// Configure pulls the *client.Client out of the Provider's
// ConfigureResponse.DataSourceData. See the addonDataSource
// Configure doc comment for the nil-ProviderData rationale.
func (d *supervisorInfoDataSource) Configure(_ context.Context, req datasource.ConfigureRequest, resp *datasource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}
	c, ok := req.ProviderData.(*client.Client)
	if !ok {
		resp.Diagnostics.AddError(
			"Provider configured with the wrong client type",
			"The homeassistant provider's ConfigureResponse.DataSourceData is not a *client.Client; this is always an internal error.",
		)
		return
	}
	d.client = c
}

// Read calls Client.GetInfo and populates the four Computed
// attributes. Any Bridge error surfaces through
// diagnostics.MapError so the Summary text, request_id, and
// DOCS.md anchor match the rest of the Provider (CF-13 +
// D-08..D-11). There is no 404 branch — GET /v1/info always
// exists when the Bridge is reachable.
func (d *supervisorInfoDataSource) Read(ctx context.Context, _ datasource.ReadRequest, resp *datasource.ReadResponse) {
	if d.client == nil {
		resp.Diagnostics.AddError(
			"Provider not configured",
			"Cannot read data.homeassistant_supervisor_info: the provider has not been configured with a *client.Client.",
		)
		return
	}

	info, err := d.client.GetInfo(ctx)
	if err != nil {
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	state := supervisorInfoDataSourceModel{
		BridgeVersion:     types.StringValue(info.BridgeVersion),
		SupervisorVersion: types.StringValue(info.SupervisorVersion),
		UptimeSeconds:     types.Int64Value(info.UptimeSeconds),
		StateFilePath:     types.StringValue(info.StateFilePath),
	}
	resp.Diagnostics.Append(resp.State.Set(ctx, &state)...)
}
