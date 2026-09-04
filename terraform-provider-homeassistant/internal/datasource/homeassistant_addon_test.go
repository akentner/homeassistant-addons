package datasource_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	fwdatasource "github.com/hashicorp/terraform-plugin-framework/datasource/schema"
	"github.com/hashicorp/terraform-plugin-framework/tfsdk"
	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-go/tftypes"

	"terraform-bridge/contract"

	"terraform-provider-homeassistant/internal/client"
	tfdatasource "terraform-provider-homeassistant/internal/datasource"
)

// addonDSModel mirrors every attribute of the homeassistant_addon
// data source schema. The framework's State.Get rejects partial
// struct targets, so this struct must stay in lockstep with the
// schema (including the five D-01 attributes).
type addonDSModel struct {
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

// addonDSSchemaFor invokes the data source's Schema method and
// returns the produced schema.
func addonDSSchemaFor(t *testing.T, d datasource.DataSource) fwdatasource.Schema {
	t.Helper()
	var resp datasource.SchemaResponse
	d.Schema(context.Background(), datasource.SchemaRequest{}, &resp)
	if resp.Diagnostics.HasError() {
		t.Fatalf("DataSource.Schema returned error diagnostics: %v", resp.Diagnostics)
	}
	return resp.Schema
}

// addonDSType returns the tftypes.Object matching the data
// source's schema. Used to build the tfsdk.Config the Read
// request carries.
func addonDSType() tftypes.Object {
	return tftypes.Object{
		AttributeTypes: map[string]tftypes.Type{
			"slug":          tftypes.String,
			"name":          tftypes.String,
			"version":       tftypes.String,
			"state":         tftypes.String,
			"started":       tftypes.Bool,
			"options":       tftypes.Map{ElementType: tftypes.String},
			"boot":          tftypes.String,
			"repository":    tftypes.String,
			"hostname":      tftypes.String,
			"dns":           tftypes.List{ElementType: tftypes.String},
			"ingress_url":   tftypes.String,
			"ingress_entry": tftypes.String,
			"webui_url":     tftypes.String,
		},
	}
}

// buildAddonDSConfig builds the tfsdk.Config the framework would
// hand to Read: `slug` populated from the user's *.tf, every
// Computed attribute null (unknown until Read fills it).
func buildAddonDSConfig(t *testing.T, schema fwdatasource.Schema, slug string) tfsdk.Config {
	t.Helper()
	rawType := addonDSType()
	return tfsdk.Config{
		Raw: tftypes.NewValue(rawType, map[string]tftypes.Value{
			"slug":          tftypes.NewValue(tftypes.String, slug),
			"name":          tftypes.NewValue(tftypes.String, nil),
			"version":       tftypes.NewValue(tftypes.String, nil),
			"state":         tftypes.NewValue(tftypes.String, nil),
			"started":       tftypes.NewValue(tftypes.Bool, nil),
			"options":       tftypes.NewValue(tftypes.Map{ElementType: tftypes.String}, nil),
			"boot":          tftypes.NewValue(tftypes.String, nil),
			"repository":    tftypes.NewValue(tftypes.String, nil),
			"hostname":      tftypes.NewValue(tftypes.String, nil),
			"dns":           tftypes.NewValue(tftypes.List{ElementType: tftypes.String}, nil),
			"ingress_url":   tftypes.NewValue(tftypes.String, nil),
			"ingress_entry": tftypes.NewValue(tftypes.String, nil),
			"webui_url":     tftypes.NewValue(tftypes.String, nil),
		}),
		Schema: schema,
	}
}

// newAddonDSWithClient constructs the data source and wires the
// Client through Configure (the same handoff the framework
// performs via ConfigureResponse.DataSourceData).
func newAddonDSWithClient(t *testing.T, c *client.Client) datasource.DataSource {
	t.Helper()
	d := tfdatasource.NewAddonDataSource()
	cfg, ok := d.(datasource.DataSourceWithConfigure)
	if !ok {
		t.Fatalf("addon data source does not implement DataSourceWithConfigure")
	}
	var resp datasource.ConfigureResponse
	cfg.Configure(context.Background(), datasource.ConfigureRequest{ProviderData: c}, &resp)
	if resp.Diagnostics.HasError() {
		t.Fatalf("Configure: %v", resp.Diagnostics)
	}
	return d
}

// TestDataSourceSchema asserts the PROV-11 schema shape: `slug` is
// the single Required argument and every AddOnInfo field (including
// the five D-01 additions) is declared Computed.
func TestDataSourceSchema(t *testing.T) {
	d := tfdatasource.NewAddonDataSource()
	schema := addonDSSchemaFor(t, d)

	slug, ok := schema.Attributes["slug"]
	if !ok {
		t.Fatalf("Schema.Attributes has no 'slug' key")
	}
	if !slug.IsRequired() {
		t.Errorf("slug is not Required (Required = %v)", slug.IsRequired())
	}

	computed := []string{
		"name", "version", "state", "started", "options", "boot", "repository",
		"hostname", "dns", "ingress_url", "ingress_entry", "webui_url",
	}
	for _, name := range computed {
		attr, ok := schema.Attributes[name]
		if !ok {
			t.Errorf("Schema.Attributes has no %q key", name)
			continue
		}
		if !attr.IsComputed() {
			t.Errorf("%s attribute is not Computed (Computed = %v)", name, attr.IsComputed())
		}
		if attr.IsRequired() {
			t.Errorf("%s attribute must not be Required (read-only data source)", name)
		}
	}

	// Exactly one Required attribute (slug) — a data source that
	// accidentally marks a Computed attribute Required would break
	// every consumer's *.tf.
	var requiredCount int
	for _, attr := range schema.Attributes {
		if attr.IsRequired() {
			requiredCount++
		}
	}
	if requiredCount != 1 {
		t.Errorf("Required attribute count = %d, want 1 (slug only)", requiredCount)
	}
}

// TestDataSourceRead_Success drives the happy path: the fake Bridge
// returns a fully-populated AddOnInfo (including the five D-01
// fields) and Read must land every attribute in resp.State.
func TestDataSourceRead_Success(t *testing.T) {
	want := contract.AddOnInfo{
		Slug:         "a0d7c6b6_my_addon",
		Name:         "My Add-on",
		Version:      "1.2.3",
		State:        "started",
		Started:      true,
		Options:      map[string]string{"log_level": "info"},
		Boot:         "auto",
		Repository:   "core",
		Hostname:     "a0d7c6b6-my-addon",
		DNS:          []string{"a0d7c6b6-my-addon.local.hass.io", "my-addon.local"},
		IngressURL:   "/api/hassio_ingress/abc123/",
		IngressEntry: "/api/hassio_ingress/abc123",
		WebUIURL:     "http://homeassistant.local:8099/",
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
	d := newAddonDSWithClient(t, c)
	schema := addonDSSchemaFor(t, d)

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildAddonDSConfig(t, schema, want.Slug),
	}, &resp)

	if resp.Diagnostics.HasError() {
		t.Fatalf("Read: diagnostics = %v", resp.Diagnostics)
	}

	var state addonDSModel
	if diags := resp.State.Get(context.Background(), &state); diags.HasError() {
		t.Fatalf("State.Get: %v", diags)
	}
	for name, got := range map[string]string{
		"slug":          state.Slug.ValueString(),
		"name":          state.Name.ValueString(),
		"version":       state.Version.ValueString(),
		"state":         state.State.ValueString(),
		"boot":          state.Boot.ValueString(),
		"repository":    state.Repository.ValueString(),
		"hostname":      state.Hostname.ValueString(),
		"ingress_url":   state.IngressURL.ValueString(),
		"ingress_entry": state.IngressEntry.ValueString(),
		"webui_url":     state.WebUIURL.ValueString(),
	} {
		wantVal := map[string]string{
			"slug":          want.Slug,
			"name":          want.Name,
			"version":       want.Version,
			"state":         want.State,
			"boot":          want.Boot,
			"repository":    want.Repository,
			"hostname":      want.Hostname,
			"ingress_url":   want.IngressURL,
			"ingress_entry": want.IngressEntry,
			"webui_url":     want.WebUIURL,
		}[name]
		if got != wantVal {
			t.Errorf("%s = %q, want %q", name, got, wantVal)
		}
	}
	if !state.Started.ValueBool() {
		t.Errorf("started = false, want true")
	}
	if got := state.Options["log_level"].ValueString(); got != "info" {
		t.Errorf("options[log_level] = %q, want %q", got, "info")
	}

	var dns []string
	if diags := state.DNS.ElementsAs(context.Background(), &dns, false); diags.HasError() {
		t.Fatalf("DNS.ElementsAs: %v", diags)
	}
	if len(dns) != len(want.DNS) || dns[0] != want.DNS[0] || dns[1] != want.DNS[1] {
		t.Errorf("dns = %v, want %v", dns, want.DNS)
	}
}

