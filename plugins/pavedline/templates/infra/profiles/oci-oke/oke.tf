resource "oci_core_network_security_group" "api" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-api-endpoint"
}

resource "oci_core_network_security_group_security_rule" "api_from_workers" {
  # checkov:skip=CKV_OCI_21: stateful on purpose; a stateless ingress rule would need a matching egress rule for every reply.
  network_security_group_id = oci_core_network_security_group.api.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = var.workers_subnet_cidr
  source_type               = "CIDR_BLOCK"
  description               = "Kubernetes API from workers"
  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }
}

resource "oci_containerengine_cluster" "this" {
  # checkov:skip=CKV2_OCI_6: pod security policies were removed in Kubernetes 1.25; pod security admission replaces them.
  compartment_id     = var.compartment_ocid
  name               = "${var.name_prefix}-oke"
  vcn_id             = oci_core_vcn.this.id
  kubernetes_version = var.kubernetes_version
  type               = var.cluster_type

  endpoint_config {
    is_public_ip_enabled = true
    subnet_id            = oci_core_subnet.api.id
    nsg_ids              = [oci_core_network_security_group.api.id]
  }

  options {
    # Flannel overlay keeps pods off the VCN, so no pod subnet or per-pod VNIC is needed.
    kubernetes_network_config {
      pods_cidr     = var.pods_cidr
      services_cidr = var.services_cidr
    }
  }
}

# Labels are set by the node pool itself. No boot-time scripts of any kind.
resource "oci_containerengine_node_pool" "this" {
  for_each = var.node_pools

  compartment_id     = var.compartment_ocid
  cluster_id         = oci_containerengine_cluster.this.id
  name               = "${var.name_prefix}-${each.key}"
  kubernetes_version = var.kubernetes_version
  node_shape         = var.node_shape

  node_shape_config {
    ocpus         = each.value.ocpus
    memory_in_gbs = each.value.memory
  }

  node_source_details {
    source_type             = "IMAGE"
    image_id                = var.node_image_id
    boot_volume_size_in_gbs = var.node_boot_volume_gbs
  }

  dynamic "initial_node_labels" {
    for_each = each.value.labels
    content {
      key   = initial_node_labels.key
      value = initial_node_labels.value
    }
  }

  node_config_details {
    size                                = each.value.size
    is_pv_encryption_in_transit_enabled = true
    placement_configs {
      availability_domain = data.oci_identity_availability_domains.this.availability_domains[var.availability_domain_index].name
      subnet_id           = oci_core_subnet.workers.id
    }
  }
}

data "oci_containerengine_cluster_kube_config" "this" {
  cluster_id = oci_containerengine_cluster.this.id
}

locals {
  kubeconfig   = yamldecode(data.oci_containerengine_cluster_kube_config.this.content)
  cluster_host = local.kubeconfig.clusters[0].cluster.server
  cluster_ca   = base64decode(local.kubeconfig.clusters[0].cluster["certificate-authority-data"])
}

# Taints: the node pool resource has no taint argument, so the kubernetes provider applies them to the pool's nodes.
# Second phase (enable_node_taints = true) because node names exist only after the nodes join. A node replaced later
# is untainted until the next apply; re-run the plan after any node cycle.
data "oci_containerengine_node_pool" "taint_targets" {
  for_each     = var.enable_node_taints ? { for k, v in var.node_pools : k => v if length(v.taints) > 0 } : {}
  node_pool_id = oci_containerengine_node_pool.this[each.key].id
}

locals {
  taint_targets = merge([
    for pool, data_source in data.oci_containerengine_node_pool.taint_targets : {
      for pair in setproduct([for n in data_source.nodes : n.private_ip], var.node_pools[pool].taints) :
      "${pool}/${pair[0]}/${pair[1].key}" => { node = pair[0], taint = pair[1] }
    }
  ]...)
}

resource "kubernetes_node_taint" "this" {
  for_each = local.taint_targets

  metadata {
    name = each.value.node
  }
  taint {
    key    = each.value.taint.key
    value  = each.value.taint.value
    effect = each.value.taint.effect
  }
}
