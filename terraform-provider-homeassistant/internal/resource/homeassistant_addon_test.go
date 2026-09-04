package resource_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework-timeouts/resource/timeouts"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	fwresource "github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/tfsdk"
	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-go/tftypes"

	"terraform-bridge/contract"

	"terraform-provider-homeassistant/internal/client"
	tfresource "terraform-provider-homeassistant/internal/resource"
)

// tfsdkSchema is the framework's typed Schema value as returned by
// resource.SchemaResponse.Schema. The schema package's
// `schema.Schema` is the framework's view; we alias it here so
// the helper signatures stay short.
type tfsdkSchema = fwresource.Schema

// addonImportModel is the typed view used by Read + Import tests
// to verify State contents. The struct MUST mirror every
// schema attribute + block field using the framework's types
// package — the framework's State.Get rejects partial struct
// targets with a "mismatch between struct and object" diagnostic,
// and rejects plain Go types where types.String etc. is required.
type addonImportModel struct {
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

// schemaResponseFor invokes the resource's Schema method and
// returns the schema it produced. Used by tests that need to
// build a tfsdk.State matching the resource's schema.
func schemaResponseFor(t *testing.T, r resource.Resource) tfsdkSchema {
	t.Helper()
	var resp resource.SchemaResponse
	r.Schema(context.Background(), resource.SchemaRequest{}, &resp)
	if resp.Diagnostics.HasError() {
		t.Fatalf("resource.Schema returned error diagnostics: %v", resp.Diagnostics)
	}
	return resp.Schema
}

// newAddonResourceWithClient constructs a freshly-wired
// addonResource (via the exported NewAddonResource constructor)
// with the Client pre-installed via Configure. Returns the
// Resource (typed as the concrete AddonResource so tests can
// drive ResourceWithImportState + ResourceWithConfigure methods).
func newAddonResourceWithClient(t *testing.T, c *client.Client) *tfresource.AddonResource {
	t.Helper()
	r := tfresource.NewAddonResource()
	r.Configure(context.Background(), resource.ConfigureRequest{ProviderData: c}, &resource.ConfigureResponse{})
	return r
}

// buildState constructs a tfsdk.State with the supplied slug +
// repository populated. Used as the prior-state input to Read /
// Import. The state's Raw is built from a tftypes.Object whose
// shape matches the schema exactly (including the timeouts block);
// SetAttribute against this State succeeds because the framework
// can transform the value into the expected ObjectValue.
func buildState(t *testing.T, schema tfsdkSchema, slug, repository string) tfsdk.State {
	t.Helper()
	rawType := tftypes.Object{
		AttributeTypes: map[string]tftypes.Type{
			"slug":       tftypes.String,
			"repository": tftypes.String,
			"options":    tftypes.Map{ElementType: tftypes.String},
			"start":      tftypes.Bool,
			"boot":       tftypes.String,
			"version":    tftypes.String,
			"state":      tftypes.String,
			"started":    tftypes.Bool,
			"hostname":   tftypes.String,
			"timeouts": tftypes.Object{
				AttributeTypes: map[string]tftypes.Type{
					"create": tftypes.String,
					"read":   tftypes.String,
					"update": tftypes.String,
					"delete": tftypes.String,
				},
			},
		},
	}
	raw := tftypes.NewValue(rawType, map[string]tftypes.Value{
		"slug":       tftypes.NewValue(tftypes.String, slug),
		"repository": tftypes.NewValue(tftypes.String, repository),
		"options": tftypes.NewValue(tftypes.Map{ElementType: tftypes.String}, map[string]tftypes.Value{
			"log_level": tftypes.NewValue(tftypes.String, "info"),
		}),
		"start":    tftypes.NewValue(tftypes.Bool, true),
		"boot":     tftypes.NewValue(tftypes.String, "auto"),
		"version":  tftypes.NewValue(tftypes.String, "0.0.0"),
		"state":    tftypes.NewValue(tftypes.String, "started"),
		"started":  tftypes.NewValue(tftypes.Bool, true),
		"hostname": tftypes.NewValue(tftypes.String, ""),
		"timeouts": tftypes.NewValue(rawType.AttributeTypes["timeouts"].(tftypes.Object), nil),
	})
	return tfsdk.State{Raw: raw, Schema: schema}
}

// addonModelType returns the tftypes.Object type matching the
// Resource's schema (with all attribute types + the timeouts
// block's nested Object). Used by ImportState tests so the
// State.SetAttribute call can transform the value into the
// expected shape.
func addonModelType() tftypes.Object {
	return tftypes.Object{
		AttributeTypes: map[string]tftypes.Type{
			"slug":       tftypes.String,
			"repository": tftypes.String,
			"options":    tftypes.Map{ElementType: tftypes.String},
			"start":      tftypes.Bool,
			"boot":       tftypes.String,
			"version":    tftypes.String,
			"state":      tftypes.String,
			"started":    tftypes.Bool,
			"hostname":   tftypes.String,
			"timeouts": tftypes.Object{
				AttributeTypes: map[string]tftypes.Type{
					"create": tftypes.String,
					"read":   tftypes.String,
					"update": tftypes.String,
					"delete": tftypes.String,
				},
			},
		},
	}
}

// TestResourceSchema_RequiredAttributes asserts the schema's
// `slug` attribute is Required and the Computed `version`,
// `state`, `started` attributes are present.
func TestResourceSchema_RequiredAttributes(t *testing.T) {
	r := tfresource.NewAddonResource()
	schema := schemaResponseFor(t, r)

	slug, ok := schema.Attributes["slug"]
	if !ok {
		t.Fatalf("Schema.Attributes has no 'slug' key")
	}
	if !slug.IsRequired() {
		t.Errorf("slug is not Required (Required = %v)", slug.IsRequired())
	}

	for _, name := range []string{"version", "state", "started"} {
		attr, ok := schema.Attributes[name]
		if !ok {
			t.Errorf("Schema.Attributes has no %q key", name)
			continue
		}
		if !attr.IsComputed() {
			t.Errorf("%s attribute is not Computed (Computed = %v)", name, attr.IsComputed())
		}
	}
}

// TestResourceSchema_StateUsesUseStateForUnknown asserts the
// `state` Computed attribute carries the UseStateForUnknown plan
// modifier (PROV-10 + CF-04). Verified by reading the
// PlanModifiers via the underlying stringplanmodifier reflection.
func TestResourceSchema_StateUsesUseStateForUnknown(t *testing.T) {
	r := tfresource.NewAddonResource()
	schema := schemaResponseFor(t, r)

	stateAttr, ok := schema.Attributes["state"]
	if !ok {
		t.Fatalf("Schema.Attributes has no 'state' key")
	}
	// Inspect the PlanModifiers via the concrete
	// fwresource.StringAttribute.StringPlanModifiers() method
	// (the schema.Attributes map yields the schema.Attribute
	// interface so we type-assert).
	stringAttr, ok := stateAttr.(fwresource.StringAttribute)
	if !ok {
		t.Fatalf("state attribute is not a StringAttribute (got %T)", stateAttr)
	}
	modifiers := stringAttr.StringPlanModifiers()
	if len(modifiers) == 0 {
		t.Fatalf("state attribute has no plan modifiers; want UseStateForUnknown")
	}
	desc := modifiers[0].Description(context.Background())
	if !strings.Contains(strings.ToLower(desc), "state") {
		t.Errorf("state plan modifier description = %q, want one mentioning 'state'", desc)
	}
}

// TestResourceRead_Success drives a happy-path Read: the fake
// server returns a contract.AddOnInfo payload; the Resource.Read
// populates resp.State with version + state + started +
// repository + boot + options.
func TestResourceRead_Success(t *testing.T) {
	want := contract.AddOnInfo{
		Slug:       "a0d7c6b6_my_addon",
		Name:       "My Add-on",
		Version:    "1.2.3",
		State:      "started",
		Started:    true,
		Options:    map[string]string{"log_level": "info"},
		Boot:       "auto",
		Repository: "core",
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		wantPath := "/v1/addons/" + want.Slug + "/info"
		if r.URL.Path != wantPath {
			t.Errorf("server: path = %q, want %q", r.URL.Path, wantPath)
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(want)
	}))
	defer srv.Close()

	c, err := client.NewClient(srv.URL, "test-bearer-token")
	if err != nil {
		t.Fatalf("client.NewClient: %v", err)
	}
	r := newAddonResourceWithClient(t, c)
	schema := schemaResponseFor(t, r)
	prior := buildState(t, schema, want.Slug, "core")

	var resp resource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	r.Read(context.Background(), resource.ReadRequest{State: prior}, &resp)

	if resp.Diagnostics.HasError() {
		t.Fatalf("Read: diagnostics = %v", resp.Diagnostics)
	}

	var state addonImportModel
	diags := resp.State.Get(context.Background(), &state)
	if diags.HasError() {
		t.Fatalf("State.Get: %v", diags)
	}
	if state.Version.ValueString() != want.Version {
		t.Errorf("Version = %q, want %q", state.Version.ValueString(), want.Version)
	}
	if state.State.ValueString() != want.State {
		t.Errorf("State = %q, want %q", state.State.ValueString(), want.State)
	}
	if state.Started.ValueBool() != want.Started {
		t.Errorf("Started = %v, want %v", state.Started.ValueBool(), want.Started)
	}
	if state.Repository.ValueString() != want.Repository {
		t.Errorf("Repository = %q, want %q", state.Repository.ValueString(), want.Repository)
	}
}

