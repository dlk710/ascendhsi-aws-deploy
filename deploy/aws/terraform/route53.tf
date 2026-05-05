resource "aws_acm_certificate" "frontend" {
  count    = var.create_acm_certificates ? 1 : 0
  provider = aws.us_east_1

  domain_name       = var.frontend_domain
  validation_method = "DNS"

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-frontend-cert"
  })
}

resource "aws_acm_certificate" "api" {
  count = var.create_acm_certificates ? 1 : 0

  domain_name       = var.api_domain
  validation_method = "DNS"

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-api-cert"
  })
}

resource "aws_route53_record" "frontend_validation" {
  for_each = var.create_acm_certificates ? {
    for option in aws_acm_certificate.frontend[0].domain_validation_options :
    option.domain_name => {
      name   = option.resource_record_name
      record = option.resource_record_value
      type   = option.resource_record_type
    }
  } : {}

  zone_id = var.route53_zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

resource "aws_route53_record" "api_validation" {
  for_each = var.create_acm_certificates ? {
    for option in aws_acm_certificate.api[0].domain_validation_options :
    option.domain_name => {
      name   = option.resource_record_name
      record = option.resource_record_value
      type   = option.resource_record_type
    }
  } : {}

  zone_id = var.route53_zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "frontend" {
  count    = var.create_acm_certificates ? 1 : 0
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.frontend[0].arn
  validation_record_fqdns = [for record in aws_route53_record.frontend_validation : record.fqdn]
}

resource "aws_acm_certificate_validation" "api" {
  count = var.create_acm_certificates ? 1 : 0

  certificate_arn         = aws_acm_certificate.api[0].arn
  validation_record_fqdns = [for record in aws_route53_record.api_validation : record.fqdn]
}
