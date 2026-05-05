resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-frontend-oac"
  description                       = "Private access from CloudFront to the frontend S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  comment             = "${local.name_prefix} frontend"
  default_root_object = var.frontend_default_root_object
  aliases             = [var.frontend_domain]

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3-origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    target_origin_id       = "frontend-s3-origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  logging_config {
    bucket = aws_s3_bucket.logs.bucket_domain_name
    prefix = "cloudfront/"
  }

  viewer_certificate {
    acm_certificate_arn      = local.frontend_certificate
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = local.tags
}

data "aws_iam_policy_document" "frontend_bucket_policy" {
  statement {
    sid = "AllowCloudFrontRead"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = ["s3:GetObject"]

    resources = ["${aws_s3_bucket.frontend.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket_policy.json
}

resource "aws_route53_record" "frontend_alias" {
  count = var.create_route53_records ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.frontend_domain
  type    = "A"

  alias {
    evaluate_target_health = false
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
  }
}

resource "aws_route53_record" "api_alias" {
  count = var.create_route53_records ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.api_domain
  type    = "A"

  alias {
    evaluate_target_health = true
    name                   = aws_lb.api.dns_name
    zone_id                = aws_lb.api.zone_id
  }
}