// TestResourceRead_NotFoundReturnsEmpty is the CF-06 idempotency
// guard: when the Bridge returns 404 + not_found, Read must leave
// the response state empty (no diagnostics). This lets `terraform
// destroy` succeed against a missing add-on (Delete is a no-op).
func TestResourceRead_NotFoundReturnsEmpty(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
			ErrorCode: "not_found",
			RequestID: "rid-404",
		})
	}))
	defer srv.Close()

	c, err := client.NewClient(srv.URL, "test-bearer-token")
	if err != nil {
		t.Fatalf("client.NewClient: %v", err)
	}
	r := newAddonResourceWithClient(t, c)
	schema := schemaResponseFor(t, r)
	prior := buildState(t, schema, "missing", "core")

	var resp resource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	r.Read(context.Background(), resource.ReadRequest{State: prior}, &resp)

	if resp.Diagnostics.HasError() {
		t.Errorf("Read(404): expected no error diagnostics, got %v", resp.Diagnostics)
	}
}

// TestResourceRead_OtherErrorReturnsDiagnostic asserts the
// non-404 error path: a 502 + upstream_error surfaces as a
// typed MapError Diagnostic via diagnostics.MapError.
func TestResourceRead_OtherErrorReturnsDiagnostic(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
			ErrorCode: "upstream_error",
			RequestID: "rid-502",
		})
	}))
	defer srv.Close()

	c, err := client.NewClient(srv.URL, "test-bearer-token")
	if err != nil {
		t.Fatalf("client.NewClient: %v", err)
	}
	r := newAddonResourceWithClient(t, c)
	schema := schemaResponseFor(t, r)
	prior := buildState(t, schema, "any", "core")

	var resp resource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	r.Read(context.Background(), resource.ReadRequest{State: prior}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Read(502): expected Error diagnostics, got none")
	}
	if !strings.Contains(resp.Diagnostics[0].Summary(), "Transient Supervisor failure") {
		t.Errorf("Read(502): summary %q does not contain upstream_error diagnostic text", resp.Diagnostics[0].Summary())
	}
}