// TestDataSourceRead_NotFoundReturnsDiagnostic asserts the 404
// branch. Unlike the Resource (CF-06: 404 → empty state so destroy
// is a no-op), a data source lookup for a missing add-on is an
// Error — the user asserted the add-on exists.
func TestDataSourceRead_NotFoundReturnsDiagnostic(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
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
	d := newAddonDSWithClient(t, c)
	schema := addonDSSchemaFor(t, d)

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildAddonDSConfig(t, schema, "missing"),
	}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Read(404): expected Error diagnostics, got none")
	}
	summary := resp.Diagnostics[0].Summary()
	if !strings.Contains(summary, "was not found at Bridge") {
		t.Errorf("Read(404): summary %q does not carry ErrNotFoundText", summary)
	}
	detail := resp.Diagnostics[0].Detail()
	if !strings.Contains(detail, "DOCS.md#troubleshooting-not-found") {
		t.Errorf("Read(404): detail %q missing the D-10 DOCS.md anchor", detail)
	}
}

// TestDataSourceRead_OtherErrorReturnsDiagnostic asserts the
// non-404 error path routes through diagnostics.MapError: a 502 +
// upstream_error surfaces the canonical per-code Summary text.
func TestDataSourceRead_OtherErrorReturnsDiagnostic(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
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
	d := newAddonDSWithClient(t, c)
	schema := addonDSSchemaFor(t, d)

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildAddonDSConfig(t, schema, "any"),
	}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Read(502): expected Error diagnostics, got none")
	}
	if !strings.Contains(resp.Diagnostics[0].Summary(), "Transient Supervisor failure") {
		t.Errorf("Read(502): summary %q does not carry the upstream_error text", resp.Diagnostics[0].Summary())
	}
}

