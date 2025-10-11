# 🤖 Agent Setup Checklist for Find Your Team

## ✅ What You've Provided:
- **AWS Account ID**: 575108952095
- **Canonical User ID**: 37d5650e53c6b5b5c7cfd8c5a3a59de01ff7c0339d13f5397be4d0d1f484e95e
- **Access Key**: AKIAYLZZKGAP22LJ2MPE

## 🔑 What You Still Need:

### 1. AWS Secret Access Key
You need to provide your **AWS Secret Access Key** that corresponds to the Access Key `AKIAYLZZKGAP22LJ2MPE`.

**To get it:**
1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/home#/security_credentials)
2. Find your access key `AKIAYLZZKGAP22LJ2MPE`
3. If you don't have the secret key, create a new access key pair
4. Copy the secret access key

### 2. Required AWS Permissions
Make sure your IAM user has these policies attached:
- ✅ `AmazonBedrockFullAccess`
- ✅ `AmazonDynamoDBFullAccess` 
- ✅ `AmazonIoTCoreFullAccess`
- ✅ `CloudWatchFullAccess`
- ✅ `AmazonOpenSearchServiceFullAccess`

## 🚀 Setup Steps:

### Step 1: Add Secret Access Key
Edit `config.ini` and replace:
```ini
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY_HERE
```
With your actual secret access key.

### Step 2: Setup IoT Endpoint
Run the setup script:
```bash
python setup_aws_iot.py
```

### Step 3: Test the Setup
```bash
python app.py
```

### Step 4: Verify Agents
Visit http://localhost:5002 and test:
- **Onboarding Agent**: Chat with the AI for profile setup
- **Matching Agent**: Get team recommendations
- **Team Agent**: Manage team interactions
- **Integration Agent**: Handle external integrations

## 🔧 Agent Components:

### 1. **Onboarding Agent** (`agents/onboarding_agent.py`)
- Uses **Amazon Bedrock** (Claude 3.5 Sonnet)
- Stores data in **DynamoDB**
- Handles user profile creation

### 2. **Matching Agent** (`agents/matching_agent.py`)
- Uses **Amazon Bedrock** for AI matching
- **OpenSearch** for vector similarity
- **DynamoDB** for team data

### 3. **Team Agent** (`agents/team_agent.py`)
- **IoT Core** for real-time communication
- **DynamoDB** for team management
- **CloudWatch** for monitoring

### 4. **Integration Agent** (`agents/integration_agent.py`)
- **API Gateway** for external integrations
- **Lambda** functions for processing
- **S3** for file storage

## 🐛 Troubleshooting:

### If agents don't work:
1. **Check AWS credentials**: `aws sts get-caller-identity`
2. **Verify permissions**: Test each service access
3. **Check logs**: Look at `app.log` for errors
4. **Test endpoints**: `curl http://localhost:5002/api/health`

### Common Issues:
- **"Access Denied"**: Check IAM permissions
- **"Region not supported"**: Ensure Bedrock is available in us-west-2
- **"Endpoint not found"**: Run the IoT setup script
- **"Table not found"**: DynamoDB tables are created automatically

## 📞 Need Help?
If you encounter issues:
1. Check the error logs in `app.log`
2. Verify your AWS credentials with: `aws configure list`
3. Test individual services in AWS Console
4. Run the health check: `curl http://localhost:5002/api/health`

---

**Once you provide the secret access key, the agents should work perfectly! 🎉**