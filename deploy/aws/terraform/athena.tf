resource "aws_athena_workgroup" "observability" {
  name = "${local.name_prefix}-observability"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = false

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/queries/"
    }
  }

  tags = local.tags
}

resource "aws_athena_database" "observability" {
  name   = replace("${local.name_prefix}_observability", "-", "_")
  bucket = aws_s3_bucket.athena_results.id
}

resource "aws_athena_named_query" "create_cloudfront_logs_table" {
  name      = "create_cloudfront_logs_table"
  database  = aws_athena_database.observability.name
  workgroup = aws_athena_workgroup.observability.name
  query     = templatefile("${path.module}/athena/create_cloudfront_logs_table.sql.tftpl", { logs_bucket = aws_s3_bucket.logs.id })
}

resource "aws_athena_named_query" "create_alb_access_logs_table" {
  name      = "create_alb_access_logs_table"
  database  = aws_athena_database.observability.name
  workgroup = aws_athena_workgroup.observability.name
  query     = templatefile("${path.module}/athena/create_alb_access_logs_table.sql.tftpl", { logs_bucket = aws_s3_bucket.logs.id, account_id = local.account_id })
}

resource "aws_athena_named_query" "create_backend_application_logs_table" {
  name      = "create_backend_application_logs_table"
  database  = aws_athena_database.observability.name
  workgroup = aws_athena_workgroup.observability.name
  query     = templatefile("${path.module}/athena/create_backend_application_logs_table.sql.tftpl", { logs_bucket = aws_s3_bucket.logs.id })
}

resource "aws_athena_named_query" "recent_alb_5xx" {
  name      = "recent_alb_5xx"
  database  = aws_athena_database.observability.name
  workgroup = aws_athena_workgroup.observability.name
  query     = file("${path.module}/athena/recent_alb_5xx.sql")
}

resource "aws_athena_named_query" "top_cloudfront_errors" {
  name      = "top_cloudfront_errors"
  database  = aws_athena_database.observability.name
  workgroup = aws_athena_workgroup.observability.name
  query     = file("${path.module}/athena/top_cloudfront_errors.sql")
}
