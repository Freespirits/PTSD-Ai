# =============================================================================
# PTSD-Ai AWS infrastructure (il-central-1 / Tel Aviv)
# This is a STARTER template. Review security groups, IAM, and scaling
# before applying to production.
#
# Usage:
#   terraform init
#   terraform plan -var="domain=yourdomain.example"
#   terraform apply
# =============================================================================

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # Recommended: remote state. Uncomment after creating the bucket.
  # backend "s3" {
  #   bucket         = "ptsd-ai-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "il-central-1"
  #   encrypt        = true
  #   dynamodb_table = "ptsd-ai-tf-locks"
  # }
}

provider "aws" {
  region = "il-central-1"

  default_tags {
    tags = {
      Project     = "ptsd-ai"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ----------------------------------------------------------------------------
# Variables
# ----------------------------------------------------------------------------
variable "environment" {
  type    = string
  default = "production"
}

variable "domain" {
  type        = string
  description = "Domain name (e.g. ozen.example.co.il)"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

# ----------------------------------------------------------------------------
# VPC
# ----------------------------------------------------------------------------
data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "ptsd-ai-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "ptsd-ai-igw" }
}

resource "aws_subnet" "public" {
  count                   = 3
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "ptsd-ai-public-${count.index}" }
}

resource "aws_subnet" "private" {
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags              = { Name = "ptsd-ai-private-${count.index}" }
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "ptsd-ai-nat-eip" }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = "ptsd-ai-nat" }

  depends_on = [aws_internet_gateway.igw]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "ptsd-ai-public-rt" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
  tags = { Name = "ptsd-ai-private-rt" }
}

resource "aws_route_table_association" "public" {
  count          = 3
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = 3
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ----------------------------------------------------------------------------
# ECR
# ----------------------------------------------------------------------------
resource "aws_ecr_repository" "agent" {
  name                 = "ptsd-ai/agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ----------------------------------------------------------------------------
# ECS cluster + task definitions
# ----------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "ptsd-ai"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "ptsd-ai-ecs-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_exec_attach" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow task execution role to read secrets
resource "aws_iam_role_policy" "ecs_secrets" {
  name = "ptsd-ai-secrets-read"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = "arn:aws:secretsmanager:il-central-1:*:secret:ptsd-ai/*"
    }]
  })
}

# ----------------------------------------------------------------------------
# Outputs
# ----------------------------------------------------------------------------
output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "ecr_url" {
  value = aws_ecr_repository.agent.repository_url
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

# ----------------------------------------------------------------------------
# TODO: Add in follow-up
# - ECS Services (agent worker, token-server, web-nginx)
# - ALB + TLS cert (ACM)
# - Route 53 record
# - CloudFront + WAF
# - EC2 for Qdrant + ivrit-ai STT (if self-hosting)
# - CloudWatch alarms + dashboards
# - Secrets (create via CLI or separate terraform file)
# ----------------------------------------------------------------------------
