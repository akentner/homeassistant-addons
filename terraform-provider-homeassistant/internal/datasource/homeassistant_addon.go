// Package datasource holds the Provider's DataSource implementations.
// Plan 01 shipped both data sources as thin stubs (PROV-11 +
// PROV-12); Plan 03 fills in the schemas and the Read bodies against
// the Bridge read endpoints that Phases 11+12 already expose.
//
// File layout:
//
//   - homeassistant_addon.go           — the homeassistant_addon data
//     source (PROV-11): read-only lookup by
//     slug against GET /v1/addons/{slug}/info.
//   - homeassistant_supervisor_info.go — the homeassistant_supervisor_info
//     data source (PROV-12): read-only
//     single read of GET /v1/info.
//
// Both data sources obtain their *client.Client through the
// framework's Configure handoff: Provider.Configure stashes the
// configured Client on ConfigureResponse.DataSourceData, and the
// framework hands it to each data source as
// datasource.ConfigureRequest.ProviderData.
//
// Error surfacing follows CF-13 + D-08..D-11: every Bridge error is
// translated through diagnostics.MapError so the Summary text, the
// `request_id` correlation, and the DOCS.md troubleshooting anchor
// are identical to the Resource's diagnostics. The 404 branch is the
// one deliberate exception — the Client translates 404 into the
// ErrAddonNotFound sentinel (no BridgeError to map), so the data
// source constructs the diagnostic directly from doc.ErrNotFoundText.
//
// Unlike the Resource, a missing add-on is an ERROR for the data
// source: a data source is a read-time assertion that something
// exists (the CF-06 "404 → empty state" idempotency rule exists so
// `terraform destroy` can be a no-op, which has no data-source
// analogue).
package datasource

import (
	"context"
	"errors"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/datasource/schema"
	"github.com/hashicorp/terraform-plugin-framework/diag"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"terraform-provider-homeassistant/internal/client"
	"terraform-provider-homeassistant/internal/diagnostics"
)

// addonDataSourceModel is the typed view of the homeassistant_addon
// data source schema. `slug` is the single Required argument; every
// other field is Computed and mirrors the (Plan 03-extended)
// contract.AddOnInfo shape per CF-11 + D-01.
type addonDataSourceModel struct {
	Slug         types.String            `tfsdk:"slug"`
	Name         types.String            `tfsdk:"name"`
	Version      types.String            `tfsdk:"version"`
	State        types.String            `tfsdk:"state"`
	Started      types.Bool              `tfsdk:"started"`
	Options      map[string]types.String `tfsdk:"options"`
	Boot         types.String            `tfsdk:"boot"`
	Repository   types.String            `tfsdk:"repository"`
	Hostname     types.String            `tfsdk:"hostname"`
	DNS          types.List              `tfsdk:"dns"`
	IngressURL   types.String            `tfsdk:"ingress_url"`
	IngressEntry types.String            `tfsdk:"ingress_entry"`
	WebUIURL     types.String            `tfsdk:"webui_url"`
}

// addonDataSource implements the homeassistant_addon data source
// (PROV-11). The struct holds the configured *client.Client stashed
// by Configure; the framework calls Configure before every Read, so
// the Client is always current.
type addonDataSource struct {
	client *client.Client
}

// NewAddonDataSource returns a fresh instance suitable for use as
// a `func() datasource.DataSource` element in the Provider's
// DataSources() slice.
func NewAddonDataSource() datasource.DataSource {
	return &addonDataSource{}
}

// Compile-time assertions that addonDataSource satisfies the
// framework's DataSource interface and the Configure extension.
var (
	_ datasource.DataSource              = (*addonDataSource)(nil)
	_ datasource.DataSourceWithConfigure = (*addonDataSource)(nil)
)

// Metadata returns the data source's type name (the second segment
// of the data source address; e.g. `data "homeassistant_addon"`).
func (d *addonDataSource) Metadata(_ context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_addon"
}

// Schema declares the PROV-11 surface: `slug` Required, everything
// else Computed. The Computed set mirrors contract.AddOnInfo one
// field per attribute (CF-11: the data source returns the full info
// payload), including the five D-01 fields.
func (d *addonDataSource) Schema(_ context.Context, _ datasource.SchemaRequest, resp *datasource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Reads a single Home Assistant add-on by slug via the Bridge's GET /v1/addons/{slug}/info endpoint. Read-only: use this to reference an add-on's attributes without managing its lifecycle (PROV-11).",
		Attributes: map[string]schema.Attribute{
			"slug": schema.StringAttribute{
				Required:    true,
				Description: "Add-on slug to look up (e.g. 'a0d7b6b6_my_addon').",
			},
			"name": schema.StringAttribute{
				Computed:    true,
				Description: "Human-readable add-on name reported by Supervisor.",
			},
			"version": schema.StringAttribute{
				Computed:    true,
				Description: "Currently-installed add-on version.",
			},
			"state": schema.StringAttribute{
				Computed:    true,
				Description: "Current Supervisor-reported state (e.g. 'started', 'stopped').",
			},
			"started": schema.BoolAttribute{
				Computed:    true,
				Description: "Whether the add-on is currently running.",
			},
			"options": schema.MapAttribute{
				Computed:    true,
				ElementType: types.StringType,
				Description: "Add-on options currently applied at the Supervisor (flat string map).",
			},
			"boot": schema.StringAttribute{
				Computed:    true,
				Description: "Boot mode reported by Supervisor: 'auto', 'manual', or 'manual_only'.",
			},
			"repository": schema.StringAttribute{
				Computed:    true,
				Description: "Repository the add-on was installed from (e.g. 'core').",
			},
			"hostname": schema.StringAttribute{
				Computed:    true,
				Description: "Supervisor-reported hostname for the add-on (D-01). Empty when Supervisor does not set it.",
			},
			"dns": schema.ListAttribute{
				Computed:    true,
				ElementType: types.StringType,
				Description: "Supervisor-reported DNS names for the add-on container (D-01). Null when Supervisor omits the field.",
			},
			"ingress_url": schema.StringAttribute{
				Computed:    true,
				Description: "Supervisor-reported Ingress URL (D-01). Empty when the add-on does not expose Ingress.",
			},
			"ingress_entry": schema.StringAttribute{
				Computed:    true,
				Description: "Supervisor-reported Ingress entry path (D-01). Empty when the add-on does not expose Ingress.",
			},
			"webui_url": schema.StringAttribute{
				Computed:    true,
				Description: "Supervisor-reported Web UI URL (D-01). Empty when the add-on does not publish a Web UI.",
			},
		},
	}
}

