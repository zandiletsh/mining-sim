# OpsBrain on AWS (Terraform)

Builds: VPC, 2 public subnets, load balancer, ECR, ECS Fargate (2 tasks, autoscale 2-5), IAM roles, logs.
Cost: about $1-2 per day while running. Run `terraform destroy` when you are done.

1. `aws configure`  (or `aws sso login`) then `aws sts get-caller-identity`
2. `cd terraform` then `terraform init`
3. `terraform apply -target=aws_ecr_repository.api`   (makes the image registry first)
4. Push the image (see below)
5. `terraform apply`  (makes everything else)
6. Open the `url` output + `/docs`
7. Finished? `terraform destroy`

## Push the image
```
$REG = terraform output -raw ecr_registry
$REPO = terraform output -raw ecr_repository_url
aws ecr get-login-password --region af-south-1 | docker login --username AWS --password-stdin $REG
cd ..
docker build -t opsbrain-api .
docker tag opsbrain-api:latest "${REPO}:latest"
docker push "${REPO}:latest"
cd terraform
```
