path "f01/data/*" {
  capabilities = ["create", "update", "read"]
}
path "f01/metadata/*" {
  capabilities = ["read"]
}
path "auth/approle/role/f01-cli/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/f01-cli/secret-id" {
  capabilities = ["update"]
}

path "auth/approle/role/f01-dev-day/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/f01-dev-day/secret-id" {
  capabilities = ["update"]
}