// TestDataSourceRead_RequestIDInDetail is the D-11 correlation
// guard: every error diagnostic carries the Bridge's request_id in
// the Detail field so operators can grep the Bridge logs.
func TestDataSourceRead_RequestIDInDetail(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusLocked)
		_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
			ErrorCode: "locked",
			RequestID: "rid-locked-42",
		})
	}))
	defer srv.Close()

	c, err := client.NewClient(srv.URL, "test-bearer-token")
	if err != nil {
		t.Fatalf("client.NewClient: %v", err)
	}
	d := newAddonDSWithClient(t, c)
	schema := addonDSSchemaFor(t, d)

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildAddonDSConfig(t, schema, "busy"),
	}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Read(423): expected Error diagnostics, got none")
	}
	detail := resp.Diagnostics[0].Detail()
	if !strings.Contains(detail, "request_id: rid-locked-42") {
		t.Errorf("Read(423): detail %q missing `request_id: rid-locked-42` (D-11)", detail)
	}
	// PITFALLS S-1: the bearer token must never reach a diagnostic.
	if strings.Contains(detail, "test-bearer-token") || strings.Contains(resp.Diagnostics[0].Summary(), "test-bearer-token") {
		t.Errorf("bearer token leaked into diagnostic: summary=%q detail=%q", resp.Diagnostics[0].Summary(), detail)
	}
}

