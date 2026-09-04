package provider_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	fwprovider "github.com/hashicorp/terraform-plugin-framework/provider/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/tfsdk"
	"github.com/hashicorp/terraform-plugin-go/tftypes"

	"terraform-bridge/contract"

	tfprovider "terraform-provider-homeassistant/internal/provider"
)

// schemaResponseFor invokes the Provider's Schema method and
// returns the schema it produced. Helper used by every test in
// this file so the Schema method only needs to be wired once.
func schemaResponseFor(t *testing.T, p provider.Provider) fwprovider.Schema {
	t.Helper()
	var resp provider.SchemaResponse
	p.Schema(context.Background(), provider.SchemaRequest{}, &resp)
	if resp.Diagnostics.HasError() {
		t.Fatalf("Provider.Schema returned error diagnostics: %v", resp.Diagnostics)
	}
	return resp.Schema
}

// buildConfig constructs a tfsdk.Config from the supplied
// endpoint + bearer_token values using the Provider's schema.
// Mirrors how the Terraform CLI would populate the Provider
// configuration block in production. The Raw tftypes.Value is
// built directly so the test does not depend on
// terraform-plugin-testing's acctest helpers (a heavier
// dependency than Plan 01 needs).
func buildConfig(t *testing.T, schema fwprovider.Schema, endpoint, bearerToken string) tfsdk.Config {
	t.Helper()
	// Build the tftypes.Object that backs the Config. The schema
	// declares two String attributes; both must be present (the
	// schema marks them Required) so the Raw object carries both
	// keys.
	rawType := tftypes.Object{
		AttributeTypes: map[string]tftypes.Type{
			"endpoint":     tftypes.String,
			"bearer_token": tftypes.String,
		},
	}
	raw := tftypes.NewValue(rawType, map[string]tftypes.Value{
		"endpoint":     tftypes.NewValue(tftypes.String, endpoint),
		"bearer_token": tftypes.NewValue(tftypes.String, bearerToken),
	})
	return tfsdk.Config{
		Raw:    raw,
		Schema: schema,
	}
}

// TestProvider_Metadata asserts the type name + version returned
// by Metadata. Both fields are stable contract for downstream
// Resource + DataSource addresses.
func TestProvider_Metadata(t *testing.T) {
	p := tfprovider.New()
	var resp provider.MetadataResponse
	p.Metadata(context.Background(), provider.MetadataRequest{}, &resp)

	if resp.TypeName != "homeassistant" {
		t.Errorf("TypeName = %q, want %q", resp.TypeName, "homeassistant")
	}
	if resp.Version != tfprovider.Version {
		t.Errorf("Version = %q, want %q", resp.Version, tfprovider.Version)
	}
}

// TestProvider_Schema_EndpointRequired asserts the endpoint
// argument is declared Required in the Provider schema.
func TestProvider_Schema_EndpointRequired(t *testing.T) {
	p := tfprovider.New()
	schema := schemaResponseFor(t, p)

	endpoint, ok := schema.Attributes["endpoint"]
	if !ok {
		t.Fatalf("Schema.Attributes has no 'endpoint' key")
	}
	if !endpoint.IsRequired() {
		t.Errorf("endpoint attribute is not Required (Required = %v)", endpoint.IsRequired())
	}
}

// TestProvider_Schema_BearerTokenSensitive asserts the
// bearer_token argument is marked Sensitive so Terraform hides it
// from plan output (CF-03 + PITFALLS S-1).
func TestProvider_Schema_BearerTokenSensitive(t *testing.T) {
	p := tfprovider.New()
	schema := schemaResponseFor(t, p)

	token, ok := schema.Attributes["bearer_token"]
	if !ok {
		t.Fatalf("Schema.Attributes has no 'bearer_token' key")
	}
	if !token.IsSensitive() {
		t.Errorf("bearer_token attribute is not Sensitive (Sensitive = %v)", token.IsSensitive())
	}
}

// fakeVersionServer stands up an httptest.Server that responds to
// GET /v1/version with the given handshake body. Other paths
// return 404. The returned URL is the server's base.
func fakeVersionServer(t *testing.T, hs contract.VersionHandshake) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/version" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(hs)
	}))
}

