# Least privilege: only statements with a consumer in this profile. The kubernetes secrets are written by Tofu on the
# founder's machine, not by pods, so workers get no vault access.

# Consumer: the backup bucket (lifecycle rule execution and the bucket's customer-managed key). Lets Object Storage apply the lifecycle rule and use the vault key for the bucket.
resource "oci_identity_policy" "object_storage_service" {
  provider       = oci.home
  compartment_id = var.compartment_ocid
  name           = "${var.name_prefix}-objectstorage-service"
  description    = "Object Storage service: lifecycle rules and key use for the backup bucket."
  statements = [
    "Allow service objectstorage-${var.region} to manage object-family in compartment id ${var.compartment_ocid} where target.bucket.name = '${var.backup_bucket_name}'",
    "Allow service objectstorage-${var.region} to use keys in compartment id ${var.compartment_ocid} where target.key.id = '${oci_kms_key.this.id}'",
  ]
}

# The identity CNPG uses for S3-compatible access to the backup bucket. Its customer secret key is created by the
# founder in the console (shown once) and placed in the vault. It reaches the cluster either through
# k8s_secret_bindings (then it passes through the Terraform state, see the README) or by hand with kubectl (then it
# does not).
resource "oci_identity_user" "backup" {
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.name_prefix}-backup"
  description    = "Database backup writer (S3-compatible access)."
  email          = null
}

resource "oci_identity_group" "backup" {
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.name_prefix}-backup"
  description    = "Database backup writers."
}

resource "oci_identity_user_group_membership" "backup" {
  provider = oci.home
  user_id  = oci_identity_user.backup.id
  group_id = oci_identity_group.backup.id
}

# Consumer: CNPG backups, which use this user's S3-compatible keys. Objects of the one backup bucket only.
resource "oci_identity_policy" "backup" {
  provider       = oci.home
  compartment_id = var.compartment_ocid
  name           = "${var.name_prefix}-backup-bucket"
  description    = "Backup group: objects of the backup bucket only."
  statements = [
    "Allow group ${oci_identity_group.backup.name} to manage objects in compartment id ${var.compartment_ocid} where target.bucket.name = '${var.backup_bucket_name}'",
    "Allow group ${oci_identity_group.backup.name} to read buckets in compartment id ${var.compartment_ocid} where target.bucket.name = '${var.backup_bucket_name}'",
  ]
}
