# Administrative F01 CLI, never a tenant or public API identity.
path "f01/data/*" {
  capabilities = ["create", "update", "read"]
}
path "f01/metadata/*" {
  capabilities = ["read"]
}
