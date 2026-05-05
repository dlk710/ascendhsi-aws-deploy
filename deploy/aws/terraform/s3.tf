resource "aws_s3_bucket" "frontend" {
  bucket = local.frontend_bucket_name

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-frontend"
  })
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket" "storage" {
  bucket = local.storage_bucket_name

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-active-storage"
  })
}

resource "aws_s3_bucket_public_access_block" "storage" {
  bucket = aws_s3_bucket.storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "storage" {
  bucket = aws_s3_bucket.storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "storage" {
  bucket = aws_s3_bucket.storage.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket" "archive" {
  bucket = local.archive_bucket_name

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-archive-storage"
  })
}

resource "aws_s3_bucket_public_access_block" "archive" {
  bucket = aws_s3_bucket.archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    id     = "archive-to-deep-archive"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = var.archive_transition_days
      storage_class = "DEEP_ARCHIVE"
    }
  }
}

resource "aws_s3_bucket" "logs" {
  bucket = local.logs_bucket_name

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-logs"
  })
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "logs" {
  depends_on = [aws_s3_bucket_ownership_controls.logs]

  bucket = aws_s3_bucket.logs.id
  acl    = "private"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "logs-to-glacier-ir"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = var.log_archive_transition_days
      storage_class = "GLACIER_IR"
    }
  }
}

resource "aws_s3_bucket" "athena_results" {
  bucket = local.athena_results_bucket

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-athena-results"
  })
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "logs_bucket_policy" {
  statement {
    sid = "AllowAlbAccessLogs"

    principals {
      type        = "Service"
      identifiers = ["logdelivery.elasticloadbalancing.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.logs.arn}/alb/AWSLogs/${local.account_id}/*",
    ]
  }

  statement {
    sid = "AllowCloudFrontLegacyLoggingAclCheck"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = [
      "s3:GetBucketAcl",
      "s3:PutBucketAcl",
    ]

    resources = [aws_s3_bucket.logs.arn]
  }

  statement {
    sid = "AllowCloudFrontLegacyLoggingWrite"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.logs.arn}/cloudfront/*",
    ]
  }

  statement {
    sid = "AllowFirehoseWrite"

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.firehose_delivery.arn]
    }

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

resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id
  policy = data.aws_iam_policy_document.logs_bucket_policy.json
}
