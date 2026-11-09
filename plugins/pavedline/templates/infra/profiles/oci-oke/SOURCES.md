# Sources and pins (checked 2026-11-09)

Each pin is the newest release at least two weeks old on 2026-11-09 (cutoff 2026-10-26).

| Pin | Value | Released | URL |
|---|---|---|---|
| `oracle/oci` provider | `= 9.10.0` (9.11.0 on 2026-10-21 is too new) | 2026-10-14 | https://github.com/oracle/terraform-provider-oci/releases/tag/v9.10.0 |
| `hashicorp/kubernetes` provider | `= 3.3.0` (3.4.0 on 2026-10-19 is too new) | 2026-10-01 | https://github.com/hashicorp/terraform-provider-kubernetes/releases/tag/v3.3.0 |
| OpenTofu (CI) | v1.13.2 (1.13.8 on 2026-11-04 is too new) | 2026-10-21 | https://github.com/opentofu/opentofu/releases/tag/v1.13.2 |
| `required_version` | `>= 1.9.0` | n/a | floor for both `tofu` and `terraform` |

OpenTofu release checksum used in CI: `tofu_1.13.2_linux_amd64.tar.gz`
`ac05d9952662c7db28dd57e93f0a68018837bfdf9342384ec0987977c16a9645`, from
https://github.com/opentofu/opentofu/releases/download/v1.13.2/tofu_1.13.2_SHA256SUMS (read 2026-11-09).

## Licences

- OpenTofu: MPL-2.0, https://github.com/opentofu/opentofu/blob/main/LICENSE (2026-11-09).
- `oracle/oci` provider: MPL-2.0, https://github.com/oracle/terraform-provider-oci/blob/master/LICENSE.txt.
- Terraform: Business Source License 1.1 ("Licensor: International Business Machines Corporation (IBM)"),
  https://github.com/hashicorp/terraform/blob/main/LICENSE (read 2026-11-09). Not open source, which is why CI uses
  OpenTofu; the profile still works with either CLI.
- Terraform OKE module (not used): UPL-1.0, https://github.com/oracle-terraform-modules/terraform-oci-oke (v5.5.2,
  2026-10-13). Native resources were chosen so every line can be reviewed.

## Facts the profile relies on

- The `oci_containerengine_node_pool` resource exposes `initial_node_labels` but no taint argument (checked in the
  provider schema, 9.10.0, 2026-11-09); taints use `kubernetes_node_taint` from the kubernetes provider.
- Checkov 3.3.30 (the image pinned by the product starter's security workflow) passes 21 checks on this directory with
  two documented skips (`CKV2_OCI_6`, pod security policies removed in Kubernetes 1.25; `CKV_OCI_21`, stateful NSG rule).
