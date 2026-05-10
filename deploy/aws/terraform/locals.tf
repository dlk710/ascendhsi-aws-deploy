locals {
  account_id                 = var.account_id != "" ? var.account_id : data.aws_caller_identity.current.account_id
  name_prefix                = "${var.project_name}-${var.environment}"
  frontend_bucket_base       = replace(lower(var.frontend_bucket_base_name), "_", "-")
  storage_bucket_base        = replace(lower(var.storage_bucket_base_name), "_", "-")
  archive_bucket_base        = replace(lower(var.archive_bucket_base_name), "_", "-")
  logs_bucket_base           = replace(lower(var.logs_bucket_base_name), "_", "-")
  athena_results_bucket_base = replace(lower(var.athena_results_bucket_base_name), "_", "-")
  frontend_bucket_name       = "${local.frontend_bucket_base}-${var.environment}-${local.account_id}"
  storage_bucket_name        = "${local.storage_bucket_base}-${var.environment}-${local.account_id}"
  archive_bucket_name        = "${local.archive_bucket_base}-${var.environment}-${local.account_id}"
  logs_bucket_name           = "${local.logs_bucket_base}-${var.environment}-${local.account_id}"
  athena_results_bucket      = "${local.athena_results_bucket_base}-${var.environment}-${local.account_id}"
  issue_log_table_name       = var.issue_log_table_name != "" ? var.issue_log_table_name : "${local.name_prefix}-product-issue-logs"
  backend_image              = var.backend_image != "" ? var.backend_image : "${aws_ecr_repository.backend.repository_url}:latest"
  frontend_certificate       = var.create_acm_certificates ? aws_acm_certificate_validation.frontend[0].certificate_arn : var.frontend_certificate_arn
  api_certificate            = var.create_acm_certificates ? aws_acm_certificate_validation.api[0].certificate_arn : var.api_certificate_arn
  frontend_aliases           = local.frontend_certificate != "" ? [var.frontend_domain] : []
  cors_origins               = distinct(concat(["https://${var.frontend_domain}"], var.allowed_cors_origins))
  backend_secrets            = [{ name = "ASCEND_DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn }, { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key.arn }]
  tags = {
    Project     = "Ascend"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