// TestProvider_Configure_Success drives a happy-path Configure:
// the fake server returns a valid handshake, the Provider
// constructs a *client.Client, calls GetVersion, verifies the
// version window, and stashes the configured Client in
// resp.ResourceData (the framework's per-Resource handoff).
func TestProvider_Configure_Success(t *testing.T) {
	srv := fakeVersionServer(t, contract.VersionHandshake{
		BridgeVersion:      "0.5.0",
		SchemaVersion:      "1.0.0",
		MinProviderVersion: "0.0.0",
		MaxProviderVersion: "1.999.0",
	})
	defer srv.Close()

	p := tfprovider.New()
	schema := schemaResponseFor(t, p)
	config := buildConfig(t, schema, srv.URL, "test-bearer-token")

	var resp provider.ConfigureResponse
	p.Configure(context.Background(), provider.ConfigureRequest{Config: config}, &resp)

	if resp.Diagnostics.HasError() {
		t.Fatalf("Configure: diagnostics = %v", resp.Diagnostics)
	}
	if resp.ResourceData == nil {
		t.Fatalf("Configure: resp.ResourceData is nil (Provider must stash the Client for downstream Resources)")
	}
}

// TestProvider_Configure_VersionBelowMin asserts the version
// out-of-window path. The fake server reports min_provider_version
// = "99.99.0" which is far above the Provider's "0.0.0" stub.
// Configure must refuse with a typed Error diagnostic.
func TestProvider_Configure_VersionBelowMin(t *testing.T) {
	srv := fakeVersionServer(t, contract.VersionHandshake{
		BridgeVersion:      "0.5.0",
		SchemaVersion:      "1.0.0",
		MinProviderVersion: "99.99.0",
		MaxProviderVersion: "1.999.0",
	})
	defer srv.Close()

	p := tfprovider.New()
	schema := schemaResponseFor(t, p)
	config := buildConfig(t, schema, srv.URL, "test-bearer-token")

	var resp provider.ConfigureResponse
	p.Configure(context.Background(), provider.ConfigureRequest{Config: config}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Configure(version_below_min): expected Error diagnostics, got none")
	}
	summary := resp.Diagnostics[0].Summary()
	if !strings.Contains(summary, "too old") && !strings.Contains(summary, "below") {
		t.Errorf("Configure(version_below_min): summary %q does not mention 'too old' or 'below'", summary)
	}
	if resp.ResourceData != nil {
		t.Errorf("Configure(version_below_min): ResourceData must be nil on failure, got %v", resp.ResourceData)
	}
}

// TestProvider_Configure_VersionAboveMax asserts the
// max_provider_version ceiling path. The fake server reports
// max_provider_version = "0.0.0" which is at-or-below the
// Provider's "0.0.0". Configure must refuse with a typed Error
// diagnostic.
func TestProvider_Configure_VersionAboveMax(t *testing.T) {
	srv := fakeVersionServer(t, contract.VersionHandshake{
		BridgeVersion:      "0.5.0",
		SchemaVersion:      "1.0.0",
		MinProviderVersion: "0.0.0",
		MaxProviderVersion: "0.0.0",
	})
	defer srv.Close()

	p := tfprovider.New()
	schema := schemaResponseFor(t, p)
	config := buildConfig(t, schema, srv.URL, "test-bearer-token")

	var resp provider.ConfigureResponse
	p.Configure(context.Background(), provider.ConfigureRequest{Config: config}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Configure(version_above_max): expected Error diagnostics, got none")
	}
	summary := resp.Diagnostics[0].Summary()
	if !strings.Contains(summary, "too new") && !strings.Contains(summary, "above") {
		t.Errorf("Configure(version_above_max): summary %q does not mention 'too new' or 'above'", summary)
	}
}

// TestProvider_Configure_ClientConstructionFailure asserts the
// failure path where the user's `endpoint` argument fails the
// client.NewClient URL parser. Configure must surface an Error
// diagnostic rather than panicking.
func TestProvider_Configure_ClientConstructionFailure(t *testing.T) {
	p := tfprovider.New()
	schema := schemaResponseFor(t, p)
	config := buildConfig(t, schema, "://no-scheme", "test-bearer-token")

	var resp provider.ConfigureResponse
	p.Configure(context.Background(), provider.ConfigureRequest{Config: config}, &resp)

	if !resp.Diagnostics.HasError() {
		t.Fatalf("Configure(bad-url): expected Error diagnostic, got none")
	}
}