// TestDataSourceRead_OmittedD01FieldsStayEmpty is the D-02
// pass-through guard for the data source: a Supervisor payload
// that omits the five new fields decodes to empty strings + a null
// DNS list, with no Provider-side synthesis.
func TestDataSourceRead_OmittedD01FieldsStayEmpty(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"slug":"legacy","name":"Legacy","version":"0.1.0",` +
			`"state":"stopped","started":false,"boot":"manual","repository":"core"}`))
	}))
	defer srv.Close()

	c, err := client.NewClient(srv.URL, "test-bearer-token")
	if err != nil {
		t.Fatalf("client.NewClient: %v", err)
	}
	d := newAddonDSWithClient(t, c)
	schema := addonDSSchemaFor(t, d)

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildAddonDSConfig(t, schema, "legacy"),
	}, &resp)

	if resp.Diagnostics.HasError() {
		t.Fatalf("Read: diagnostics = %v", resp.Diagnostics)
	}
	var state addonDSModel
	if diags := resp.State.Get(context.Background(), &state); diags.HasError() {
		t.Fatalf("State.Get: %v", diags)
	}
	for name, got := range map[string]string{
		"hostname":      state.Hostname.ValueString(),
		"ingress_url":   state.IngressURL.ValueString(),
		"ingress_entry": state.IngressEntry.ValueString(),
		"webui_url":     state.WebUIURL.ValueString(),
	} {
		if got != "" {
			t.Errorf("%s = %q, want empty string (D-02 pass-through)", name, got)
		}
	}
	if !state.DNS.IsNull() {
		t.Errorf("dns = %v, want null list", state.DNS)
	}
}

// TestDataSourceConfigure_WrongClientType asserts the type
// assertion guard: a non-*client.Client ProviderData surfaces a
// diagnostic rather than panicking.
func TestDataSourceConfigure_WrongClientType(t *testing.T) {
	d := tfdatasource.NewAddonDataSource().(datasource.DataSourceWithConfigure)
	var resp datasource.ConfigureResponse
	d.Configure(context.Background(), datasource.ConfigureRequest{ProviderData: "not-a-client"}, &resp)
	if !resp.Diagnostics.HasError() {
		t.Errorf("Configure(string): expected Error diagnostics, got none")
	}
}

// TestDataSourceConfigure_NilProviderDataIsSilent asserts the
// framework's validate-pass contract: a nil ProviderData (before
// Provider.Configure has run) must NOT emit a diagnostic, or every
// `tofu validate` would report a spurious error.
func TestDataSourceConfigure_NilProviderDataIsSilent(t *testing.T) {
	d := tfdatasource.NewAddonDataSource().(datasource.DataSourceWithConfigure)
	var resp datasource.ConfigureResponse
	d.Configure(context.Background(), datasource.ConfigureRequest{ProviderData: nil}, &resp)
	if resp.Diagnostics.HasError() {
		t.Errorf("Configure(nil): expected no diagnostics, got %v", resp.Diagnostics)
	}
}

// TestDataSourceRead_NoClientReturnsDiagnostic asserts the
// defensive guard in Read when the data source was never
// configured (an internal error, but must not panic).
func TestDataSourceRead_NoClientReturnsDiagnostic(t *testing.T) {
	d := tfdatasource.NewAddonDataSource()
	schema := addonDSSchemaFor(t, d)

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildAddonDSConfig(t, schema, "any"),
	}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Read(no client): expected Error diagnostics, got none")
	}
}

// Compile-time guard: the data source satisfies the framework
// interfaces the Provider's DataSources() slice relies on.
var (
	_ datasource.DataSource = tfdatasource.NewAddonDataSource()
)
