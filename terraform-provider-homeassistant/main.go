// Package main is the entrypoint for the terraform-provider-homeassistant
// OpenTofu/Terraform provider. Phase 13 Plan 01 replaces the Phase 9
// stub with a real providerserver.Serve wired to the Provider in
// internal/provider/.
package main

import (
	"context"
	"log"

	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/providerserver"

	tfprovider "terraform-provider-homeassistant/internal/provider"
)

// Version is the Provider version. In Phase 13 Plan 01 this is a
// compile-time constant; Phase 14 wires the 3-file versioning sync
// (CF-14) so this constant tracks the same value as Bridge's
// build.yaml.
const Version = "0.0.0"

func main() {
	err := providerserver.Serve(
		context.Background(),
		newProvider,
		providerserver.ServeOpts{
			// Address must follow hostname/namespace/type form
			// (validated by ServeOpts.validate). The Provider's
			// Metadata returns TypeName = "homeassistant" which
			// becomes the `type` segment; the namespace is
			// `akentner` matching the GitHub org that publishes
			// the provider; the host `registry.terraform.io` is
			// the public HashiCorp registry.
			Address: "registry.terraform.io/akentner/homeassistant",
		},
	)
	if err != nil {
		log.Fatal(err)
	}
}

// newProvider returns a fresh Provider implementation on every
// invocation. The framework calls this constructor for each
// Provider RPC; constructing on every call keeps state out of the
// Provider instance (the Configure handshake re-creates the
// configured Client each time, so a stale instance cannot leak
// across RPCs).
func newProvider() provider.Provider {
	return tfprovider.New()
}
