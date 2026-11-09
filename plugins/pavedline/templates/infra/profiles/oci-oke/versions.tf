# Plain HCL: `tofu` (OpenTofu, MPL-2.0; what Pavedline's CI validates with) and `terraform` both accept it.
# Providers are pinned exactly. URLs and dates: SOURCES.md.
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "= 9.10.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "= 3.3.0"
    }
  }

  # Backend left local on purpose. State holds secret material (the vault bundle read below), so keep it off shared
  # disks; move it to a remote backend only when the founder chooses one, and never put backend credentials in this repo.
  backend "local" {}
}

provider "oci" {
  region              = var.region
  auth                = var.oci_auth
  config_file_profile = var.oci_profile
}

# IAM, budgets and tag namespaces live in the tenancy's home region.
provider "oci" {
  alias               = "home"
  region              = var.home_region
  auth                = var.oci_auth
  config_file_profile = var.oci_profile
}

# Talks to the cluster this profile creates. Nothing is read from it until enable_cluster_resources is true.
provider "kubernetes" {
  host                   = local.cluster_host
  cluster_ca_certificate = local.cluster_ca
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "oci"
    args = [
      "ce", "cluster", "generate-token",
      "--cluster-id", oci_containerengine_cluster.this.id,
      "--region", var.region,
      "--profile", var.oci_profile,
      "--auth", var.kubernetes_auth_mode,
    ]
  }
}
