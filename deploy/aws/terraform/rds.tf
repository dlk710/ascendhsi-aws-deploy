resource "random_password" "db_password" {
  length           = 24
  special          = true
  override_special = "_%@"
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-db-subnets"
  })
}

resource "aws_db_instance" "main" {
  identifier              = "${local.name_prefix}-postgres"
  engine                  = "postgres"
  engine_version          = var.db_engine_version
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  max_allocated_storage   = var.db_allocated_storage + 20
  db_name                 = var.db_name
  username                = var.db_username
  password                = random_password.db_password.result
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  publicly_accessible     = false
  storage_encrypted       = true
  skip_final_snapshot     = true
  backup_retention_period = 1
  deletion_protection     = false
  multi_az                = false
  apply_immediately       = true

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-postgres"
  })
}

resource "aws_secretsmanager_secret" "database_url" {
  name = "${local.name_prefix}/backend/database-url"

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql://%s:%s@%s:%s/%s?sslmode=%s",
    var.db_username,
    random_password.db_password.result,
    aws_db_instance.main.address,
    aws_db_instance.main.port,
    var.db_name,
    var.database_ssl_mode,
  )
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name = "${local.name_prefix}/backend/openai-api-key"

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}
