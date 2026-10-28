output "url" {
  description = "Open this + /docs in the browser"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_registry" {
  value = split("/", aws_ecr_repository.api.repository_url)[0]
}
