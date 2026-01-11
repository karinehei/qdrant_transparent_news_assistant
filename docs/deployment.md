# Deployment Guide

## AWS Deployment

### Architecture

```
Internet
   │
   ▼
CloudFront (CDN)
   │
   ▼
Application Load Balancer (ALB)
   │
   ├─── ECS/Fargate (API)
   │    └─── Container: news-api
   │
   ├─── RDS PostgreSQL (Audit DB)
   │
   └─── ECS (Qdrant) or Managed Qdrant
```

### Step 1: Container Registry (ECR)

```bash
# Create ECR repository
aws ecr create-repository --repository-name transparent-news-assistant

# Build and push
docker build -t transparent-news-assistant .
docker tag transparent-news-assistant:latest <account>.dkr.ecr.<region>.amazonaws.com/transparent-news-assistant:latest
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker push <account>.dkr.ecr.<region>.amazonaws.com/transparent-news-assistant:latest
```

### Step 2: RDS PostgreSQL

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier news-audit-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username news_user \
  --master-user-password <secure-password> \
  --allocated-storage 20 \
  --vpc-security-group-ids <sg-id> \
  --db-subnet-group-name <subnet-group>
```

### Step 3: ECS Task Definition

```json
{
  "family": "transparent-news-assistant",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<ecr-repo>/transparent-news-assistant:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {"name": "QDRANT_URL", "value": "http://qdrant:6333"},
        {"name": "AUDIT_DB_URL", "value": "postgresql://..."}
      ],
      "secrets": [
        {"name": "MISTRAL_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/transparent-news-assistant",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Step 4: ECS Service

```bash
aws ecs create-service \
  --cluster news-cluster \
  --service-name news-api \
  --task-definition transparent-news-assistant \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-1,subnet-2],securityGroups=[sg-1],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=<target-group-arn>,containerName=api,containerPort=8000"
```

### Step 5: Application Load Balancer

- Create ALB with health check on `/health`
- Configure target group for ECS service
- Set up SSL certificate (ACM)

### Step 6: Qdrant Deployment

**Option A: ECS**
- Deploy Qdrant container on ECS
- Use EFS for persistent storage

**Option B: Managed Service**
- Use Qdrant Cloud or self-hosted managed instance

### Step 7: Frontend (S3 + CloudFront)

```bash
# Build frontend
cd web
npm run build

# Upload to S3
aws s3 sync dist/ s3://news-assistant-frontend/

# Create CloudFront distribution
# Point to S3 bucket
# Configure CORS for API
```

### Environment Variables

Set in ECS task definition or use AWS Secrets Manager:

```bash
MISTRAL_API_KEY=<from-secrets-manager>
QDRANT_URL=http://qdrant-internal:6333
AUDIT_DB_URL=postgresql://user:pass@rds-endpoint:5432/db
```

### Health Checks

- ALB health check: `/health`
- ECS health check: `/ready`
- Configure appropriate intervals and thresholds

### Scaling

- **ECS Auto Scaling**: Based on CPU/memory or ALB request count
- **RDS**: Consider read replicas for audit queries
- **Qdrant**: Horizontal scaling with sharding

### Monitoring

- CloudWatch Logs for application logs
- CloudWatch Metrics for ECS/RDS metrics
- X-Ray for distributed tracing (optional)
- Custom metrics for latency, error rates

### Cost Optimization

- Use Fargate Spot for non-critical workloads
- RDS Reserved Instances for predictable load
- CloudFront caching for static assets
- S3 lifecycle policies for old audit data

## Alternative: Docker Compose on EC2

For simpler deployments:

1. Launch EC2 instance
2. Install Docker and Docker Compose
3. Clone repository
4. Configure `.env`
5. Run `docker-compose up -d`

Use CloudWatch Agent for logging and monitoring.
