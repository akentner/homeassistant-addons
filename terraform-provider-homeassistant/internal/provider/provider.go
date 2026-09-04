// Package provider holds the terraform-provider-homeassistant
// Provider implementation (PROV-01). The Provider wires:
//
//   - The Metadata / Schema / Configure / Resources / DataSources
//     surface that terraform-plugin-framework v1.19.0 calls into
//     during the gRPC handshake.
//   - An internal/client.Client constructed from the user's
//     `endpoint` + `bearer_token` Provider arguments, then handed
//     to every Resource and DataSource via Configure on the
//     resource side (per the framework idiom).
//
// Per CF-01..CF-03, the Provider:
//
//   - Serves via providerserver.Serve at
//     `registry.terraform.io/akentner/homeassistant` (the address
//     is fixed in main.go's providerserver.ServeOpts).
//   - Uses the modern (terraform-plugin-framework) interface — NOT
//     the SDKv2 provider.PluginServer.
//   - Marks `bearer_token` Sensitive: true so Terraform hides it
//     from plan output (CF-03 + PITFALLS S-1).
//   - Performs the GET /v1/version handshake in Configure and
//     refuses to operate when the Provider's version falls outside
//     the Bridge's [min_provider_version, max_provider_version]
//     window (PROV-03 + CF-02).
//
// File layout (Plan 01 deliverable):
//
//   - provider.go (this file) — Provider type + all five Provider
//     interface methods + Version constant.
//   - provider_test.go — unit tests covering Metadata, Schema,
//     Configure (success + version out-of-window), Resources,
//     DataSources.
//
// The Resource and DataSource bodies live in internal/resource/ and
// internal/datasource/ respectively (see those packages for the
// per-implementation detail).
package provider

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/provider/schema"
	fwresource "github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"terraform-provider-homeassistant/internal/client"
	datasrc "terraform-provider-homeassistant/internal/datasource"
	"terraform-provider-homeassistant/internal/diagnostics"
	"terraform-provider-homeassistant/internal/resource"
)

// Version is the Provider's semver string. Phase 9 shipped it as a
// `0.0.0` stub; Phase 14 wires the 3-file versioning sync (CF-14)
// so this constant tracks the same version as Bridge's
// build.yaml. The Provider's Configure compares this against the
// Bridge's [min_provider_version, max_provider_version] window per
// PROV-03.
const Version = "0.0.0"

// New constructs a fresh Provider with the configured version. The
// constructor is package-level (not a method on Provider) so
// main.go's newProvider() can return `provider.Provider` without
// exposing Provider itself.
func New() *Provider {
	return &Provider{version: Version}
}

// Provider implements provider.Provider (PROV-01).
type Provider struct {
	version string
}

// Compile-time check that Provider implements provider.Provider.
var _ provider.Provider = &Provider{}

// Metadata returns the type name + version pair. The type name
// (`homeassistant`) becomes the first segment of every resource /
// data source address (`homeassistant_addon`,
// `homeassistant_supervisor_info`).
func (p *Provider) Metadata(_ context.Context, _ provider.MetadataRequest, resp *provider.MetadataResponse) {
	resp.TypeName = "homeassistant"
	resp.Version = p.version
}

// Schema declares the Provider's two required arguments:
//
//   - endpoint: the Bridge's base URL (e.g. `http://homeassistant:8124`).
//   - bearer_token: the Bridge-issued bearer token. Marked Sensitive
//     so Terraform hides it from plan output and CLI logs (CF-03 +
//     PITFALLS S-1).
//
// Both are Required — Configure relies on the framework's
// precondition check before invoking our code, so a missing value
// surfaces as a framework-generated Error before any network call
// is made.
func (p *Provider) Schema(_ context.Context, _ provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = schema.Schema{
		Attributes: map[string]schema.Attribute{
			"endpoint": schema.StringAttribute{
				Required:    true,
				Description: "Base URL of the terraform-bridge HTTP API (e.g. http://homeassistant:8124).",
			},
			"bearer_token": schema.StringAttribute{
				Required:    true,
				Sensitive:   true,
				Description: "Bearer token matching the Bridge's current /data/bridge-token hash. Sensitive — never echoed in plan output.",
			},
		},
	}
}

