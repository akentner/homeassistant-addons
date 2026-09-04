// Package resource holds the Provider's Resource implementations.
// Plan 01 ships exactly one resource: homeassistant_addon (PROV-02)
// with a tracer-level Read body and Create / Update / Delete
// stubs. Plan 02 expands the schema with the full PROV-02 attribute
// set (url, options, start, boot + Plan 03's hostname / dns /
// ingress_url / ingress_entry / webui_url per D-01) and fills in
// the Create / Update / Delete bodies with the adoption-aware flow
// (D-04..D-06) + nonce-protected Delete (D-05..D-08 + LIFE-03).
//
// The Resource mirrors Bridge's supervisor.Client shape via the
// internal/client package (CF-16) — bearer-token-injecting
// RoundTripper, NewRequestWithContext per call, body-drain on
// non-200 BEFORE JSON decode (Phase 11 Rule-1 fix).
package resource

import (
	"context"
	"errors"
	"strings"

	"github.com/hashicorp/terraform-plugin-framework-timeouts/resource/timeouts"
	"github.com/hashicorp/terraform-plugin-framework/path"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringdefault"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringplanmodifier"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"terraform-provider-homeassistant/internal/client"
	"terraform-provider-homeassistant/internal/diagnostics"
)

// addonResourceModel is the typed view of the homeassistant_addon
// schema (Plan 01 minimum-viable subset per CF-10; Plan 02 expands
// to the full schema). The tfsdk struct tags map Go field names to
// schema attribute names — the framework uses these tags
// exclusively for the marshalling layer, so the field order here
// does not need to match the schema declaration order.
//
// Timeouts carries the per-operation timeouts block
// (PROV-09 + CF-03). Plan 01 only declares the block in the schema;
// Plan 02 wires Create / Update / Delete to read from this struct
// and apply the configured deadlines.
type addonResourceModel struct {
	Slug       types.String            `tfsdk:"slug"`
	Repository types.String            `tfsdk:"repository"`
	Options    map[string]types.String `tfsdk:"options"`
	Start      types.Bool              `tfsdk:"start"`
	Boot       types.String            `tfsdk:"boot"`
	Version    types.String            `tfsdk:"version"`
	State      types.String            `tfsdk:"state"`
	Started    types.Bool              `tfsdk:"started"`
	Hostname   types.String            `tfsdk:"hostname"`
	Timeouts   timeouts.Value          `tfsdk:"timeouts"`
}

// AddonResource implements resource.Resource + resource.ResourceWithImportState
// (PROV-08). The Resource holds the configured *client.Client
// stashed by Configure; the framework guarantees a fresh Configure
// call before every Read, so the Client is always current.
type AddonResource struct {
	client *client.Client
}

// NewAddonResource returns a fresh AddonResource suitable for use as
// a `func() resource.Resource` element in the Provider's Resources()
// slice. The Resource's Client is unset at construction; Configure
// wires it.
func NewAddonResource() *AddonResource {
	return &AddonResource{}
}

// Compile-time assertion that AddonResource satisfies the
// terraform-plugin-framework Resource interface (and the
// ResourceWithImportState + ResourceWithConfigure extensions).
var (
	_ resource.Resource                = (*AddonResource)(nil)
	_ resource.ResourceWithImportState = (*AddonResource)(nil)
	_ resource.ResourceWithConfigure   = (*AddonResource)(nil)
)

// Metadata returns the resource's type name. The Provider's
// TypeName (`homeassistant`) is prepended by the framework to form
// the full address `homeassistant_addon`.
func (r *AddonResource) Metadata(_ context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_addon"
}

