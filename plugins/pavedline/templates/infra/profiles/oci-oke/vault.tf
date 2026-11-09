# Secret SHELLS. Terraform creates each secret with a placeholder and never overwrites it afterwards: the founder places
# the real value in the console, and the vault stays authoritative.

resource "oci_kms_vault" "this" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.name_prefix}-vault"
  vault_type     = "DEFAULT"
}

resource "oci_kms_key" "this" {
  compartment_id      = var.compartment_ocid
  display_name        = "${var.name_prefix}-master"
  management_endpoint = oci_kms_vault.this.management_endpoint
  protection_mode     = var.kms_protection_mode
  key_shape {
    algorithm = "AES"
    length    = 32
  }
}

resource "oci_vault_secret" "this" {
  for_each = var.vault_secret_names

  compartment_id = var.compartment_ocid
  vault_id       = oci_kms_vault.this.id
  key_id         = oci_kms_key.this.id
  secret_name    = "${var.name_prefix}-${each.key}"
  description    = "Placeholder. The real value is placed in the console by the founder."

  secret_content {
    content_type = "BASE64"
    content      = base64encode("placeholder-set-in-console")
  }

  lifecycle {
    ignore_changes = [secret_content]
  }
}

# Every (Kubernetes Secret, data key) pair of the bindings, each reading its vault secret's current version.
locals {
  bound_pairs = var.enable_cluster_resources ? merge([
    for name, b in var.k8s_secret_bindings : {
      for k, vault_secret in b.keys : "${name}/${k}" => { secret = name, key = k, vault_secret = vault_secret }
    }
  ]...) : {}
}

data "oci_secrets_secretbundle" "bound" {
  for_each = local.bound_pairs

  secret_id = oci_vault_secret.this[each.value.vault_secret].id
  stage     = "CURRENT"
}

# The values bound here end up in the Terraform state (and in plan.out): see the README for how to protect it, or
# create the Secret by hand with kubectl and leave it out of the bindings.
resource "kubernetes_secret_v1" "from_vault" {
  for_each = var.enable_cluster_resources ? var.k8s_secret_bindings : {}

  metadata {
    name      = each.key
    namespace = each.value.namespace
  }
  lifecycle {
    precondition {
      condition = alltrue([
        for k, vault_secret in each.value.keys :
        base64decode(data.oci_secrets_secretbundle.bound["${each.key}/${k}"].secret_bundle_content[0].content) != "placeholder-set-in-console"
      ])
      error_message = "A vault secret in this binding still holds the placeholder. Place the real value in the console first."
    }
  }
  data = {
    for k, vault_secret in each.value.keys :
    k => base64decode(data.oci_secrets_secretbundle.bound["${each.key}/${k}"].secret_bundle_content[0].content)
  }
}
