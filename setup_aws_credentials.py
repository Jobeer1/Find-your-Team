#!/usr/bin/env python3
"""
AWS Credentials Setup Helper for Find Your Team
Account: ysterjobeer (575108952095)
"""

import configparser
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import sys

def check_aws_credentials():
    """Check if AWS credentials are properly configured"""
    print("🔍 Checking AWS credentials...")
    
    try:
        # Try to create a session
        session = boto3.Session()
        sts = session.client('sts')
        
        # Get caller identity to verify credentials
        identity = sts.get_caller_identity()
        
        print("✅ AWS credentials are configured!")
        print(f"   Account ID: {identity['Account']}")
        print(f"   User ARN: {identity['Arn']}")
        
        # Verify it's the correct account
        if identity['Account'] == '575108952095':
            print("✅ Correct AWS account (ysterjobeer)")
        else:
            print(f"⚠️  Warning: Expected account 575108952095, but got {identity['Account']}")
        
        return True
        
    except NoCredentialsError:
        print("❌ No AWS credentials found")
        return False
    except ClientError as e:
        print(f"❌ AWS credentials error: {e}")
        return False

def test_required_services():
    """Test access to required AWS services"""
    print("\n🧪 Testing AWS service access...")
    
    services_to_test = [
        ('bedrock-runtime', 'Bedrock (AI Models)'),
        ('dynamodb', 'DynamoDB (Database)'),
        ('iot-data', 'IoT Core (Real-time messaging)'),
        ('opensearch', 'OpenSearch (Search engine)'),
        ('logs', 'CloudWatch Logs')
    ]
    
    session = boto3.Session()
    
    for service_name, description in services_to_test:
        try:
            if service_name == 'bedrock-runtime':
                client = session.client(service_name, region_name='us-east-1')
                # Try to list foundation models
                client.list_foundation_models()
                print(f"✅ {description}")
            elif service_name == 'dynamodb':
                client = session.client(service_name, region_name='us-east-1')
                client.list_tables()
                print(f"✅ {description}")
            elif service_name == 'iot-data':
                # IoT requires an endpoint, so we'll skip the actual test
                print(f"⏭️  {description} (requires IoT endpoint setup)")
            elif service_name == 'opensearch':
                client = session.client(service_name, region_name='us-east-1')
                client.list_domain_names()
                print(f"✅ {description}")
            elif service_name == 'logs':
                client = session.client(service_name, region_name='us-east-1')
                client.describe_log_groups(limit=1)
                print(f"✅ {description}")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['AccessDenied', 'UnauthorizedOperation']:
                print(f"❌ {description} - Access Denied (need permissions)")
            else:
                print(f"⚠️  {description} - {error_code}")
        except Exception as e:
            print(f"❌ {description} - {str(e)}")

def update_config_with_credentials():
    """Update config.ini with actual AWS credentials"""
    print("\n📝 Updating config.ini with your credentials...")
    
    # Check if credentials are in environment or AWS credentials file
    session = boto3.Session()
    credentials = session.get_credentials()
    
    if credentials:
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Update AWS section
        if 'AWS' not in config:
            config['AWS'] = {}
            
        config['AWS']['aws_access_key_id'] = credentials.access_key
        config['AWS']['aws_secret_access_key'] = credentials.secret_key
        
        if credentials.token:
            config['AWS']['aws_session_token'] = credentials.token
        
        # Write back to file
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
            
        print("✅ config.ini updated with AWS credentials")
        return True
    else:
        print("❌ Could not retrieve AWS credentials")
        return False

def setup_instructions():
    """Provide setup instructions"""
    print("\n" + "="*60)
    print("🚀 AWS SETUP INSTRUCTIONS")
    print("="*60)
    print()
    print("Your AWS Account Details:")
    print("  Account ID: 575108952095")
    print("  Account Alias: ysterjobeer")
    print("  Sign-in URL: https://ysterjobeer.signin.aws.amazon.com/console")
    print()
    print("Steps to set up AWS credentials:")
    print()
    print("1. 🌐 Sign in to AWS Console:")
    print("   https://ysterjobeer.signin.aws.amazon.com/console")
    print()
    print("2. 👤 Create or use an IAM User:")
    print("   - Go to IAM > Users")
    print("   - Create new user or select existing user")
    print("   - Attach these policies:")
    print("     • AmazonBedrockFullAccess")
    print("     • AmazonDynamoDBFullAccess") 
    print("     • AmazonIoTCoreFullAccess")
    print("     • CloudWatchFullAccess")
    print("     • AmazonOpenSearchServiceFullAccess")
    print()
    print("3. 🔑 Create Access Keys:")
    print("   - Go to IAM > Users > [Your User] > Security credentials")
    print("   - Click 'Create access key'")
    print("   - Choose 'Application running outside AWS'")
    print("   - Copy the Access Key ID and Secret Access Key")
    print()
    print("4. 💾 Configure credentials (choose one method):")
    print()
    print("   Method A - AWS CLI (Recommended):")
    print("   $ aws configure")
    print("   AWS Access Key ID: [paste your key]")
    print("   AWS Secret Access Key: [paste your secret]")
    print("   Default region: us-east-1")
    print("   Default output format: json")
    print()
    print("   Method B - Environment Variables:")
    print("   $ export AWS_ACCESS_KEY_ID=your_access_key_here")
    print("   $ export AWS_SECRET_ACCESS_KEY=your_secret_key_here")
    print("   $ export AWS_DEFAULT_REGION=us-east-1")
    print()
    print("   Method C - Edit config.ini directly:")
    print("   Replace YOUR_AWS_ACCESS_KEY_ID_HERE with your actual key")
    print("   Replace YOUR_AWS_SECRET_ACCESS_KEY_HERE with your actual secret")
    print()
    print("5. 🧪 Test the setup:")
    print("   $ python setup_aws_credentials.py")
    print()
    print("="*60)

def main():
    print("🔧 Find Your Team - AWS Setup Helper")
    print("Account: ysterjobeer (575108952095)")
    print("="*50)
    
    # Check if credentials exist
    if check_aws_credentials():
        test_required_services()
        
        # Try to update config.ini
        if update_config_with_credentials():
            print("\n🎉 Setup complete! Your AWS credentials are configured.")
            print("\nNext steps:")
            print("1. Run the application: python app.py")
            print("2. Test the chat functionality")
            print("3. Check that AI responses work properly")
        else:
            print("\n⚠️  Credentials found but couldn't update config.ini")
            
    else:
        setup_instructions()
        print("\n❌ Please set up AWS credentials first, then run this script again.")
        sys.exit(1)

if __name__ == "__main__":
    main()