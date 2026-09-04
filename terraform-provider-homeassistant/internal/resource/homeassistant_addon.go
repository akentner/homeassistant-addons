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
	"github.com/hashicorp/terraform-plugin-framework/diag"
	"github.com/hashicorp/terraform-plugin-framework/path"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/booldefault"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringdefault"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringplanmodifier"
	"github.com/hashicorp/terraform-plugin-framework/schema/validator"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"terraform-bridge/contract"

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
	URL        types.String            `tfsdk:"url"`
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
			"url": schema.StringAttribute{
				Optional:    true,
				Description: "Explicit add-on repository URL. Optional — only set when the add-on lives in a non-core repository not registered via the Supervisor UI.",
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
				Description: "Whether the add-on should be started after install (default true). D-05 convergent UX — Create follows up with POST /start when start=true and the add-on is not already running.",
				Default:     booldefault.StaticBool(true),
			},
			"boot": schema.StringAttribute{
				Optional:    true,
				Computed:    true,
				Description: "Boot mode: 'auto', 'manual', or 'manual_only'. Plan 02 wires the update flow via /v1/addons/{slug}/options with boot alongside options.",
				Validators: []validator.String{
					stringOneOf("auto", "manual", "manual_only"),
				},
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
				Description: "Supervisor-reported hostname for the add-on. Plan 03 widens the AddOnInfo struct per D-01 — populated once the Bridge's /info endpoint exposes the hostname field.",
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

// stringOneOf is a small validator constructor used by Schema to
// restrict the `boot` attribute to a closed enum per CF-10.
// Returns a validator that rejects any value outside the given set
// (case-sensitive). Mirrors the stringvalidator.OneOf helper in
// the terraform-plugin-framework validators package without
// pulling that dependency in for a single use-site.
func stringOneOf(allowed ...string) validator.String {
	return stringOneOfValidator(allowed)
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

// Create implements the adoption-aware flow per D-04..D-06 + CF-07.
//
// The four-step algorithm:
//
//  1. GET /v1/addons/{slug}/info (D-04). 200 → adoption path
//     (use the AddOnInfo as the initial state; if the user's
//     options/boot differ from info.Options/info.Boot → POST
//     /options per D-06 single-round-trip convergent update).
//  2. 404 → fresh install: POST /v1/addons/{slug}/install.
//  3. On 409 already_installed from POST /install (the
//     concurrent-race fallback per CF-07 + Phase 12 D-26): fall
//     through to re-fetch via GET info and adopt.
//  4. After adoption OR successful install: if start=true and
//     started=false (D-05 convergent UX) → POST
//     /v1/addons/{slug}/start.
//
// On any non-trivial error → diagnostics.MapError(err). On
// success → re-fetch via GET /info and populate resp.State.
func (r *AddonResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	if r.client == nil {
		resp.Diagnostics.AddError(
			"Provider not configured",
			"Cannot create homeassistant_addon: Provider has not been configured with a *client.Client.",
		)
		return
	}

	var plan addonResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)
	if resp.Diagnostics.HasError() {
		return
	}

	slug := plan.Slug.ValueString()
	if slug == "" {
		resp.Diagnostics.AddError(
			"Invalid plan",
			"homeassistant_addon Create requires a non-empty slug.",
		)
		return
	}

	// Step 1: GET /v1/addons/{slug}/info (D-04 adoption probe).
	info, err := r.client.GetAddonInfo(ctx, slug)
	adopted := false
	switch {
	case err == nil:
		// 200 → adoption path (D-04). info is non-nil.
		adopted = true
	case errors.Is(err, client.ErrAddonNotFound):
		// 404 → fresh install. info stays nil; fall through to
		// the install path below.
	default:
		// Other error (network, 502, etc.) → MapError. The Create
		// fails fast; we do NOT attempt install on a transient
		// failure (the operator can retry).
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	// Step 2: D-06 convergent-options follow-up for the adoption
	// path. Synthesize a priorState from the AddOnInfo so the
	// diff helper has a real baseline (otherwise the user's
	// plan options always differ from the empty zero value,
	// triggering an unnecessary POST /options on every
	// adoption).
	if adopted {
		if err := r.applyOptionsIfChanged(ctx, slug, infoToBaseline(info), &plan, &resp.Diagnostics); err != nil {
			resp.Diagnostics.Append(diagnostics.MapError(err)...)
			return
		}
	} else {
		// Step 3: 404 → POST /install.
		installErr := r.client.PostAddonInstall(ctx, slug)
		if installErr != nil {
			if errors.Is(installErr, client.ErrAlreadyInstalled) {
				// CF-07 + Phase 12 D-26 concurrent-race fallback.
				// Fall through to adoption: re-fetch via GET info.
				info, err = r.client.GetAddonInfo(ctx, slug)
				if err != nil {
					resp.Diagnostics.Append(diagnostics.MapError(err)...)
					return
				}
				adopted = true
				// After adoption, also push options/boot if they
				// differ — same D-06 path as the GET-first adoption.
				if err := r.applyOptionsIfChanged(ctx, slug, infoToBaseline(info), &plan, &resp.Diagnostics); err != nil {
					resp.Diagnostics.Append(diagnostics.MapError(err)...)
					return
				}
			} else {
				resp.Diagnostics.Append(diagnostics.MapError(installErr)...)
				return
			}
		}
	}

	// Step 4: D-05 follow-up start. If the user wants start=true
	// (the schema default) AND the add-on is currently not
	// running → POST /v1/addons/{slug}/start. The "currently not
	// running" check covers both the fresh-install case (info is
	// nil; assume not-started per D-05) and the adoption case
	// (info.Started is the source of truth).
	if plan.Start.ValueBool() {
		currentlyStarted := info != nil && info.Started
		if !currentlyStarted {
			startErr := r.client.PostAddonStart(ctx, slug)
			if startErr != nil {
				resp.Diagnostics.Append(diagnostics.MapError(startErr)...)
				return
			}
		}
	}

	// Final re-fetch: regardless of whether we adopted or freshly
	// installed + started, refresh via GET /info so the framework
	// sees the authoritative state for the resp.State.
	finalInfo, err := r.client.GetAddonInfo(ctx, slug)
	if err != nil {
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	// Populate the response state from the final AddOnInfo. We
	// preserve the user's plan-time slug + repository + start +
	// boot (they are Config-level attributes, not Refresh-driven)
	// and overwrite the Computed fields.
	r.applyInfoToState(&plan, finalInfo)
	resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
}

// infoToBaseline synthesizes an addonResourceModel from an
// AddOnInfo for use as the prior-state baseline in Create's
// D-06 convergent-options path. Only the fields the diff helper
// reads (Options + Boot) need to be populated; other fields
// stay at their zero values.
func infoToBaseline(info *contract.AddOnInfo) *addonResourceModel {
	if info == nil {
		return nil
	}
	baseline := &addonResourceModel{
		Boot: types.StringValue(info.Boot),
	}
	if info.Options != nil {
		baseline.Options = make(map[string]types.String, len(info.Options))
		for k, v := range info.Options {
			baseline.Options[k] = types.StringValue(v)
		}
	}
	return baseline
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

// Update implements CF-08 + PROV-06. The handler computes the
// options/boot diff between the planned and current state and
// pushes any change via POST /v1/addons/{slug}/options.
//
// PROV-06 pwned handling: the Bridge's /options endpoint
// currently surfaces the typed OptionsValidateDiagnostic envelope
// ONLY on the 400 validation-failure path. The Phase 13 Provider
// surfaces pwned as a Warning when ANY response body from the
// options flow contains a top-level `pwned` field; the typed
// envelope wiring is deferred to Phase 14. The handler pokes at
// the response via a small dedicated helper that catches the
// 200-OK + pwned=true case via a custom bridge-test server shape.
//
// On a non-trivial error → diagnostics.MapError(err). On success
// → re-fetch via GET /info and populate resp.State.
func (r *AddonResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	if r.client == nil {
		resp.Diagnostics.AddError(
			"Provider not configured",
			"Cannot update homeassistant_addon: Provider has not been configured with a *client.Client.",
		)
		return
	}

	var plan, state addonResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)
	if resp.Diagnostics.HasError() {
		return
	}
	resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
	if resp.Diagnostics.HasError() {
		return
	}

	slug := plan.Slug.ValueString()
	if slug == "" {
		resp.Diagnostics.AddError(
			"Invalid plan",
			"homeassistant_addon Update requires a non-empty slug in state.",
		)
		return
	}

	// Options/boot diff. Pass the prior state's options as the
	// "info" baseline so the same diff helper used by Create's
	// adoption path works. The diags pointer lets the helper
	// append the pwned Warning (CF-08 + PROV-06 + D-09) when the
	// Bridge's options response surfaces a pwned advisory.
	if err := r.applyOptionsIfChanged(ctx, slug, &state, &plan, &resp.Diagnostics); err != nil {
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	// Final re-fetch.
	finalInfo, err := r.client.GetAddonInfo(ctx, slug)
	if err != nil {
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}
	r.applyInfoToState(&plan, finalInfo)
	resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
}

// Delete implements CF-09 + LIFE-03. The handler fetches a fresh
// nonce via POST /v1/auth/nonce and immediately calls POST
// /v1/addons/{slug}/uninstall with the nonce as the X-Force-Destroy
// header. Per D-07, a nonce_expired or nonce_used response from
// the Bridge triggers a single retry (re-fetch nonce + re-call
// uninstall) within the per-operation timeout budget — the retry
// is bounded so the operation cannot loop indefinitely.
//
// On 204 (CF-09 success) or 404 (CF-06 idempotency: Delete on
// missing add-on is a no-op) the handler returns success with
// resp.State empty. On any other Bridge error → diagnostics.MapError.
func (r *AddonResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	if r.client == nil {
		resp.Diagnostics.AddError(
			"Provider not configured",
			"Cannot delete homeassistant_addon: Provider has not been configured with a *client.Client.",
		)
		return
	}

	var state addonResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
	if resp.Diagnostics.HasError() {
		return
	}

	slug := state.Slug.ValueString()
	if slug == "" {
		resp.Diagnostics.AddError(
			"Invalid state",
			"homeassistant_addon Delete requires a non-empty slug in state.",
		)
		return
	}

	// Fetch a fresh nonce + call uninstall. One retry allowed
	// for nonce_expired|nonce_used per D-07.
	nonceResp, err := r.client.PostAuthNonce(ctx)
	if err != nil {
		resp.Diagnostics.Append(diagnostics.MapError(err)...)
		return
	}

	installErr := r.client.PostAddonUninstall(ctx, slug, nonceResp.Nonce)
	if installErr == nil {
		// Success — resp.State is intentionally empty (CF-06 +
		// CF-09). The framework drops the resource from state.
		return
	}

	// Retry path (D-07): nonce_expired or nonce_used → re-fetch
	// nonce + re-call uninstall once.
	var be *client.BridgeError
	if errors.As(installErr, &be) {
		if be.Err.ErrorCode == "nonce_expired" || be.Err.ErrorCode == "nonce_used" {
			nonceResp2, err2 := r.client.PostAuthNonce(ctx)
			if err2 != nil {
				resp.Diagnostics.Append(diagnostics.MapError(err2)...)
				return
			}
			installErr = r.client.PostAddonUninstall(ctx, slug, nonceResp2.Nonce)
			if installErr == nil {
				return
			}
		}
	}

	resp.Diagnostics.Append(diagnostics.MapError(installErr)...)
}

// applyOptionsIfChanged is the shared D-06 single-round-trip
// helper used by Create (adoption path) and Update (diff path).
// It compares the planned options/boot against the prior baseline
// (priorInfo.Options + priorInfo.Boot on the Create adoption
// path; priorState.Options + priorState.Boot on the Update path)
// and, if either differs, POSTs the merged options body to
// /v1/addons/{slug}/options.
//
// On success the function inspects the Bridge response for a
// top-level `pwned` field (CF-08 + PROV-06 + D-09) and surfaces
// a Warning diagnostic via diagnostics.AddPwnedWarning when
// present. The pwned response body is the Phase 14 wire-level
// shape; Phase 13 wires the Provider side so the contract is
// locked in regardless of when the Bridge begins surfacing
// the typed envelope.
//
// The merge convention: planned options take precedence; keys
// present in the baseline but absent from the plan are kept
// (so the user's plan never silently drops Supervisor-side
// defaults like log_level=info). boot is taken from the plan
// when non-empty, else from the baseline.
func (r *AddonResource) applyOptionsIfChanged(ctx context.Context, slug string, priorState *addonResourceModel, plan *addonResourceModel, diags *diag.Diagnostics) error {
	planOpts := plan.Options
	planBoot := plan.Boot.ValueString()

	var baselineOpts map[string]types.String
	var baselineBoot string
	if priorState != nil {
		baselineOpts = priorState.Options
		baselineBoot = priorState.Boot.ValueString()
	}

	// Diff: only push when at least one of options/boot differs.
	optionsDiffer := !mapStringEqual(baselineOpts, planOpts)
	bootDiffers := planBoot != baselineBoot && planBoot != ""

	if !optionsDiffer && !bootDiffers {
		return nil
	}

	// Build the merged body. Use the plan's options as the
	// ground truth; carry forward any baseline keys the plan did
	// not include so a partial plan doesn't silently drop
	// Supervisor-side defaults. The merged map is what Bridge's
	// /options receives verbatim (CF-08 + PROV-06).
	merged := make(map[string]any, len(planOpts))
	for k, v := range planOpts {
		merged[k] = v.ValueString()
	}
	// Carry forward baseline keys not present in the plan so a
	// partial plan doesn't silently drop Supervisor-side
	// defaults like log_level=info.
	for k, v := range baselineOpts {
		if _, present := merged[k]; !present {
			merged[k] = v.ValueString()
		}
	}
	// boot is sent as a top-level key alongside options (per the
	// Phase 12 BRIDGE-08 contract that /options accepts both).
	if planBoot != "" {
		merged["boot"] = planBoot
	}

	respBody, err := r.client.PostAddonOptions(ctx, slug, merged)
	if err != nil {
		return err
	}

	// Inspect for pwned advisory. The Bridge's current
	// OptionsValidateDiagnostic envelope appears on the 400
	// validation failure path; the future 200-OK + pwned=true
	// shape is being verified in Phase 14. Until that lands,
	// this code path is exercised only by the dedicated
	// pwned-warning test against a custom test handler.
	if diags != nil {
		if pwned, ok := respBody["pwned"]; ok && pwned != nil {
			if pwnedBool, isBool := pwned.(bool); isBool && pwnedBool {
				// Build a useful detail string from the
				// response payload. The pwned_message field
				// is the canonical Supervisor-supplied text;
				// fall back to the raw payload if absent.
				detail := "pwned: true (Bridge response)"
				if msg, ok := respBody["pwned_message"].(string); ok && msg != "" {
					detail = msg
				}
				diagnostics.AddPwnedWarning(diags, detail)
			}
		}
	}

	return nil
}

// mapStringEqual compares two map[string]types.String for deep
// equality via ValueString(). Used by applyOptionsIfChanged to
// detect when the user's options differ from the Bridge-side
// baseline.
func mapStringEqual(a, b map[string]types.String) bool {
	if len(a) != len(b) {
		return false
	}
	for k, av := range a {
		bv, ok := b[k]
		if !ok {
			return false
		}
		if av.ValueString() != bv.ValueString() {
			return false
		}
	}
	return true
}

// applyInfoToState populates a model's Computed fields from an
// AddOnInfo payload. The slug + repository + start + boot + url
// attributes are Config-level and are preserved from the input
// plan; only the Computed fields + options are overwritten. This
// is the shared helper used by Create + Update to keep the
// state-finalization code in one place.
func (r *AddonResource) applyInfoToState(model *addonResourceModel, info *contract.AddOnInfo) {
	if info == nil {
		return
	}
	model.Version = types.StringValue(info.Version)
	model.State = types.StringValue(info.State)
	model.Started = types.BoolValue(info.Started)
	if info.Repository != "" {
		model.Repository = types.StringValue(info.Repository)
	}
	if info.Boot != "" {
		model.Boot = types.StringValue(info.Boot)
	}
	if info.Options != nil {
		opts := make(map[string]types.String, len(info.Options))
		for k, v := range info.Options {
			opts[k] = types.StringValue(v)
		}
		model.Options = opts
	}
	// hostname + url are forward-compat placeholders. hostname
	// stays null until Plan 03 widens AddOnInfo per D-01; url is
	// never repopulated from /info (the Bridge does not echo it
	// back — the user's *.tf is the source of truth).
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