// TestResourceImport_PassthroughSingleSlug asserts CF-05
// ImportStatePassthroughID with `{slug}` (no `/`): the import ID
// populates slug + repository (repository defaults to "core").
func TestResourceImport_PassthroughSingleSlug(t *testing.T) {
	r := tfresource.NewAddonResource()
	schema := schemaResponseFor(t, r)

	// Initialize the import State with an empty Object of the
	// schema's type so SetAttribute inside ImportState has a
	// well-formed Raw to merge into.
	importState := tfsdk.State{
		Raw:    tftypes.NewValue(addonModelType(), nil),
		Schema: schema,
	}

	var resp resource.ImportStateResponse
	resp.State = importState
	r.ImportState(context.Background(), resource.ImportStateRequest{ID: "a0d7c6b6_test"}, &resp)

	if resp.Diagnostics.HasError() {
		t.Fatalf("ImportState: diagnostics = %v", resp.Diagnostics)
	}

	// Get with a struct that mirrors every field in the schema —
	// the framework rejects partial struct targets.
	var state addonImportModel
	diags := resp.State.Get(context.Background(), &state)
	if diags.HasError() {
		t.Fatalf("State.Get: %v", diags)
	}
	if state.Slug.ValueString() != "a0d7c6b6_test" {
		t.Errorf("Slug = %q, want %q", state.Slug.ValueString(), "a0d7c6b6_test")
	}
	if state.Repository.ValueString() != "core" {
		t.Errorf("Repository = %q, want %q (default)", state.Repository.ValueString(), "core")
	}
}

