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

// supervisorInfoDSModel mirrors every attribute of the
// homeassistant_supervisor_info data source schema (CF-11: the
// body shape mirrors contract.BridgeInfo exactly).
type supervisorInfoDSModel struct {
	BridgeVersion     types.String `tfsdk:"bridge_version"`
	SupervisorVersion types.String `tfsdk:"supervisor_version"`
	UptimeSeconds     types.Int64  `tfsdk:"uptime_seconds"`
	StateFilePath     types.String `tfsdk:"state_file_path"`
}

// supervisorInfoDSType returns the tftypes.Object matching the
// data source's schema. The data source takes no arguments, so the
// Config carries only null Computed values.
func supervisorInfoDSType() tftypes.Object {
	return tftypes.Object{
		AttributeTypes: map[string]tftypes.Type{
			"bridge_version":     tftypes.String,
			"supervisor_version": tftypes.String,
			"uptime_seconds":     tftypes.Number,
			"state_file_path":    tftypes.String,
		},
	}
}

// buildSupervisorInfoDSConfig builds the argument-less tfsdk.Config
// the framework hands to Read.
func buildSupervisorInfoDSConfig(t *testing.T, schema fwdatasource.Schema) tfsdk.Config {
	t.Helper()
	return tfsdk.Config{
		Raw: tftypes.NewValue(supervisorInfoDSType(), map[string]tftypes.Value{
			"bridge_version":     tftypes.NewValue(tftypes.String, nil),
			"supervisor_version": tftypes.NewValue(tftypes.String, nil),
			"uptime_seconds":     tftypes.NewValue(tftypes.Number, nil),
			"state_file_path":    tftypes.NewValue(tftypes.String, nil),
		}),
		Schema: schema,
	}
}

// newSupervisorInfoDSWithClient constructs the data source and
// wires the Client through Configure.
func newSupervisorInfoDSWithClient(t *testing.T, c *client.Client) datasource.DataSource {
	t.Helper()
	d := tfdatasource.NewSupervisorInfoDataSource()
	cfg, ok := d.(datasource.DataSourceWithConfigure)
	if !ok {
		t.Fatalf("supervisor_info data source does not implement DataSourceWithConfigure")
	}
	var resp datasource.ConfigureResponse
	cfg.Configure(context.Background(), datasource.ConfigureRequest{ProviderData: c}, &resp)
	if resp.Diagnostics.HasError() {
		t.Fatalf("Configure: %v", resp.Diagnostics)
	}
	return d
}

// TestDataSourceSchema_NoRequiredAttributes asserts the PROV-12
// shape: zero Required attributes (the data source takes no
// arguments) and exactly the four Computed attributes mirroring
// contract.BridgeInfo per CF-11.
func TestDataSourceSchema_NoRequiredAttributes(t *testing.T) {
	d := tfdatasource.NewSupervisorInfoDataSource()
	var schemaResp datasource.SchemaResponse
	d.Schema(context.Background(), datasource.SchemaRequest{}, &schemaResp)
	if schemaResp.Diagnostics.HasError() {
		t.Fatalf("Schema: %v", schemaResp.Diagnostics)
	}
	schema := schemaResp.Schema

	var requiredCount int
	for name, attr := range schema.Attributes {
		if attr.IsRequired() {
			requiredCount++
			t.Errorf("attribute %q is Required; the data source takes no arguments (PROV-12)", name)
		}
	}
	if requiredCount != 0 {
		t.Errorf("Required attribute count = %d, want 0", requiredCount)
	}

	want := []string{"bridge_version", "supervisor_version", "uptime_seconds", "state_file_path"}
	if len(schema.Attributes) != len(want) {
		t.Errorf("attribute count = %d, want %d (%v)", len(schema.Attributes), len(want), want)
	}
	for _, name := range want {
		attr, ok := schema.Attributes[name]
		if !ok {
			t.Errorf("Schema.Attributes has no %q key", name)
			continue
		}
		if !attr.IsComputed() {
			t.Errorf("%s attribute is not Computed (Computed = %v)", name, attr.IsComputed())
		}
	}

	// uptime_seconds must be Int64 so lifecycle.precondition
	// comparisons parse it without coercion (CF-11).
	if _, ok := schema.Attributes["uptime_seconds"].(fwdatasource.Int64Attribute); !ok {
		t.Errorf("uptime_seconds is not an Int64Attribute (got %T)", schema.Attributes["uptime_seconds"])
	}
}

