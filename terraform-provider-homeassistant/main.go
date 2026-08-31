// Package main is the entrypoint for the terraform-provider-homeassistant
// OpenTofu/Terraform provider. Phase 9 ships a stub that imports the
// shared contract types from terraform-bridge/contract (via the `replace`
// directive in go.mod); Phase 13 fills in the resource and data-source
// bodies without changing this file's structure or the package layout.
package main

import (
	"context"
	"log"

	"github.com/hashicorp/terraform-plugin-framework/providerserver"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/provider/schema"

	"terraform-bridge/contract"
)

// Version is the Provider version. In Phase 9 it is a compile-time
// constant; the Bridge/Provider version sync enforced by
// internal/validate-versions.sh guarantees it matches the Bridge X.Y.Z.
const Version = "0.0.0"

func main() {
	err := providerserver.Serve(
		context.Background(),
		newStubProvider,
		providerserver.ServeOpts{
			Address: "registry.terraform.io/akentner/homeassistant",
		},
	)
	if err != nil {
		log.Fatal(err)
	}
}

// newStubProvider constructs the Phase 9 placeholder. Phase 13 replaces
// this with a real provider that calls Bridge /v1/version (PROV-03) and
// registers the homeassistant_addon resource plus the two data sources
// (PROV-02/11/12).
func newStubProvider() provider.Provider {
	return &stubProvider{}
}

// stubProvider is the Phase 9 placeholder. Embedding provider.Provider
// satisfies the interface's Metadata/Configure/DataSources/Resources
// methods at compile time (the embedded nil interface would panic if any
// were called at runtime, but Phase 9 only serves the schema). Phase 13
// replaces the embedding with explicit implementations.
type stubProvider struct {
	provider.Provider
}

// Schema satisfies provider.Provider. Phase 9 returns an empty schema
// because no resource types have been declared yet — the Provider is a
// no-op that the protocol layer requires only to be loadable. Phase 13
// fills this in.
func (p *stubProvider) Schema(_ context.Context, _ provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = schema.Schema{}
}

// References one of the shared contract types so the `replace` directive's
// drift-detection is exercised at build time. Phase 13 replaces this with
// a real Configure handshake consuming contract.VersionHandshake.
var _ contract.VersionHandshake