// TestResourceImport_PassthroughRepoSlashSlug asserts CF-05
// ImportStatePassthroughID with `{repository}/{slug}`: the import
// ID populates both attributes from the split.
func TestResourceImport_PassthroughRepoSlashSlug(t *testing.T) {
	r := tfresource.NewAddonResource()
	schema := schemaResponseFor(t, r)

	importState := tfsdk.State{
		Raw:    tftypes.NewValue(addonModelType(), nil),
		Schema: schema,
	}

	var resp resource.ImportStateResponse
	resp.State = importState
	r.ImportState(context.Background(), resource.ImportStateRequest{ID: "local/my_addon"}, &resp)

	if resp.Diagnostics.HasError() {
		t.Fatalf("ImportState: diagnostics = %v", resp.Diagnostics)
	}

	var state addonImportModel
	diags := resp.State.Get(context.Background(), &state)
	if diags.HasError() {
		t.Fatalf("State.Get: %v", diags)
	}
	if state.Slug.ValueString() != "my_addon" {
		t.Errorf("Slug = %q, want %q", state.Slug.ValueString(), "my_addon")
	}
	if state.Repository.ValueString() != "local" {
		t.Errorf("Repository = %q, want %q", state.Repository.ValueString(), "local")
	}
}

// TestResourceImport_EmptyID asserts the empty-import-ID error
// path. Per the ImportState contract the resource must surface
// a diagnostic rather than silently setting empty attributes.
func TestResourceImport_EmptyID(t *testing.T) {
	r := tfresource.NewAddonResource()
	schema := schemaResponseFor(t, r)

	importState := tfsdk.State{
		Raw:    tftypes.NewValue(addonModelType(), nil),
		Schema: schema,
	}

	var resp resource.ImportStateResponse
	resp.State = importState
	r.ImportState(context.Background(), resource.ImportStateRequest{ID: ""}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("ImportState(empty): expected Error diagnostics, got none")
	}
}

// TestResourceImport_EmptySlugAfterSplit asserts the
// `{repository}/` form (empty slug after split) surfaces a
// diagnostic.
func TestResourceImport_EmptySlugAfterSplit(t *testing.T) {
	r := tfresource.NewAddonResource()
	schema := schemaResponseFor(t, r)

	importState := tfsdk.State{
		Raw:    tftypes.NewValue(addonModelType(), nil),
		Schema: schema,
	}

	var resp resource.ImportStateResponse
	resp.State = importState
	r.ImportState(context.Background(), resource.ImportStateRequest{ID: "local/"}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("ImportState('local/'): expected Error diagnostics, got none")
	}
}

