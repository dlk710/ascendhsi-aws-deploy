variable "project_name" {
  description = "Short project slug used in resource names."
  type        = string
  default     = "ascend"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "Primary AWS region."
  type        = string
  default     = "us-east-2"
}

variable "account_id" {
  description = "Expected AWS account ID."
  type        = string
  default     = ""
}

variable "frontend_domain" {
  description = "Public frontend domain."
  type        = string
}

variable "api_domain" {
  description = "Public API domain."
  type        = string
}

variable "route53_zone_id" {
  description = "Hosted zone ID used when creating DNS records and ACM validation records."
  type        = string
  default     = ""
}

variable "create_route53_records" {
  description = "Whether Terraform should create Route53 records for frontend and API domains."
  type        = bool
  default     = false
}

variable "create_acm_certificates" {
  description = "Whether Terraform should create ACM certificates and validate them in Route53."
  type        = bool
  default     = false
}

variable "frontend_certificate_arn" {
  description = "Existing us-east-1 ACM certificate ARN for the frontend domain when create_acm_certificates is false."
  type        = string
  default     = ""
}

variable "api_certificate_arn" {
  description = "Existing regional ACM certificate ARN for the API domain when create_acm_certificates is false."
  type        = string
  default     = ""
}

variable "storage_bucket_base_name" {
  description = "Base name for the active client-data bucket."
  type        = string
  default     = "client_data"
}

variable "archive_bucket_base_name" {
  description = "Base name for the archive bucket."
  type        = string
  default     = "client_data-archive"
}

variable "frontend_bucket_base_name" {
  description = "Base name for the frontend asset bucket."
  type        = string
  default     = "ascend-frontend"
}

variable "logs_bucket_base_name" {
  description = "Base name for the central observability logs bucket."
  type        = string
  default     = "ascend-observability-logs"
}

variable "athena_results_bucket_base_name" {
  description = "Base name for Athena query results."
  type        = string
  default     = "ascend-athena-results"
}

variable "backend_image" {
  description = "Backend container image URI in ECR."
  type        = string
  default     = ""
}

variable "frontend_default_root_object" {
  description = "Default object served by CloudFront."
  type        = string
  default     = "index.html"
}

variable "openai_api_key" {
  description = "OpenAI API key stored in Secrets Manager for the backend runtime."
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "ascend"
}

variable "db_username" {
  description = "PostgreSQL application username."
  type        = string
  default     = "ascend_app"
}

variable "db_instance_class" {
  description = "RDS instance class sized for the initial deployment."
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GiB."
  type        = number
  default     = 20
}

variable "db_engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16.4"
}

variable "database_ssl_mode" {
  description = "SSL mode appended to the PostgreSQL connection string."
  type        = string
  default     = "require"
}

variable "backend_desired_count" {
  description = "Desired number of backend tasks."
  type        = number
  default     = 2
}

variable "backend_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "health_check_path" {
  description = "Backend target group health check path."
  type        = string
  default     = "/ready"
}

variable "signed_url_ttl_seconds" {
  description = "Time-to-live for signed S3 download URLs."
  type        = number
  default     = 3600
}

variable "archive_transition_days" {
  description = "Days before archive objects transition deeper into cold storage."
  type        = number
  default     = 90
}

variable "log_archive_transition_days" {
  description = "Days before logs transition into deeper archive storage."
  type        = number
  default     = 30
}

variable "allowed_cors_origins" {
  description = "Extra browser origins allowed to call the API in addition to the primary frontend domain."
  type        = list(string)
  default = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
  ]
}
