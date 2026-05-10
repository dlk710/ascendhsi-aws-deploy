resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  tags = local.tags
}

resource "aws_lb" "api" {
  name               = substr("${local.name_prefix}-api", 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  access_logs {
    bucket  = aws_s3_bucket.logs.id
    prefix  = "alb"
    enabled = true
  }

  tags = local.tags
}

resource "aws_lb_target_group" "api" {
  name        = substr("${local.name_prefix}-api", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    path                = var.health_check_path
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }

  tags = local.tags
}

resource "aws_lb_listener" "http_forward" {
  count = local.api_certificate == "" ? 1 : 0

  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  count = local.api_certificate != "" ? 1 : 0

  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  count = local.api_certificate != "" ? 1 : 0

  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = local.api_certificate
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.backend_cpu)
  memory                   = tostring(var.backend_memory)
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = local.backend_image
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "ASCEND_APP_NAME", value = "Ascend Product Suite" },
        { name = "ASCEND_DATABASE_PATH", value = "/tmp/ascend/ascend.sqlite" },
        { name = "ASCEND_UPLOAD_ROOT", value = "/tmp/ascend/uploads" },
        { name = "ASCEND_MIRROR_ROOT", value = "/tmp/ascend/mirror" },
        { name = "ASCEND_CORS_ORIGINS", value = join(",", local.cors_origins) },
        { name = "ASCEND_S3_ENABLED", value = "true" },
        { name = "ASCEND_STORAGE_BUCKET", value = aws_s3_bucket.storage.id },
        { name = "ASCEND_ARCHIVE_BUCKET", value = aws_s3_bucket.archive.id },
        { name = "ASCEND_STORAGE_PUBLIC_BASE_URL", value = "" },
        { name = "ASCEND_S3_SERVER_SIDE_ENCRYPTION", value = "AES256" },
        { name = "ASCEND_API_DOMAIN", value = var.api_domain },
        { name = "ASCEND_PUBLIC_BASE_URL", value = length(local.frontend_aliases) > 0 ? "https://${var.frontend_domain}" : "https://${aws_cloudfront_distribution.frontend.domain_name}" },
        { name = "ASCEND_EMAIL_PROVIDER", value = var.invite_email_provider },
        { name = "ASCEND_INVITE_EMAIL_FROM", value = var.invite_email_from },
        { name = "ASCEND_INVITE_REPLY_TO", value = var.invite_email_reply_to },
        { name = "ASCEND_SES_REGION", value = var.invite_email_region },
        { name = "ASCEND_INVITE_EXPIRY_DAYS", value = tostring(var.invite_expiry_days) },
        { name = "ASCEND_BUG_LOG_TABLE", value = local.issue_log_table_name },
        { name = "ASCEND_FRONTEND_BUCKET", value = aws_s3_bucket.frontend.id },
        { name = "ASCEND_CLOUDFRONT_DISTRIBUTION_ID", value = aws_cloudfront_distribution.frontend.id },
        { name = "ASCEND_ECS_CLUSTER", value = "${local.name_prefix}-cluster" },
        { name = "ASCEND_ECS_SERVICE", value = "${local.name_prefix}-backend" },
        { name = "ASCEND_ECR_REPOSITORY", value = aws_ecr_repository.backend.name },
        { name = "ASCEND_ALB_NAME", value = substr("${local.name_prefix}-api", 0, 32) },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "AWS_COST_EXPLORER_REGION", value = "us-east-1" },
      ]
      secrets = local.backend_secrets
      command = [
        "uvicorn",
        "app.api:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
      ]
    },
  ])

  tags = local.tags
}

resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [
    aws_lb_listener.http_forward,
    aws_lb_listener.http_redirect,
    aws_lb_listener.https,
  ]

  tags = local.tags
}
