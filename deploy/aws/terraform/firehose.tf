resource "aws_kinesis_firehose_delivery_stream" "application_logs" {
  name        = "${local.name_prefix}-application-logs"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose_delivery.arn
    bucket_arn          = aws_s3_bucket.logs.arn
    prefix              = "application/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "application-errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    buffering_size      = 5
    buffering_interval  = 60
    compression_format  = "GZIP"
  }

  tags = local.tags
}
