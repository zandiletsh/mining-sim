variable "region" {
  description = "AWS region"
  type        = string
  default     = "af-south-1" # Cape Town
}

variable "name" {
  description = "Name prefix for everything"
  type        = string
  default     = "opsbrain"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "image_tag" {
  description = "Docker image tag in ECR"
  type        = string
  default     = "latest"
}

variable "desired_count" {
  description = "How many API tasks to run"
  type        = number
  default     = 2
}

variable "cpu" {
  description = "Fargate CPU units (1024 = 1 vCPU). The optimiser is CPU heavy."
  type        = number
  default     = 1024
}

variable "memory" {
  description = "Fargate memory in MB"
  type        = number
  default     = 2048
}
