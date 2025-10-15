#!/usr/bin/env python3
"""
授权轮询线程
"""

from PySide6.QtCore import QThread, Signal
from typing import Optional, Dict, Any
import json


class AuthThread(QThread):
    """授权轮询线程"""
    
    auth_success = Signal(dict)
    auth_failed = Signal(str)
    status_update = Signal(str)
    
    def __init__(self, api_client, device_code: str):
        super().__init__()
        self.api_client = api_client
        self.device_code = device_code
        self.running = True
    
    def run(self):
        """轮询授权状态"""
        max_attempts = 120  # 10分钟
        attempts = 0
        poll_interval = 5
        
        while self.running and attempts < max_attempts:
            try:
                result = self.api_client.poll_auth_status(self.device_code)
            except Exception as e:
                print(f"轮询网络错误: {e}")
                # 网络错误时继续轮询，不中断
                self.msleep(poll_interval * 1000)
                attempts += 1
                continue
            
            if result:
                if result.get("status") == "ok":
                    self.auth_success.emit(result.get("data", {}))
                    break
                elif result.get("status") == "error":
                    self.auth_failed.emit(result.get("error", "授权失败"))
                    break
                else:
                    self.status_update.emit("等待用户扫码...")
            
            self.msleep(poll_interval * 1000)
            attempts += 1
        
        if attempts >= max_attempts:
            self.auth_failed.emit("授权超时")
    
    def stop(self):
        """停止轮询"""
        self.running = False


class AutoAuthThread(QThread):
    """自动授权轮询线程（无需登录）"""
    
    auth_success = Signal(dict)
    auth_failed = Signal(str)
    status_update = Signal(str)
    
    def __init__(self, api_client, device_code: str):
        super().__init__()
        self.api_client = api_client
        self.device_code = device_code
        self.running = True
    
    def run(self):
        """轮询授权状态"""
        self.running = True  # 确保running状态正确初始化
        max_attempts = 120  # 10分钟
        attempts = 0
        poll_interval = 5  # 遵循设备授权最小间隔建议
        
        while self.running and attempts < max_attempts:
            try:
                result = self.api_client.poll_auto_auth_status(
                    self.device_code, 
                    self.api_client.device_fingerprint
                )
            except Exception as e:
                print(f"轮询网络错误: {e}")
                # 网络错误时继续轮询，不中断
                self.msleep(poll_interval * 1000)
                attempts += 1
                continue
            
            if result:
                if (result.get("status") or "").lower() in ("success", "ok"):
                    # 打印完整成功响应
                    try:
                        print("[AUTH SUCCESS]", json.dumps(result, ensure_ascii=False, indent=2))
                    except Exception:
                        print("[AUTH SUCCESS]", result)
                    # 自动授权成功，设置JWT token
                    jwt_token = result.get("jwt_token")
                    baidu_token = result.get("baidu_token")
                    user_info = result.get("user_info")
                    
                    if jwt_token:
                        self.api_client.user_jwt = jwt_token
                        self.api_client.session.headers.update({'Authorization': f'Bearer {self.api_client.user_jwt}'})
                    if baidu_token:
                        self.api_client.baidu_token = baidu_token
                    if user_info:
                        self.api_client.user_info = user_info
                    try:
                        # 多账号保存与切换
                        uk = str(user_info.get('uk')) if user_info else None
                        if uk:
                            self.api_client.save_account(uk, jwt_token, baidu_token, user_info)
                            self.api_client.set_current_account(uk)
                        # 兼容旧存储
                        self.api_client.save_tokens(jwt_token, baidu_token, user_info)
                    except Exception:
                        pass
                    self.auth_success.emit(result)
                    break
                elif result.get("status") == "error":
                    error_msg_raw = result.get("error") or ""
                    error_msg = error_msg_raw.lower()
                    if "authorization_pending" in error_msg or "not yet completed" in error_msg:
                        # 降低UI刷新频率：仅在每3次更新一次
                        if attempts % 3 == 0:
                            self.status_update.emit("安全提示：二维码仅用于百度网盘授权，服务器不会保存任何个人信息。请在手机端扫码授权。")
                    elif "slow_down" in error_msg:
                        poll_interval = min(poll_interval + 2, 15)
                        if attempts % 3 == 0:
                            self.status_update.emit(f"安全提示：请在手机端确认授权（服务器不保存任何个人信息）。{poll_interval}s后自动重试…")
                    else:
                        print("[AUTH ERROR]", result)
                        self.auth_failed.emit(error_msg_raw or "授权失败")
                        break
                elif result.get("status") == "pending":
                    if attempts % 3 == 0:
                        self.status_update.emit("安全提示：二维码仅用于百度网盘授权，服务器不会保存任何个人信息。请在手机端扫码授权。")
            
            self.msleep(poll_interval * 1000)
            attempts += 1
        
        if attempts >= max_attempts:
            self.auth_failed.emit("授权超时")
    
    def stop(self):
        """停止轮询"""
        self.running = False