// TestSupervisorInfoDataSourceRead_Success drives the happy path:
// the fake Bridge returns a BridgeInfo body and Read lands all four
// attributes in resp.State.
//
// (Named with the SupervisorInfo prefix rather than the plan's
// literal `TestDataSourceRead_Success` because both data source
// test files share the `datasource_test` package, where that name
// is already taken by the homeassistant_addon test.)
func TestSupervisorInfoDataSourceRead_Success(t *testing.T) {
	want := contract.BridgeInfo{
		BridgeVersion:     "0.3.0",
		SupervisorVersion: "2026.08.1",
		UptimeSeconds:     4242,
		StateFilePath:     "/data/terraform.tfstate",
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/info" {
			t.Errorf("server: path = %q, want %q", r.URL.Path, "/v1/info")
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
	d := newSupervisorInfoDSWithClient(t, c)

	var schemaResp datasource.SchemaResponse
	d.Schema(context.Background(), datasource.SchemaRequest{}, &schemaResp)
	schema := schemaResp.Schema

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildSupervisorInfoDSConfig(t, schema),
	}, &resp)

	if resp.Diagnostics.HasError() {
		t.Fatalf("Read: diagnostics = %v", resp.Diagnostics)
	}

	var state supervisorInfoDSModel
	if diags := resp.State.Get(context.Background(), &state); diags.HasError() {
		t.Fatalf("State.Get: %v", diags)
	}
	if got := state.BridgeVersion.ValueString(); got != want.BridgeVersion {
		t.Errorf("bridge_version = %q, want %q", got, want.BridgeVersion)
	}
	if got := state.SupervisorVersion.ValueString(); got != want.SupervisorVersion {
		t.Errorf("supervisor_version = %q, want %q", got, want.SupervisorVersion)
	}
	if got := state.UptimeSeconds.ValueInt64(); got != want.UptimeSeconds {
		t.Errorf("uptime_seconds = %d, want %d", got, want.UptimeSeconds)
	}
	if got := state.StateFilePath.ValueString(); got != want.StateFilePath {
		t.Errorf("state_file_path = %q, want %q", got, want.StateFilePath)
	}
}

// TestSupervisorInfoDataSourceRead_ErrorReturnsDiagnostic asserts a
// Bridge error surfaces through diagnostics.MapError with the
// canonical Summary text plus the D-11 request_id correlation in
// the Detail. (Prefixed for the same package-collision reason as
// TestSupervisorInfoDataSourceRead_Success above.)
func TestSupervisorInfoDataSourceRead_ErrorReturnsDiagnostic(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
			ErrorCode: "upstream_error",
			RequestID: "rid-info-502",
		})
	}))
	defer srv.Close()

	c, err := client.NewClient(srv.URL, "test-bearer-token")
	if err != nil {
		t.Fatalf("client.NewClient: %v", err)
	}
	d := newSupervisorInfoDSWithClient(t, c)

	var schemaResp datasource.SchemaResponse
	d.Schema(context.Background(), datasource.SchemaRequest{}, &schemaResp)
	schema := schemaResp.Schema

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildSupervisorInfoDSConfig(t, schema),
	}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Read(502): expected Error diagnostics, got none")
	}
	if !strings.Contains(resp.Diagnostics[0].Summary(), "Transient Supervisor failure") {
		t.Errorf("Read(502): summary %q does not carry the upstream_error text", resp.Diagnostics[0].Summary())
	}
	detail := resp.Diagnostics[0].Detail()
	if !strings.Contains(detail, "request_id: rid-info-502") {
		t.Errorf("Read(502): detail %q missing `request_id: rid-info-502` (D-11)", detail)
	}
	// PITFALLS S-1: the bearer token must never reach a diagnostic.
	if strings.Contains(detail, "test-bearer-token") {
		t.Errorf("bearer token leaked into diagnostic detail: %q", detail)
	}
}

// TestSupervisorInfoConfigure_WrongClientType asserts the type
// assertion guard.
func TestSupervisorInfoConfigure_WrongClientType(t *testing.T) {
	d := tfdatasource.NewSupervisorInfoDataSource().(datasource.DataSourceWithConfigure)
	var resp datasource.ConfigureResponse
	d.Configure(context.Background(), datasource.ConfigureRequest{ProviderData: 42}, &resp)
	if !resp.Diagnostics.HasError() {
		t.Errorf("Configure(int): expected Error diagnostics, got none")
	}
}

// TestSupervisorInfoRead_NoClientReturnsDiagnostic asserts the
// defensive unconfigured guard in Read.
func TestSupervisorInfoRead_NoClientReturnsDiagnostic(t *testing.T) {
	d := tfdatasource.NewSupervisorInfoDataSource()
	var schemaResp datasource.SchemaResponse
	d.Schema(context.Background(), datasource.SchemaRequest{}, &schemaResp)

	var resp datasource.ReadResponse
	resp.State = tfsdk.State{Schema: schemaResp.Schema}
	d.Read(context.Background(), datasource.ReadRequest{
		Config: buildSupervisorInfoDSConfig(t, schemaResp.Schema),
	}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Read(no client): expected Error diagnostics, got none")
	}
}

// TestSupervisorInfoMetadata asserts the data source type name so
// the `data "homeassistant_supervisor_info"` address stays stable.
func TestSupervisorInfoMetadata(t *testing.T) {
	d := tfdatasource.NewSupervisorInfoDataSource()
	var resp datasource.MetadataResponse
	d.Metadata(context.Background(), datasource.MetadataRequest{ProviderTypeName: "homeassistant"}, &resp)
	if resp.TypeName != "homeassistant_supervisor_info" {
		t.Errorf("TypeName = %q, want %q", resp.TypeName, "homeassistant_supervisor_info")
	}
}

// Compile-time guard: the data source satisfies the framework
// interfaces the Provider's DataSources() slice relies on.
var (
	_ datasource.DataSource = tfdatasource.NewSupervisorInfoDataSource()
)
