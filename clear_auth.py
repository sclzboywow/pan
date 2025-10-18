#!/usr/bin/env python3
"""
清除本地授权信息
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.api_client import APIClient
from pathlib import Path

def clear_all_auth():
    """清除所有本地授权信息"""
    print("🗑️ 正在清除本地授权信息...")
    
    # 创建APIClient实例
    client = APIClient()
    
    # 清除单账号token
    print("📝 清除单账号token...")
    client.clear_tokens()
    
    # 清除多账号信息
    print("📝 清除多账号信息...")
    try:
        accounts_path = client._accounts_path()
        if accounts_path.exists():
            accounts_path.unlink()
            print(f"✅ 已删除: {accounts_path}")
        else:
            print("ℹ️ 多账号文件不存在")
    except Exception as e:
        print(f"❌ 清除多账号信息失败: {e}")
    
    # 清除所有相关文件
    print("📝 清除所有相关文件...")
    try:
        base_dir = client._accounts_dir()
        if base_dir.exists():
            for file_path in base_dir.glob("*.json"):
                try:
                    file_path.unlink()
                    print(f"✅ 已删除: {file_path}")
                except Exception as e:
                    print(f"❌ 删除文件失败 {file_path}: {e}")
        else:
            print("ℹ️ 存储目录不存在")
    except Exception as e:
        print(f"❌ 清除文件失败: {e}")
    
    # 重置内存中的状态
    print("📝 重置内存状态...")
    client.user_jwt = None
    client.baidu_token = None
    client.user_info = None
    client.accounts = {}
    client.current_account_uk = None
    
    # 清除请求头中的Authorization
    if 'Authorization' in client.session.headers:
        del client.session.headers['Authorization']
    
    print("✅ 所有本地授权信息已清除！")
    print("🎯 现在您可以重新进行扫码授权了")
    
    # 显示当前状态
    print(f"\n📊 当前状态:")
    print(f"JWT Token: {client.user_jwt}")
    print(f"百度Token: {client.baidu_token}")
    print(f"用户信息: {client.user_info}")
    print(f"账号数量: {len(client.accounts) if hasattr(client, 'accounts') else 0}")

if __name__ == "__main__":
    clear_all_auth()
