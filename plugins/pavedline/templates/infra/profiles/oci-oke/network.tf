# Ingress is a Cloudflare Tunnel (outbound only), so there is no load balancer subnet and no public worker address.

data "oci_identity_availability_domains" "this" {
  compartment_id = var.tenancy_ocid
}

data "oci_core_services" "all" {
  filter {
    name   = "name"
    values = ["All .* Services In Oracle Services Network"]
    regex  = true
  }
}

resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.name_prefix}-vcn"
  cidr_blocks    = [var.vcn_cidr]
  dns_label      = replace(var.name_prefix, "-", "")
}

resource "oci_core_internet_gateway" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-igw"
}

resource "oci_core_nat_gateway" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-nat"
}

resource "oci_core_service_gateway" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-sgw"
  services {
    service_id = data.oci_core_services.all.services[0].id
  }
}

resource "oci_core_route_table" "api" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-api"
  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.this.id
  }
}

resource "oci_core_route_table" "workers" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-workers"
  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.this.id
  }
  route_rules {
    destination       = data.oci_core_services.all.services[0].cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.this.id
  }
}

resource "oci_core_security_list" "api" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-api"

  dynamic "ingress_security_rules" {
    for_each = var.api_allowed_cidrs
    content {
      protocol    = "6"
      source      = ingress_security_rules.value
      description = "Kubernetes API from an allowed address"
      tcp_options {
        min = 6443
        max = 6443
      }
    }
  }
  ingress_security_rules {
    protocol    = "6"
    source      = var.workers_subnet_cidr
    description = "Kubernetes API from workers"
    tcp_options {
      min = 6443
      max = 6443
    }
  }
  ingress_security_rules {
    protocol    = "6"
    source      = var.workers_subnet_cidr
    description = "Worker registration"
    tcp_options {
      min = 12250
      max = 12250
    }
  }
  egress_security_rules {
    protocol         = "6"
    destination      = var.workers_subnet_cidr
    description      = "API to kubelets"
    destination_type = "CIDR_BLOCK"
    tcp_options {
      min = 10250
      max = 10250
    }
  }
  egress_security_rules {
    protocol         = "6"
    destination      = data.oci_core_services.all.services[0].cidr_block
    description      = "API to Oracle services"
    destination_type = "SERVICE_CIDR_BLOCK"
    tcp_options {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_security_list" "workers" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-workers"

  ingress_security_rules {
    protocol    = "all"
    source      = var.workers_subnet_cidr
    description = "Node to node and pod traffic"
  }
  ingress_security_rules {
    protocol    = "6"
    source      = var.api_subnet_cidr
    description = "API to kubelets"
    tcp_options {
      min = 10250
      max = 10250
    }
  }
  egress_security_rules {
    protocol         = "all"
    destination      = "0.0.0.0/0"
    description      = "Outbound through the NAT gateway (the tunnel connector and image pulls dial out)"
    destination_type = "CIDR_BLOCK"
  }
}

resource "oci_core_subnet" "api" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  display_name               = "${var.name_prefix}-api"
  cidr_block                 = var.api_subnet_cidr
  route_table_id             = oci_core_route_table.api.id
  security_list_ids          = [oci_core_security_list.api.id]
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_subnet" "workers" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  display_name               = "${var.name_prefix}-workers"
  cidr_block                 = var.workers_subnet_cidr
  route_table_id             = oci_core_route_table.workers.id
  security_list_ids          = [oci_core_security_list.workers.id]
  prohibit_public_ip_on_vnic = true
}
