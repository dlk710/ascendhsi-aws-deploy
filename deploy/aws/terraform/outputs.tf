output "frontend_bucket_name" {
  value = aws_s3_bucket.frontend.id
}

output "frontend_cloudfront_domain" {
  value = aws_cloudfront_distribution.frontend.domain_name
}

output "api_load_balancer_dns_name" {
  value = aws_lb.api.dns_name
}

output "backend_ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "storage_bucket_name" {
  value = aws_s3_bucket.storage.id
}

output "archive_bucket_name" {
  value = aws_s3_bucket.archive.id
}

output "logs_bucket_name" {
  value = aws_s3_bucket.logs.id
}

output "athena_workgroup_name" {
  value = aws_athena_workgroup.observability.name
}

output "athena_database_name" {
  value = aws_athena_database.observability.name
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "database_secret_arn" {
  value = aws_secretsmanager_secret.database_url.arn
}
