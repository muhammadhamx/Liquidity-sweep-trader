#!/usr/bin/env python
"""
Load environment variables from .env file
"""

import os

def load_env():
    """Load environment variables from .env file"""
    env_file = '.env'
    
    if not os.path.exists(env_file):
        print(f"❌ {env_file} file not found")
        return False
    
    print(f"📁 Loading environment variables from {env_file}")
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
                    print(f"✅ Set {key.strip()}")
    
    return True

if __name__ == "__main__":
    load_env()
    
    # Test the loaded variables
    print("\n📊 Loaded MT5 Configuration:")
    print(f"   - Login: {os.environ.get('MT5_LOGIN', 'Not set')}")
    print(f"   - Server: {os.environ.get('MT5_SERVER', 'Not set')}")
    print(f"   - Account Name: {os.environ.get('MT5_ACCOUNT_NAME', 'Not set')}")
    print(f"   - Account Type: {os.environ.get('MT5_ACCOUNT_TYPE', 'Not set')}")
    print(f"   - Use Mock: {os.environ.get('USE_MOCK_MT5', 'Not set')}")
