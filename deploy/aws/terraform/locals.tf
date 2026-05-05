locals {
  account_id             = var.account_id != "" ? var.account_id : data.aws_caller_identity.current.account_id
  name_prefix            = "${var.project_name}-${var.environment}"
  frontend_bucket_name   = lower("${var.frontend_bucket_base_name}-${var.environment}-${local.account_id}")
  storage_bucket_name    = lower("${var.storage_bucket_base_name}-${var.environment}-${local.account_id}")
  archive_bucket_name    = lower("${var.archive_bucket_base_name}-${var.environment}-${local.account_id}")
  logs_bucket_name       = lower("${var.logs_bucket_base_name}-${var.environment}-${local.account_id}")
  athena_results_bucket  = lower("${var.athena_results_bucket_base_name}-${var.environment}-${local.account_id}")
  backend_image          = var.backend_image != "" ? var.backend_image : "${aws_ecr_repository.backend.repository_url}:latest"
  frontend_certificate   = var.create_acm_certificates ? aws_acm_certificate_validation.frontend[0].certificate_arn : var.frontend_certificate_arn
  api_certificate        = var.create_acm_certificates ? aws_acm_certificate_validation.api[0].certificate_arn : var.api_certificate_arn
  cors_origins           = distinct(concat(["https://${var.frontend_domain}"], var.allowed_cors_origins))
  tags = {
    Project     = "Ascend"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
