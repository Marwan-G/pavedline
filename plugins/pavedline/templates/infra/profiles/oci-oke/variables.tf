# Every identifier is a variable. Copy terraform.tfvars.example to terraform.tfvars (git-ignored) and fill it in.

variable "tenancy_ocid" {
  type        = string
  description = "Tenancy identifier."
}

variable "compartment_ocid" {
  type        = string
  description = "Compartment that holds everything this profile creates."
}

variable "region" {
  type        = string
  description = "Region identifier for the cluster and its buckets."
}

variable "home_region" {
  type        = string
  description = "The tenancy's home region (IAM and budgets must be created there)."
}

variable "oci_auth" {
  type        = string
  default     = "SecurityToken"
  description = "Provider auth mode. SecurityToken = `oci session authenticate`, no long-lived key on disk."
}

variable "oci_profile" {
  type        = string
  default     = "DEFAULT"
  description = "Profile name in the OCI config file (the same one passed to `oci session authenticate --profile-name`)."
}

variable "kubernetes_auth_mode" {
  type        = string
  default     = "security_token"
  description = "Auth mode passed to `oci ce cluster generate-token --auth`: security_token (session from `oci session authenticate`), api_key, instance_principal or resource_principal."
}

variable "name_prefix" {
  type        = string
  default     = "example"
  description = "Prefix for every resource name."
}

variable "availability_domain_index" {
  type        = number
  default     = 0
  description = "Which availability domain of the region hosts the node pools (regions with one domain: 0)."
}

variable "vcn_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "api_subnet_cidr" {
  type    = string
  default = "10.0.0.0/28"
}

variable "workers_subnet_cidr" {
  type    = string
  default = "10.0.10.0/24"
}

variable "pods_cidr" {
  type        = string
  default     = "10.244.0.0/16"
  description = "Flannel overlay range for pods (not a VCN subnet)."
}

variable "services_cidr" {
  type    = string
  default = "10.96.0.0/16"
}

variable "api_allowed_cidrs" {
  type        = list(string)
  description = "Who may reach the Kubernetes API endpoint: your own address range(s), e.g. [\"203.0.113.7/32\"]. No default on purpose."
  validation {
    condition = length(var.api_allowed_cidrs) > 0 && alltrue([
      for c in var.api_allowed_cidrs :
      can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+/[0-9]+$", c)) && can(cidrhost(c, 0)) && tonumber(split("/", c)[1]) >= 16
    ])
    error_message = "Give at least one IPv4 CIDR with a prefix of /16 or longer; open-to-the-world ranges (0.0.0.0/0, 0.0.0.0/1, ::/0) are refused."
  }
}

variable "cluster_type" {
  type        = string
  default     = "BASIC_CLUSTER"
  description = "BASIC_CLUSTER has no per-cluster charge and is enough for the taint/label and Cloudflare Tunnel ingress design here. ENHANCED_CLUSTER adds virtual nodes, add-on management and a cluster SLA (billed per hour)."
  validation {
    condition     = contains(["BASIC_CLUSTER", "ENHANCED_CLUSTER"], var.cluster_type)
    error_message = "cluster_type must be BASIC_CLUSTER or ENHANCED_CLUSTER."
  }
}

variable "kubernetes_version" {
  type        = string
  description = "OKE Kubernetes version, e.g. v1.35.1 (list with `oci ce cluster-options get --cluster-option-id all`)."
}

variable "node_image_id" {
  type        = string
  description = "Image identifier of an OKE arm64 (aarch64) node image for the cluster's Kubernetes version."
}

variable "node_shape" {
  type        = string
  default     = "VM.Standard.A1.Flex"
  description = "Ampere arm64 flexible shape."
}

variable "node_boot_volume_gbs" {
  type    = number
  default = 66
}

variable "node_pools" {
  type = map(object({
    size   = number
    ocpus  = number
    memory = number
    labels = map(string)
    taints = list(object({ key = string, value = string, effect = string }))
  }))
  description = "One OKE node pool per entry. Labels go through the pool's native initial_node_labels; taints are applied by the kubernetes provider (the node pool resource has no taint argument) once enable_node_taints is true."
  default = {
    app = {
      size   = 2
      ocpus  = 2
      memory = 8
      labels = { workload = "app" }
      taints = []
    }
    data = {
      size   = 3
      ocpus  = 1
      memory = 6
      labels = { workload = "data" }
      taints = [{ key = "workload", value = "data", effect = "NoSchedule" }]
    }
  }
}

variable "enable_node_taints" {
  type        = bool
  default     = false
  description = "Second-phase switch: set true after the nodes are Ready so kubernetes_node_taint can address them."
}

variable "backup_bucket_name" {
  type    = string
  default = "example-backups"
}

variable "backup_retention_days" {
  type        = number
  default     = 35
  description = "Days a non-current object version is kept before the lifecycle rule deletes it."
}

variable "budget_amount" {
  type        = number
  description = "Monthly budget in the tenancy's currency."
  validation {
    condition     = var.budget_amount > 0
    error_message = "budget_amount must be greater than 0."
  }
}

variable "budget_alert_recipients" {
  type        = list(string)
  description = "E-mail addresses that receive the budget alerts."
}

variable "budget_forecast_threshold_percent" {
  type    = number
  default = 80
}

variable "kms_protection_mode" {
  type        = string
  default     = "SOFTWARE"
  description = "SOFTWARE keys are free; HSM keys are billed per key version."
}

variable "vault_secret_names" {
  type        = set(string)
  default     = ["backup-s3-access-key", "backup-s3-secret-key"]
  description = "Vault secret shells to create. Each gets a placeholder; the founder places the real value in the console."
}

variable "enable_cluster_resources" {
  type        = bool
  default     = false
  description = "Second-phase switch: set true after the cluster exists to create the Kubernetes secrets below."
}

variable "k8s_secret_bindings" {
  type = map(object({
    namespace = string
    keys      = map(string)
  }))
  default     = {}
  description = "Kubernetes secret name => { namespace, keys = { data key in the Secret = vault secret name } }, so one Secret can hold several keys. The vault stays authoritative; each value is read from its secret's current version. A bound value passes through the Terraform state (see the README)."
}