// TestProvider_Configure_BearerTokenNotInDiagnostic is the
// PITFALLS S-1 + T-13-04 regression guard for the Provider
// Configure. Across the failure paths (Client construction
// failure, version window refusal) the bearer token value must
// NEVER appear in resp.Diagnostics.
func TestProvider_Configure_BearerTokenNotInDiagnostic(t *testing.T) {
	const bearer = "do-not-leak-bearer-token-XYZ"
	scenarios := []struct {
		name     string
		hs       contract.VersionHandshake
		endpoint string
	}{
		{
			name: "version_above_max",
			hs: contract.VersionHandshake{
				BridgeVersion: "0.5.0", SchemaVersion: "1.0.0",
				MinProviderVersion: "0.0.0", MaxProviderVersion: "0.0.0",
			},
			endpoint: "REPLACED_AT_TEST_RUN_TIME",
		},
		{
			name: "version_below_min",
			hs: contract.VersionHandshake{
				BridgeVersion: "0.5.0", SchemaVersion: "1.0.0",
				MinProviderVersion: "99.99.0", MaxProviderVersion: "1.999.0",
			},
			endpoint: "REPLACED_AT_TEST_RUN_TIME",
		},
		{
			name:     "bad_url",
			hs:       contract.VersionHandshake{},
			endpoint: "://no-scheme",
		},
	}

	for _, sc := range scenarios {
		t.Run(sc.name, func(t *testing.T) {
			srv := fakeVersionServer(t, sc.hs)
			defer srv.Close()

			endpoint := sc.endpoint
			if endpoint == "REPLACED_AT_TEST_RUN_TIME" {
				endpoint = srv.URL
			}

			p := tfprovider.New()
			schema := schemaResponseFor(t, p)
			config := buildConfig(t, schema, endpoint, bearer)

			var resp provider.ConfigureResponse
			p.Configure(context.Background(), provider.ConfigureRequest{Config: config}, &resp)

			if !resp.Diagnostics.HasError() {
				t.Fatalf("scenario %s: expected error diagnostics, got none", sc.name)
			}
			for _, d := range resp.Diagnostics {
				if strings.Contains(d.Summary(), bearer) || strings.Contains(d.Detail(), bearer) {
					t.Errorf("scenario %s: diagnostic leaked bearer token: Summary=%q Detail=%q",
						sc.name, d.Summary(), d.Detail())
				}
			}
		})
	}
}

// TestProvider_Resources_ReturnsAddonResource asserts the
// Provider's Resources() slice contains exactly one Resource —
// the homeassistant_addon resource. The slice length is the
// primary assertion; the Resource's identity is verified by
// calling its Metadata method and checking the type name.
func TestProvider_Resources_ReturnsAddonResource(t *testing.T) {
	p := tfprovider.New()
	factories := p.Resources(context.Background())
	if len(factories) != 1 {
		t.Fatalf("Resources(): len = %d, want 1", len(factories))
	}
	r := factories[0]()
	req := resource.MetadataRequest{ProviderTypeName: "homeassistant"}
	var resp resource.MetadataResponse
	r.Metadata(context.Background(), req, &resp)
	if resp.TypeName != "homeassistant_addon" {
		t.Errorf("Resource.TypeName = %q, want %q", resp.TypeName, "homeassistant_addon")
	}
}

// TestProvider_DataSources_ReturnsBothDataSources asserts the
// Provider's DataSources() slice contains exactly two DataSources
// — homeassistant_addon + homeassistant_supervisor_info per
// PROV-11 + PROV-12. Plan 01 ships both as thin stubs; Plan 03
// fills in the schemas + Read bodies.
func TestProvider_DataSources_ReturnsBothDataSources(t *testing.T) {
	p := tfprovider.New()
	factories := p.DataSources(context.Background())
	if len(factories) != 2 {
		t.Fatalf("DataSources(): len = %d, want 2", len(factories))
	}
	ds1 := factories[0]()
	ds2 := factories[1]()
	req := datasource.MetadataRequest{ProviderTypeName: "homeassistant"}
	var resp1, resp2 datasource.MetadataResponse
	ds1.Metadata(context.Background(), req, &resp1)
	ds2.Metadata(context.Background(), req, &resp2)
	wantNames := []string{"homeassistant_addon", "homeassistant_supervisor_info"}
	gotNames := []string{resp1.TypeName, resp2.TypeName}
	for _, want := range wantNames {
		found := false
		for _, got := range gotNames {
			if got == want {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("DataSources type names = %v, want both %v", gotNames, wantNames)
		}
	}
}
