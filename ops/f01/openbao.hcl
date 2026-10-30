ui = false
disable_mlock = true
api_addr = "https://openbao:8200"
cluster_addr = "https://openbao:8201"
storage "raft" {
  path = "/bao/data"
  node_id = "ragdev01-f01"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_cert_file = "/bao/tls/server.crt"
  tls_key_file = "/bao/tls/server.key"
  tls_min_version = "tls13"
  tls_acme_ca_directory = ""
}