// Configure pulls the *client.Client out of the Provider's
// ConfigureResponse.DataSourceData. The framework calls Configure
// once per data source before any Read, so the Client is fresh on
// every invocation.
//
// req.ProviderData is nil during the framework's initial
// validation pass (before Provider.Configure has run); returning
// silently in that case is the documented framework idiom —
// emitting a diagnostic there would surface a spurious error on
// every `tofu validate`.
func (d *addonDataSource) Configure(_ context.Context, req datasource.ConfigureRequest, resp *datasource.ConfigureResponse) {
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

// Read looks the add-on up by slug via Client.GetAddonInfo and
// populates every Computed attribute from the returned AddOnInfo.
//
// Error surfacing:
//
//   - ErrAddonNotFound (Bridge 404) → an Error diagnostic whose
//     Summary is diagnostics.ErrNotFoundText, with the DOCS.md
//     anchor for `not_found` in the Detail (D-10 + D-11).
//   - Any other error → diagnostics.MapError, which carries the
//     per-error_code Summary, the Bridge request_id, and the
//     matching DOCS.md anchor.
func (d *addonDataSource) Read(ctx context.Context, req datasource.ReadRequest, resp *datasource.ReadResponse) {
	if d.client == nil {
		resp.Diagnostics.AddError(
			"Provider not configured",
			"Cannot read data.homeassistant_addon: the provider has not been configured with a *client.Client.",
		)
		return
	}

	var config addonDataSourceModel
	resp.Diagnostics.Append(req.Config.Get(ctx, &config)...)
	if resp.Diagnostics.HasError() {
		return
	}

	slug := config.Slug.ValueString()
	if slug == "" {
		resp.Diagnostics.AddError(
			"Invalid configuration",
			"data.homeassistant_addon requires a non-empty slug.",
		)
		return
	}

	info, err := d.client.GetAddonInfo(ctx, slug)
	if err != nil {
		if errors.Is(err, client.ErrAddonNotFound) {
			// The Client translates Bridge 404 into the
			// ErrAddonNotFound sentinel, so there is no
			// *BridgeError for MapError to switch on. Build the
			// same diagnostic shape by hand (D-08 Summary +
			// D-10 anchor + D-11 request_id placeholder).
			resp.Diagnostics.Append(diag.NewErrorDiagnostic(
				diagnostics.ErrNotFoundText,
				"request_id: \n"+diagnostics.DocAnchor("not_found")+"\nslug: "+slug,
			))
			return
		}
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	state := addonDataSourceModel{
		Slug:         types.StringValue(info.Slug),
		Name:         types.StringValue(info.Name),
		Version:      types.StringValue(info.Version),
		State:        types.StringValue(info.State),
		Started:      types.BoolValue(info.Started),
		Boot:         types.StringValue(info.Boot),
		Repository:   types.StringValue(info.Repository),
		Hostname:     types.StringValue(info.Hostname),
		IngressURL:   types.StringValue(info.IngressURL),
		IngressEntry: types.StringValue(info.IngressEntry),
		WebUIURL:     types.StringValue(info.WebUIURL),
	}
	// Supervisor may omit `slug` in its payload (the Bridge passes
	// through verbatim per D-02); fall back to the requested slug
	// so the data source's own argument round-trips.
	if info.Slug == "" {
		state.Slug = types.StringValue(slug)
	}
	if info.Options != nil {
		opts := make(map[string]types.String, len(info.Options))
		for k, v := range info.Options {
			opts[k] = types.StringValue(v)
		}
		state.Options = opts
	}
	if info.DNS == nil {
		state.DNS = types.ListNull(types.StringType)
	} else {
		dnsList, listDiags := types.ListValueFrom(ctx, types.StringType, info.DNS)
		resp.Diagnostics.Append(listDiags...)
		if listDiags.HasError() {
			return
		}
		state.DNS = dnsList
	}

	resp.Diagnostics.Append(resp.State.Set(ctx, &state)...)
}
