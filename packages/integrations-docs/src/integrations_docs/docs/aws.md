---
tags: Data Infrastructure
description: Connect to Amazon Web Services (AWS) for cloud storage, databases, compute, AI/ML, and more.
---
# AWS Integration

The **AWS Integration** allows your app to connect to [Amazon Web Services (AWS)](https://aws.amazon.com/) — the world's most comprehensive cloud platform. Once connected, your app can access 200+ AWS services including storage, databases, compute, AI/ML, and more using the boto3 SDK.

## What You Can Do

With AWS integration, your app can:
- **S3 (Object Storage):** Upload, download, and manage files in S3 buckets. Generate presigned URLs for secure file access. Works with S3-compatible services like MinIO, Cloudflare R2, and DigitalOcean Spaces.
- **DynamoDB (NoSQL Database):** Store and query data in a fully managed, serverless NoSQL database with single-digit millisecond performance.
- **Lambda (Serverless Functions):** Invoke serverless functions, run code without managing servers, and build event-driven applications.
- **SES (Email Service):** Send transactional emails, marketing emails, and notifications with high deliverability.
- **SNS (Notifications):** Send push notifications, SMS, and email messages to users across multiple channels.
- **SQS (Message Queues):** Build distributed, decoupled systems with reliable message queuing.
- **Rekognition (Computer Vision):** Analyze images and videos for object detection, facial analysis, text extraction, and content moderation.
- **Comprehend (NLP):** Extract insights from text using natural language processing for sentiment analysis, entity recognition, and topic modeling.
- **Bedrock (AI Models):** Access foundation models from AI21 Labs, Anthropic, Cohere, Meta, Stability AI, and Amazon for generative AI applications.
- **And 200+ more services:** EC2, RDS, CloudWatch, Polly, Textract, Translate, and many others.

## Step 1: Obtain AWS Credentials

1. Log in to the [AWS Console](https://console.aws.amazon.com/).

2. **Create IAM credentials:**
   - Navigate to **IAM (Identity and Access Management)**.
   - Click **Users** → **Add user** or select an existing user.
   - Attach policies based on the AWS services you plan to use:
     - **S3:** `AmazonS3FullAccess` or custom S3 policy
     - **DynamoDB:** `AmazonDynamoDBFullAccess` or custom DynamoDB policy
     - **Lambda:** `AWSLambdaFullAccess` or custom Lambda policy
     - **SES:** `AmazonSESFullAccess` or custom SES policy
     - **Multiple services:** Attach multiple policies or create a custom policy combining permissions

   **Example custom policy for S3 + DynamoDB:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket",
           "dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"
         ],
         "Resource": [
           "arn:aws:s3:::YOUR_BUCKET_NAME/*",
           "arn:aws:dynamodb:YOUR_REGION:YOUR_ACCOUNT_ID:table/*"
         ]
       }
     ]
   }
   ```

3. **Generate access keys:**
   - Under **Security credentials**, click **Create access key**.
   - Choose **Application running outside AWS** as the use case.
   - Copy your **Access Key ID** and **Secret Access Key**.

   **Example credentials:**
   * **Access Key ID:** `AKIAIOSFODNN7EXAMPLE`
   * **Secret Access Key:** `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`

## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add AWS** in your app settings.
2. Enter your **AWS Access Key ID** and **AWS Secret Access Key**.
3. **(Optional)** Select your **AWS Region** (e.g., `us-east-1`, `eu-west-1`). Defaults to `us-east-1`.
4. **(Optional)** Enter an **AWS Endpoint URL** if using S3-compatible services:
   - **MinIO:** `http://localhost:9000` or your MinIO server URL
   - **Cloudflare R2:** `https://<account-id>.r2.cloudflarestorage.com`
   - **DigitalOcean Spaces:** `https://<region>.digitaloceanspaces.com`
   - Leave blank for standard AWS services.
5. Click **Connect** to validate and save your integration.

Once connected, your app can access AWS services using boto3.

## Important Notes

* **IAM permissions:** Ensure your IAM user has the necessary permissions for the AWS services you plan to use. Attach service-specific policies (e.g., `AmazonS3FullAccess`, `AmazonDynamoDBFullAccess`, `AWSLambdaFullAccess`) or create custom policies with least-privilege access.
* **AWS Region:** Most AWS services are region-specific. Select the correct region where your resources are located (e.g., S3 buckets, DynamoDB tables, Lambda functions).
* **Cost management:** Monitor AWS usage and costs through the AWS Billing Dashboard. Set up billing alerts to avoid unexpected charges.
* **Security:** Rotate your access keys regularly and enable MFA for AWS console access. Apply least-privilege IAM policies to limit permissions to only what's needed.
* **S3-compatible services:** For S3 operations, this integration works with S3-compatible storage like MinIO (self-hosted), Cloudflare R2 (zero egress fees), and DigitalOcean Spaces. Just provide the custom endpoint URL in the configuration.
* **Service availability:** Not all AWS services are available in all regions. Check the [AWS Regional Services List](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/) for service availability.
