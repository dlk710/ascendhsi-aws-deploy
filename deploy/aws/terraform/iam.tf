data "aws_iam_policy_document" "ecs_task_execution_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${local.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "ecs_task_policy" {
  statement {
    sid = "AllowS3Access"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.storage.arn,
      "${aws_s3_bucket.storage.arn}/*",
      aws_s3_bucket.archive.arn,
      "${aws_s3_bucket.archive.arn}/*",
    ]
  }

  statement {
    sid = "AllowSecretRead"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]

    resources = [
      aws_secretsmanager_secret.database_url.arn,
      aws_secretsmanager_secret.openai_api_key.arn,
    ]
  }

  statement {
    sid = "AllowFirehoseDelivery"

    actions = [
      "firehose:PutRecord",
      "firehose:PutRecordBatch",
    ]

    resources = [aws_kinesis_firehose_delivery_stream.application_logs.arn]
  }
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json

  tags = local.tags
}

resource "aws_iam_policy" "ecs_task" {
  name   = "${local.name_prefix}-ecs-task"
  policy = data.aws_iam_policy_document.ecs_task_policy.json
}

resource "aws_iam_role_policy_attachment" "ecs_task" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task.arn
}

data "aws_iam_policy_document" "firehose_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "firehose_delivery" {
  name               = "${local.name_prefix}-firehose-delivery"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume_role.json

  tags = local.tags
}

data "aws_iam_policy_document" "firehose_delivery" {
  statement {
    actions = [
      "s3:AbortMultipartUpload",
      "s3:GetBucketLocation",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:PutObject",
    ]

    resources = [
      aws_s3_bucket.logs.arn,
      "${aws_s3_bucket.logs.arn}/application/*",
    ]
  }
}

resource "aws_iam_policy" "firehose_delivery" {
  name   = "${local.name_prefix}-firehose-delivery"
  policy = data.aws_iam_policy_document.firehose_delivery.json
}

resource "aws_iam_role_policy_attachment" "firehose_delivery" {
  role       = aws_iam_role.firehose_delivery.name
  policy_arn = aws_iam_policy.firehose_delivery.arn
}