// TestResourceStubMethods asserts Create / Update / Delete return
// the Plan 01 `not_implemented` diagnostics so Plan 02's
// adopters see a consistent shape regardless of which lifecycle
// method they hit.
func TestResourceStubMethods(t *testing.T) {
	r := tfresource.NewAddonResource()
	schema := schemaResponseFor(t, r)
	prior := buildState(t, schema, "any", "core")

	// Create
	{
		var resp resource.CreateResponse
		resp.State = tfsdk.State{Schema: schema}
		r.Create(context.Background(), resource.CreateRequest{Plan: tfsdk.Plan{Schema: schema, Raw: prior.Raw}}, &resp)
		if !resp.Diagnostics.HasError() {
			t.Errorf("Create: expected Error diagnostic, got none")
		}
		if resp.Diagnostics[0].Summary() != "not_implemented" {
			t.Errorf("Create: summary = %q, want %q", resp.Diagnostics[0].Summary(), "not_implemented")
		}
	}

	// Update
	{
		var resp resource.UpdateResponse
		resp.State = tfsdk.State{Schema: schema}
		r.Update(context.Background(), resource.UpdateRequest{Plan: tfsdk.Plan{Schema: schema, Raw: prior.Raw}}, &resp)
		if !resp.Diagnostics.HasError() {
			t.Errorf("Update: expected Error diagnostic, got none")
		}
		if resp.Diagnostics[0].Summary() != "not_implemented" {
			t.Errorf("Update: summary = %q, want %q", resp.Diagnostics[0].Summary(), "not_implemented")
		}
	}

	// Delete
	{
		var resp resource.DeleteResponse
		resp.State = tfsdk.State{Schema: schema}
		r.Delete(context.Background(), resource.DeleteRequest{State: prior}, &resp)
		if !resp.Diagnostics.HasError() {
			t.Errorf("Delete: expected Error diagnostic, got none")
		}
		if resp.Diagnostics[0].Summary() != "not_implemented" {
			t.Errorf("Delete: summary = %q, want %q", resp.Diagnostics[0].Summary(), "not_implemented")
		}
	}
}

// TestResourceConfigure_NoClient asserts the Provider-not-configured
// error path. When Configure is called with req.ProviderData == nil
// the Resource must surface an Error diagnostic rather than
// panicking.
func TestResourceConfigure_NoClient(t *testing.T) {
	r := tfresource.NewAddonResource()
	var resp resource.ConfigureResponse
	r.Configure(context.Background(), resource.ConfigureRequest{ProviderData: nil}, &resp)
	if !resp.Diagnostics.HasError() {
		t.Errorf("Configure(nil): expected Error diagnostics, got none")
	}
}

// TestResourceConfigure_WrongClientType asserts the type-assertion
// guard in Configure. A non-*client.Client value must surface a
// diagnostic, not panic.
func TestResourceConfigure_WrongClientType(t *testing.T) {
	r := tfresource.NewAddonResource()
	var resp resource.ConfigureResponse
	r.Configure(context.Background(), resource.ConfigureRequest{ProviderData: "not-a-client"}, &resp)
	if !resp.Diagnostics.HasError() {
		t.Errorf("Configure(string): expected Error diagnostics, got none")
	}
}

// Compile-time guard: the resource satisfies resource.Resource +
// resource.ResourceWithImportState + resource.ResourceWithConfigure.
var (
	_ resource.Resource                = (*tfresource.AddonResource)(nil)
	_ resource.ResourceWithImportState = (*tfresource.AddonResource)(nil)
	_ resource.ResourceWithConfigure   = (*tfresource.AddonResource)(nil)
)

// errIsUnusedImportReserved is a tiny helper to keep the `errors`
// import available for future tests that might use errors.Is.
// Remove if no longer needed.
var _ = errors.Is
