output "cluster_id" {
  value = oci_containerengine_cluster.this.id
}

output "kubeconfig_command" {
  description = "Run this yourself (founder) to write a kubeconfig for the new cluster."
  value       = "oci ce cluster create-kubeconfig --cluster-id ${oci_containerengine_cluster.this.id} --region ${var.region} --token-version 2.0.0 --kube-endpoint PUBLIC_ENDPOINT --profile ${var.oci_profile} --auth security_token"
}

output "backup_bucket" {
  value = oci_objectstorage_bucket.backup.name
}

output "backup_s3_endpoint_hint" {
  description = "Object Storage S3-compatibility inputs: the namespace and the region."
  value       = "namespace=${data.oci_objectstorage_namespace.this.namespace} region=${var.region}"
}

output "vault_secret_ids" {
  description = "Place each real value in the console (Identity > Vault > secret > new version)."
  value       = { for k, s in oci_vault_secret.this : k => s.id }
}
