# Budgets are tenancy-level objects created in the home region.
resource "oci_budget_budget" "this" {
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  display_name   = "${var.name_prefix}-monthly"
  description    = "Monthly spend limit for the compartment this profile creates."
  amount         = var.budget_amount
  reset_period   = "MONTHLY"
  target_type    = "COMPARTMENT"
  targets        = [var.compartment_ocid]
}

resource "oci_budget_alert_rule" "forecast" {
  provider       = oci.home
  budget_id      = oci_budget_budget.this.id
  display_name   = "forecast-warning"
  type           = "FORECAST"
  threshold      = var.budget_forecast_threshold_percent
  threshold_type = "PERCENTAGE"
  recipients     = join(",", var.budget_alert_recipients)
  message        = "Forecast spend has passed the warning threshold of the monthly budget."
}

resource "oci_budget_alert_rule" "actual" {
  provider       = oci.home
  budget_id      = oci_budget_budget.this.id
  display_name   = "actual-critical"
  type           = "ACTUAL"
  threshold      = 100
  threshold_type = "PERCENTAGE"
  recipients     = join(",", var.budget_alert_recipients)
  message        = "Actual spend has reached the monthly budget."
}