// Schema declares the homeassistant_addon schema. Plan 01 ships the
// minimum-viable subset (slug + Computed version/state/started per
// CF-10); Plan 02 expands with options/start/boot full semantics,
// Plan 03 adds the hostname / dns / ingress_url / ingress_entry /
// webui_url Computed attributes per D-01.
//
// The `state` Computed attribute carries UseStateForUnknown()
// (PROV-10 + CF-04) so refreshes don't show spurious diffs.
// `slug` carries RequiresReplace so changing the slug triggers a
// destroy + create (different add-on = different resource).
func (r *AddonResource) Schema(_ context.Context, _ resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Attributes: map[string]schema.Attribute{
			"slug": schema.StringAttribute{
				Required:    true,
				Description: "Add-on slug (e.g. 'a0d7b6b6_my_addon'). Changing this forces a destroy + create.",
				PlanModifiers: []planmodifier.String{
					stringplanmodifier.RequiresReplace(),
				},
			},
			"repository": schema.StringAttribute{
				Optional:    true,
				Computed:    true,
				Description: "Add-on repository (default 'core'). Set to a custom repository slug for non-core add-ons.",
				Default:     stringdefault.StaticString("core"),
			},
			"options": schema.MapAttribute{
				Optional:    true,
				Computed:    true,
				ElementType: types.StringType,
				Description: "Add-on options (flat string map). Plan 02 wires the update flow via /v1/addons/{slug}/options.",
			},
			"start": schema.BoolAttribute{
				Optional:    true,
				Computed:    true,
				Description: "Whether the add-on should be started after install (default true). Plan 02 wires the follow-up start call per D-05.",
			},
			"boot": schema.StringAttribute{
				Optional:    true,
				Computed:    true,
				Description: "Boot mode: 'auto', 'manual', or 'manual_only'. Plan 02 wires the update flow.",
			},
			"version": schema.StringAttribute{
				Computed:    true,
				Description: "Currently-installed add-on version (from /v1/addons/{slug}/info).",
			},
			"state": schema.StringAttribute{
				Computed:    true,
				Description: "Current Supervisor-reported state (e.g. 'started', 'stopped'). UseStateForUnknown suppresses refresh diffs (PROV-10 + CF-04).",
				PlanModifiers: []planmodifier.String{
					stringplanmodifier.UseStateForUnknown(),
				},
			},
			"started": schema.BoolAttribute{
				Computed:    true,
				Description: "Whether the add-on is currently running (mirrors `state` for backwards compatibility).",
			},
			"hostname": schema.StringAttribute{
				Computed:    true,
				Description: "Supervisor-reported hostname for the add-on. Plan 03 widens the AddOnInfo struct per D-01.",
			},
		},
		// Plan 02 declares the per-operation timeouts block via
		// terraform-plugin-framework-timeouts. The dep is already
		// wired in go.mod; declaring the Block here keeps `go mod
		// tidy` honest and gives Plan 02 a single place to extend.
		Blocks: map[string]schema.Block{
			"timeouts": timeoutsBlock(),
		},
	}
}

// Configure pulls the *client.Client out of the Provider's
// ConfigureResponse.ResourceData (the framework's per-Resource
// channel that mirrors Provider.Configure's ClientData). The
// framework calls Configure once per Resource, before any RPC that
// uses the Resource, so the Client is fresh on every invocation.
//
// The Provider's Configure populates ProviderData via
// resp.ResourceData = c (Provider's ConfigureResponse carries a
// ResourceData field for exactly this handoff). The Resource's
// Configure receives it via req.ProviderData and type-asserts it
// to *client.Client.
func (r *AddonResource) Configure(_ context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
	if req.ProviderData == nil {
		// Provider-level Configure was never called (or failed).
		// Surface a clear Error diagnostic so the user sees the
		// misconfiguration rather than a nil-pointer panic.
		resp.Diagnostics.AddError(
			"Provider not configured",
			"The homeassistant provider was not configured before the homeassistant_addon resource was instantiated; this is always an internal error.",
		)
		return
	}
	c, ok := req.ProviderData.(*client.Client)
	if !ok {
		resp.Diagnostics.AddError(
			"Provider configured with the wrong client type",
			"The homeassistant provider's ConfigureResponse.ResourceData is not a *client.Client; this is always an internal error.",
		)
		return
	}
	r.client = c
}

// Create is a Plan 01 stub. Plan 02 fills it in with the
// adoption-aware flow per D-04..D-06.
func (r *AddonResource) Create(ctx context.Context, _ resource.CreateRequest, resp *resource.CreateResponse) {
	_ = ctx
	resp.Diagnostics.AddError(
		"not_implemented",
		"homeassistant_addon Create is not implemented in Phase 13 Plan 01 (tracer-level scope). Plan 02 fills in the Create flow with the adoption-aware semantics (D-04..D-06).",
	)
}

