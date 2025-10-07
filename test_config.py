#!/usr/bin/env python3
"""
Test AWS configuration and credentials
"""

import configparser
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os

def test_config_file():
    """Test reading config.ini"""
    print("🔧 Testing config.ini file...")
    
    config = configparser.ConfigParser()
    try:
        config.read('config.ini')
        
        # Check AWS section
        if 'AWS' in config:
            access_key = config.get('AWS', 'aws_access_key_id', fallback='')
            region = config.get('AWS', 'aws_region', fallback='')
            
            print(f"✅ Config file loaded successfully")
            print(f"   Access Key: {access_key[:10]}..." if access_key else "   Access Key: Not found")
            print(f"   Region: {region}")
            
            return access_key, region
        else:
            print("❌ No AWS section found in config.ini")
            return None, None
            
    except Exception as e:
        print(f"❌ Error reading config.ini: {e}")
        return None, None

def test_aws_credentials():
    """Test AWS credentials"""
    print("\n🔑 Testing AWS credentials...")
    
    try:
        # Test with environment variables first
        session = boto3.Session()
        sts = session.client('sts', region_name='us-west-2')
        
        identity = sts.get_caller_identity()
        
        print("✅ AWS credentials working!")
        print(f"   Account: {identity['Account']}")
        print(f"   User: {identity['Arn']}")
        
        return True
        
    except NoCredentialsError:
        print("❌ No AWS credentials found")
        return False
    except ClientError as e:
        print(f"❌ AWS error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_bedrock_access():
    """Test Bedrock access"""
    print("\n🤖 Testing Bedrock access...")
    
    try:
        bedrock = boto3.client('bedrock-runtime', region_name='us-west-2')
        
        # Try to invoke a model with a simple test
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            body='{"anthropic_version": "bedrock-2023-05-31", "max_tokens": 10, "messages": [{"role": "user", "content": "Hello"}]}'
        )
        
        print("✅ Bedrock access working!")
        print("   Model invocation successful")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            print("❌ Bedrock access denied - need permissions")
        elif error_code == 'ValidationException':
            print("⚠️  Bedrock accessible but model validation failed (this is OK)")
            return True
        else:
            print(f"❌ Bedrock error: {error_code}")
        return False
    except Exception as e:
        print(f"❌ Bedrock error: {e}")
        return False

def main():
    print("🧪 Find Your Team - Configuration Test")
    print("=" * 50)
    
    # Test config file
    access_key, region = test_config_file()
    
    # Test AWS credentials
    aws_working = test_aws_credentials()
    
    # Test Bedrock if AWS is working
    if aws_working:
        bedrock_working = test_bedrock_access()
    else:
        bedrock_working = False
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    if access_key and region:
        print("✅ Config file: OK")
    else:
        print("❌ Config file: Issues found")
    
    if aws_working:
        print("✅ AWS credentials: Working")
    else:
        print("❌ AWS credentials: Not working")
    
    if bedrock_working:
        print("✅ Bedrock AI: Ready")
    else:
        print("❌ Bedrock AI: Not accessible")
    
    if aws_working and bedrock_working:
        print("\n🎉 All systems ready! You can run the full application.")
        print("   Run: python app.py")
    elif aws_working:
        print("\n⚠️  AWS working but Bedrock needs setup. App will run in limited mode.")
        print("   Run: python app.py")
    else:
        print("\n❌ AWS setup needed. App will run in demo mode only.")
        print("   Check your credentials and try again.")

if __name__ == "__main__":
    main()