// Configure is called once per Provider lifecycle. It:
//
//  1. Reads the endpoint + bearer_token arguments out of req.Config.
//  2. Constructs a *client.Client via client.NewClient.
//  3. Calls client.GetVersion(ctx) to perform the PROV-03 handshake.
//  4. Verifies the Provider's Version lies within the Bridge's
//     [min_provider_version, max_provider_version] window. An
//     out-of-window Provider returns a typed Error diagnostic per
//     D-08 + D-11.
//  5. On success stashes the configured Client in BOTH
//     resp.ResourceData and resp.DataSourceData so every Resource
//     and DataSource can retrieve it via their own Configure
//     callback (the framework keeps the two handoff channels
//     separate).
//
// Failure paths return Error-severity Diagnostics; success leaves
// resp.Diagnostics empty and resp.ClientData populated.
func (p *Provider) Configure(ctx context.Context, req provider.ConfigureRequest, resp *provider.ConfigureResponse) {
	var data providerData
	resp.Diagnostics.Append(req.Config.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	endpoint := data.Endpoint.ValueString()
	bearerToken := data.BearerToken.ValueString()

	c, err := client.NewClient(endpoint, bearerToken)
	if err != nil {
		resp.Diagnostics.AddError(
			"Bridge client construction failed",
			err.Error(),
		)
		return
	}

	hs, err := c.GetVersion(ctx)
	if err != nil {
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	// PROV-03 + CF-02: refuse to operate when the version
	// negotiation fails. Two checks cover the two failure modes:
	//
	//   1. Provider.version < Bridge.min_provider_version
	//      → Provider is too old for this Bridge. The error is
	//      typed "version_below_min".
	//
	//   2. Bridge.schema_version > Bridge.max_provider_version
	//      → Bridge is too new for this Provider. The error is
	//      typed "version_above_max".
	//
	// The second check uses the Bridge-reported schema_version
	// because the Bridge knows its own API surface; the Provider
	// only knows its own version. The combination protects both
	// ends of the negotiation: a Provider that predates the
	// Bridge's minimum, and a Bridge whose schema predates the
	// Provider's supported maximum.
	if versionLess(p.version, hs.MinProviderVersion) {
		resp.Diagnostics.AddError(
			fmt.Sprintf("Bridge reports this Provider is too old: provider version %s is below the Bridge's min_provider_version %s",
				p.version, hs.MinProviderVersion),
			fmt.Sprintf("DOCS.md#troubleshooting-version\nbridge_schema_version: %s\nbridge_min_provider_version: %s\nbridge_max_provider_version: %s",
				hs.SchemaVersion, hs.MinProviderVersion, hs.MaxProviderVersion),
		)
		return
	}
	if versionGreater(hs.SchemaVersion, hs.MaxProviderVersion) {
		resp.Diagnostics.AddError(
			fmt.Sprintf("Bridge reports a schema version this Provider does not support: bridge schema_version %s is above the Bridge's max_provider_version %s",
				hs.SchemaVersion, hs.MaxProviderVersion),
			fmt.Sprintf("DOCS.md#troubleshooting-version\nbridge_schema_version: %s\nbridge_min_provider_version: %s\nbridge_max_provider_version: %s",
				hs.SchemaVersion, hs.MinProviderVersion, hs.MaxProviderVersion),
		)
		return
	}

	// The framework hands ResourceData to every Resource's
	// Configure and DataSourceData to every DataSource's Configure
	// — they are two separate channels, so both must be populated
	// or the data sources added in Plan 03 receive a nil
	// ProviderData and can never reach the Bridge.
	resp.ResourceData = c
	resp.DataSourceData = c
}

// Resources returns the slice of Resource constructors the Provider
// exposes. Plan 01 ships exactly one resource (`homeassistant_addon`,
// PROV-02 with the minimum-viable schema); Plan 02 expands the
// schema with the full PROV-02 attribute set + Create / Update /
// Delete bodies.
func (p *Provider) Resources(_ context.Context) []func() fwresource.Resource {
	return []func() fwresource.Resource{
		func() fwresource.Resource { return resource.NewAddonResource() },
	}
}

// DataSources returns the slice of DataSource constructors the
// Provider exposes: `homeassistant_addon` (PROV-11) and
// `homeassistant_supervisor_info` (PROV-12). Plan 01 shipped both as
// thin stubs; Plan 03 fills in the schemas + Read bodies.
func (p *Provider) DataSources(_ context.Context) []func() datasource.DataSource {
	return []func() datasource.DataSource{
		func() datasource.DataSource { return datasrc.NewAddonDataSource() },
		func() datasource.DataSource { return datasrc.NewSupervisorInfoDataSource() },
	}
}

// providerData is the typed view of the Provider's Schema attributes
// that Configure reads out of req.Config. Field names match the
// schema attribute names exactly (Go's struct tags would be
// redundant since the framework uses field names by convention).
type providerData struct {
	Endpoint    types.String `tfsdk:"endpoint"`
	BearerToken types.String `tfsdk:"bearer_token"`
}