// Read is the Plan 01 tracer. It calls client.GetAddonInfo and
// populates the Computed attributes from the AddOnInfo payload.
// On ErrAddonNotFound it leaves the state empty (CF-06 idempotency:
// Delete on a missing add-on is a no-op). On any other error it
// surfaces a typed Diagnostic via diagnostics.MapError.
func (r *AddonResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	var state addonResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
	if resp.Diagnostics.HasError() {
		return
	}

	slug := state.Slug.ValueString()
	info, err := r.client.GetAddonInfo(ctx, slug)
	if errors.Is(err, client.ErrAddonNotFound) {
		// CF-06: 404 → leave state empty. The framework treats
		// this as "resource no longer exists" and removes it from
		// state on the next apply, but a `terraform plan` against
		// a missing add-on reports no diff instead of an error.
		return
	}
	if err != nil {
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	// Populate the model from the AddOnInfo payload. Optional /
	// Computed attributes that the Bridge did not populate (e.g.
	// `hostname` when the supervisor omits it) stay at the zero
	// value, which the framework renders as `null`.
	state.Version = types.StringValue(info.Version)
	state.State = types.StringValue(info.State)
	state.Started = types.BoolValue(info.Started)
	if info.Repository != "" {
		state.Repository = types.StringValue(info.Repository)
	}
	if info.Boot != "" {
		state.Boot = types.StringValue(info.Boot)
	}
	if info.Options != nil {
		opts := make(map[string]types.String, len(info.Options))
		for k, v := range info.Options {
			opts[k] = types.StringValue(v)
		}
		state.Options = opts
	}
	// hostname is part of the schema (forward-compat with Plan 03
	// D-01) but the Bridge's AddOnInfo does not populate it in
	// Plan 01 — we leave it at the zero value (null) so the
	// framework does not echo a stale string.

	resp.Diagnostics.Append(resp.State.Set(ctx, &state)...)
}

// Update is a Plan 01 stub. Plan 02 fills it in per D-06.
func (r *AddonResource) Update(ctx context.Context, _ resource.UpdateRequest, resp *resource.UpdateResponse) {
	_ = ctx
	resp.Diagnostics.AddError(
		"not_implemented",
		"homeassistant_addon Update is not implemented in Phase 13 Plan 01 (tracer-level scope). Plan 02 fills in the Update flow with options + pwned warning semantics (D-06 + CF-08 + PROV-06).",
	)
}

// Delete is a Plan 01 stub. Plan 02 fills it in per CF-09 + LIFE-03
// (X-Force-Destroy nonce).
func (r *AddonResource) Delete(ctx context.Context, _ resource.DeleteRequest, resp *resource.DeleteResponse) {
	_ = ctx
	resp.Diagnostics.AddError(
		"not_implemented",
		"homeassistant_addon Delete is not implemented in Phase 13 Plan 01 (tracer-level scope). Plan 02 fills in the Delete flow with the X-Force-Destroy nonce guard (CF-09 + LIFE-03 + PROV-07).",
	)
}

// ImportState implements PROV-08 (CF-05). The ImportState ID
// accepts two shapes:
//
//   - `a0d7c6b6_my_addon` (no `/`) — the whole ID is the slug,
//     repository defaults to "core".
//   - `local/my_addon` (contains `/`) — left of the first `/` is
//     the repository, right is the slug. The split tolerates
//     repository names with hyphens; subsequent `/` characters are
//     not supported (repository names never contain `/` in
//     practice).
//
// After splitting, the slug attribute is set in state directly
// (ImportStatePassthroughID only handles a single attribute; the
// repository default is added here). The subsequent Read refreshes
// every other Computed attribute from /v1/addons/{slug}/info.
func (r *AddonResource) ImportState(ctx context.Context, req resource.ImportStateRequest, resp *resource.ImportStateResponse) {
	id := req.ID
	if id == "" {
		resp.Diagnostics.AddError(
			"Invalid import ID",
			"The import ID must be either {slug} or {repository}/{slug}; received an empty string.",
		)
		return
	}

	var slug, repository string
	if idx := strings.Index(id, "/"); idx >= 0 {
		repository = id[:idx]
		slug = id[idx+1:]
	} else {
		slug = id
		repository = "core"
	}

	if slug == "" {
		resp.Diagnostics.AddError(
			"Invalid import ID",
			"The import ID must include a non-empty slug; got repository="+repository+" with empty slug.",
		)
		return
	}

	// Set both attributes via SetAttribute. The framework's
	// ImportStatePassthroughID helper handles a single attribute;
	// here we set both because the resource needs the repository
	// to be present in state for downstream Refresh / Update flows.
	resp.Diagnostics.Append(resp.State.SetAttribute(ctx, path.Root("slug"), slug)...)
	resp.Diagnostics.Append(resp.State.SetAttribute(ctx, path.Root("repository"), repository)...)
}
