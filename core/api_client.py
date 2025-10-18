#!/usr/bin/env python3
"""
后端API客户端
用于对接云栈后端服务
"""

import requests
import json
import base64
import hashlib
import platform
import uuid
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from PySide6.QtCore import QObject, Signal
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class APIClient(QObject):
    """后端API客户端"""
    
    # 信号定义
    login_success = Signal(dict)  # 登录成功信号
    login_failed = Signal(str)    # 登录失败信号
    auth_success = Signal(dict)   # 授权成功信号
    auth_failed = Signal(str)     # 授权失败信号
    api_error = Signal(str)       # API错误信号
    
    def __init__(self, base_url: str = "http://118.24.67.10"):
        super().__init__()
        self.base_url = base_url
        self.user_jwt: Optional[str] = None
        self.refresh_token_value: Optional[str] = None
        self.baidu_token: Optional[Dict[str, Any]] = None
        self.session = requests.Session()
        self.device_fingerprint = self.generate_device_fingerprint()
        
        # 设置请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PanClient/1.0.0'
        })
        
        # 初始化加密密钥
        self._encryption_key = self._generate_encryption_key()
        
        # 尝试加载本地token（免登录）
        self.load_tokens()
        # 多账号：加载账号库并切换到当前账号
        self.load_accounts()
        if getattr(self, 'current_account_uk', None):
            self._apply_account(self.current_account_uk)
        elif self.user_jwt:
            self.session.headers.update({'Authorization': f'Bearer {self.user_jwt}'})
    
    # ---------- 单账号旧存储（兼容） ----------
    def get_tokens_store_path(self) -> Path:
        """获取本地token存储路径"""
        base = Path(os.environ.get('APPDATA') or Path.home() / '.pan_client')
        base.mkdir(parents=True, exist_ok=True)
        return base / 'auth_tokens.json'
    
    def save_tokens(self, jwt_token: Optional[str], baidu_token: Optional[Dict[str, Any]] = None, user_info: Optional[Dict[str, Any]] = None):
        """保存token与用户信息到本地（加密存储）"""
        try:
            data = {
                'jwt_token': jwt_token or self.user_jwt,
                'refresh_token': self.refresh_token_value,
                'baidu_token': baidu_token or self.baidu_token,
                'user_info': user_info,
            }
            
            # 将数据转换为JSON字符串
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            
            # 加密数据
            encrypted_data = self._encrypt_data(json_data)
            
            # 保存加密后的数据
            path = self.get_tokens_store_path()
            path.write_text(encrypted_data, encoding='utf-8')
        except Exception as e:
            print(f"保存token失败: {e}")
    
    def load_tokens(self):
        """从本地加载token与用户信息（解密读取）"""
        try:
            path = self.get_tokens_store_path()
            if path.exists():
                encrypted_data = path.read_text(encoding='utf-8')
                if encrypted_data:
                    # 尝试解密数据
                    try:
                        decrypted_data = self._decrypt_data(encrypted_data)
                        data = json.loads(decrypted_data)
                    except Exception:
                        # 如果解密失败，可能是旧格式的明文数据，尝试直接解析
                        data = json.loads(encrypted_data)
                    
                    self.user_jwt = data.get('jwt_token') or None
                    self.refresh_token_value = data.get('refresh_token') or None
                    self.baidu_token = data.get('baidu_token') or None
                    self.user_info = data.get('user_info') or None
        except Exception as e:
            print(f"加载token失败: {e}")
    
    def clear_tokens(self):
        """清除本地token"""
        try:
            path = self.get_tokens_store_path()
            if path.exists():
                path.unlink()
        except Exception:
            pass

    # ---------- 多账号存储 ----------
    def _accounts_dir(self) -> Path:
        """获取账号存储目录"""
        base = Path(os.environ.get('APPDATA') or Path.home() / '.pan_client')
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _accounts_path(self) -> Path:
        """获取账号存储文件路径"""
        return self._accounts_dir() / 'accounts.json'

    def load_accounts(self):
        """从本地加载账号信息（解密读取）"""
        try:
            p = self._accounts_path()
            if p.exists():
                encrypted_data = p.read_text(encoding='utf-8')
                if encrypted_data:
                    # 尝试解密数据
                    try:
                        decrypted_data = self._decrypt_data(encrypted_data)
                        data = json.loads(decrypted_data)
                    except Exception:
                        # 如果解密失败，可能是旧格式的明文数据，尝试直接解析
                        data = json.loads(encrypted_data)
                else:
                    data = {}
            else:
                data = {}
            
            self.accounts = data.get('accounts', {})
            self.current_account_uk = data.get('current_account_uk')
        except Exception:
            self.accounts = {}
            self.current_account_uk = None

    def save_accounts(self):
        """保存账号信息到本地（加密存储）"""
        try:
            p = self._accounts_path()
            payload = {
                'accounts': self.accounts,
                'current_account_uk': self.current_account_uk
            }
            
            # 将数据转换为JSON字符串
            json_data = json.dumps(payload, ensure_ascii=False, indent=2)
            
            # 加密数据
            encrypted_data = self._encrypt_data(json_data)
            
            # 保存加密后的数据
            p.write_text(encrypted_data, encoding='utf-8')
        except Exception as e:
            print(f"保存accounts失败: {e}")

    def save_account(self, uk: str, jwt_token: str, baidu_token: Dict[str, Any], user_info: Dict[str, Any], quota: Dict[str, Any] = None):
        """保存单个账号信息"""
        if not hasattr(self, 'accounts') or self.accounts is None:
            self.accounts = {}
        self.accounts[str(uk)] = {
            'jwt_token': jwt_token,
            'refresh_token': self.refresh_token_value,
            'baidu_token': baidu_token,
            'user_info': user_info,
            'quota': quota or user_info.get('quota')
        }
        self.current_account_uk = str(uk)
        self.save_accounts()

    def set_current_account(self, uk: str) -> bool:
        """切换当前账号"""
        if not hasattr(self, 'accounts') or str(uk) not in self.accounts:
            return False
        self.current_account_uk = str(uk)
        self.save_accounts()
        self._apply_account(self.current_account_uk)
        return True

    def _apply_account(self, uk: str):
        """应用指定账号的token和用户信息"""
        acct = self.accounts.get(str(uk)) or {}
        self.user_jwt = acct.get('jwt_token')
        self.refresh_token_value = acct.get('refresh_token')
        self.baidu_token = acct.get('baidu_token')
        self.user_info = acct.get('user_info')
        if self.user_jwt:
            self.session.headers.update({'Authorization': f'Bearer {self.user_jwt}'})
        else:
            if 'Authorization' in self.session.headers:
                del self.session.headers['Authorization']

    def switch_account(self, uk: str) -> bool:
        """切换到指定账号"""
        return self.set_current_account(uk)

    def remove_account(self, uk: str):
        """删除指定账号"""
        if hasattr(self, 'accounts') and str(uk) in self.accounts:
            self.accounts.pop(str(uk))
            # 若删的是当前账号，清空当前并移到任一剩余账号
            if self.current_account_uk == str(uk):
                self.current_account_uk = next(iter(self.accounts.keys()), None)
                if self.current_account_uk:
                    self._apply_account(self.current_account_uk)
                else:
                    # 无账号时清状态
                    self.logout()
            self.save_accounts()
    
    def generate_device_fingerprint(self) -> str:
        """生成设备指纹"""
        try:
            # 收集设备信息
            device_info = {
                "platform": platform.system(),
                "machine": platform.machine(),
                "hostname": platform.node(),
                "mac_address": hex(uuid.getnode()),
                "processor": platform.processor()
            }
            
            # 生成稳定的设备指纹
            fingerprint = hashlib.md5(
                json.dumps(device_info, sort_keys=True).encode()
            ).hexdigest()
            
            return fingerprint
        except Exception as e:
            print(f"生成设备指纹失败: {e}")
            # 使用备用方案
            return hashlib.md5(f"fallback_{uuid.uuid4()}".encode()).hexdigest()
    
    def _generate_encryption_key(self) -> bytes:
        """生成加密密钥"""
        try:
            # 使用设备指纹作为盐值
            salt = self.device_fingerprint.encode()[:16]  # 取前16字节作为盐值
            # 使用固定的密码短语（可以基于设备信息生成）
            password = f"pan_client_{self.device_fingerprint}".encode()
            
            # 使用PBKDF2生成密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            return key
        except Exception as e:
            print(f"生成加密密钥失败: {e}")
            # 使用备用方案
            fallback_key = hashlib.sha256(f"fallback_{self.device_fingerprint}".encode()).digest()
            return base64.urlsafe_b64encode(fallback_key)
    
    def _encrypt_data(self, data: str) -> str:
        """加密数据"""
        try:
            fernet = Fernet(self._encryption_key)
            encrypted_data = fernet.encrypt(data.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            print(f"加密数据失败: {e}")
            return data  # 加密失败时返回原数据
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """解密数据"""
        try:
            fernet = Fernet(self._encryption_key)
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            print(f"解密数据失败: {e}")
            return encrypted_data  # 解密失败时返回原数据
    
    def login(self, username: str, password: str) -> bool:
        """用户登录"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.user_jwt = data.get("access_token")
                self.refresh_token_value = data.get("refresh_token")
                if self.user_jwt:
                    # 更新请求头
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.user_jwt}'
                    })
                    # 保存token到本地
                    self.save_tokens(self.user_jwt, self.baidu_token, getattr(self, 'user_info', None))
                    self.login_success.emit(data)
                    return True
            
            self.login_failed.emit("登录失败，请检查用户名和密码")
            return False
            
        except requests.exceptions.RequestException as e:
            error_msg = f"网络连接失败: {str(e)}"
            self.login_failed.emit(error_msg)
            return False
        except Exception as e:
            error_msg = f"登录失败: {str(e)}"
            self.login_failed.emit(error_msg)
            return False
    
    def register(self, username: str, password: str) -> bool:
        """用户注册"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/register",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                return True
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("detail", "注册失败")
                self.api_error.emit(error_msg)
                return False
                
        except requests.exceptions.RequestException as e:
            error_msg = f"网络连接失败: {str(e)}"
            self.api_error.emit(error_msg)
            return False
        except Exception as e:
            error_msg = f"注册失败: {str(e)}"
            self.api_error.emit(error_msg)
            return False
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        if not self.user_jwt:
            return None
        
        try:
            response = self.session.get(f"{self.base_url}/auth/me")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return None
    
    def start_qr_auth(self) -> Optional[Dict[str, Any]]:
        """启动扫码授权"""
        if not self.user_jwt:
            return None
        
        try:
            response = self.session.post(f"{self.base_url}/oauth/device/start")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"启动授权失败: {e}")
            return None
    
    def start_auto_qr_auth(self) -> Optional[Dict[str, Any]]:
        """启动自动扫码授权（无需登录）"""
        try:
            # 使用端口8000
            response = self.session.post(f"{self.base_url}/oauth/device/start_auto")
            print(f"[DEBUG] 启动自动授权状态码: {response.status_code}")
            if response.content:
                print(f"[DEBUG] 启动自动授权响应: {response.text[:200]}...")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[DEBUG] 启动自动授权失败: HTTP {response.status_code}")
                if response.content:
                    try:
                        error_data = response.json()
                        print(f"[DEBUG] 错误详情: {error_data}")
                    except:
                        print(f"[DEBUG] 错误内容: {response.text}")
                return None
        except Exception as e:
            print(f"启动自动授权失败: {e}")
            return None
    
    def poll_auth_status(self, device_code: str) -> Optional[Dict[str, Any]]:
        """轮询授权状态"""
        if not self.user_jwt:
            return None
        
        try:
            response = self.session.post(
                f"{self.base_url}/oauth/device/poll",
                params={"device_code": device_code}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"轮询失败: {e}")
            return None
    
    def poll_auto_auth_status(self, device_code: str, device_fingerprint: str = None) -> Optional[Dict[str, Any]]:
        """轮询自动授权状态"""
        try:
            params = {"device_code": device_code}
            if device_fingerprint:
                params["device_fingerprint"] = device_fingerprint
                
            # 使用端口8000
            response = self.session.post(
                f"{self.base_url}/oauth/device/poll_auto",
                params=params
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"轮询自动授权失败: {e}")
            return None
    
    def call_api(self, operation: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """调用百度网盘API"""
        if not self.user_jwt:
            return None
        
        try:
            # 确保请求头包含Authorization
            headers = {"Authorization": f"Bearer {self.user_jwt}"}
            response = self.session.post(
                f"{self.base_url}/mcp/user/exec",
                json={"op": operation, "args": args or {}},
                headers=headers
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [401, 403]:
                # Token过期，尝试刷新
                print(f"[DEBUG] API调用失败 (HTTP {response.status_code})，尝试刷新token...")
                if self.refresh_token():
                    # 刷新成功，重试请求
                    headers = {"Authorization": f"Bearer {self.user_jwt}"}
                    response = self.session.post(
                        f"{self.base_url}/mcp/user/exec",
                        json={"op": operation, "args": args or {}},
                        headers=headers
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        print(f"[DEBUG] 重试后仍然失败: HTTP {response.status_code}")
            return None
        except Exception as e:
            print(f"API调用失败: {e}")
            return None
    
    def call_public_api(self, operation: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """调用公共API（默认也携带JWT，以满足后端统一鉴权）"""
        try:
            headers = {}
            if self.user_jwt:
                headers['Authorization'] = f'Bearer {self.user_jwt}'
            response = self.session.post(
                f"{self.base_url}/mcp/public/exec",
                json={"op": operation, "args": args or {}},
                headers=headers or None
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"公共API调用失败: {e}")
            return None
    
    def get_quota(self) -> Optional[Dict[str, Any]]:
        """获取配额信息"""
        return self.call_api("quota")
    
    def get_quota_info(self) -> Optional[Dict[str, Any]]:
        """获取网盘配额，返回 data 或 None"""
        try:
            result = self.get_quota()
            if result and result.get('status') == 'ok':
                return result.get('data') or {}
            return None
        except Exception as e:
            print(f"获取配额失败: {e}")
            return None

    def get_quota_today(self) -> Optional[Dict[str, Any]]:
        """获取用户今日阅读/下载/分享共用配额（需登录）"""
        if not self.user_jwt:
            return None
        try:
            resp = self.session.get(f"{self.base_url}/quota/today")
            if resp.status_code == 200:
                return resp.json()
            # 返回统一错误结构
            try:
                data = resp.json()
            except Exception:
                data = {"error": resp.text or str(resp.status_code)}
            return {"status": "error", "error": data.get("error") or data}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ---------- 前置查重（MD5） ----------
    def files_dedup_md5(self, md5_hex: str, sample_limit: int = 5) -> Optional[Dict[str, Any]]:
        """查重：GET /files/dedup/md5?md5=...&sample_limit=...（需登录）"""
        if not self.user_jwt:
            return {"status": "error", "error": "not_logged_in"}
        try:
            url = f"{self.base_url}/files/dedup/md5"
            headers = {"Authorization": f"Bearer {self.user_jwt}"}
            params = {"md5": md5_hex, "sample_limit": int(sample_limit)}
            resp = self.session.get(url, params=params, headers=headers)
            return resp.json() if resp.content else {"status": "error", "error": "empty_response"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def refresh_and_cache_user_quota(self):
        """拉取配额并写入本地缓存的 user_info.quota"""
        quota = self.get_quota_info()
        if quota is not None:
            if not hasattr(self, 'user_info') or self.user_info is None:
                self.user_info = {}
            self.user_info['quota'] = quota
            # 写回当前账号
            if getattr(self, 'current_account_uk', None):
                uk = self.current_account_uk
                acct = self.accounts.get(str(uk)) or {}
                acct['user_info'] = self.user_info
                acct['quota'] = quota
                self.accounts[str(uk)] = acct
                self.save_accounts()
            self.save_tokens(None, None, self.user_info)
    
    def list_files(self, dir_path: str = "/", limit: int = 100) -> Optional[Dict[str, Any]]:
        """获取文件列表"""
        return self.call_api("list_files", {"dir": dir_path, "limit": limit})
    
    def list_images(self, dir_path: str = "/", limit: int = 100) -> Optional[Dict[str, Any]]:
        """获取图片列表"""
        return self.call_api("list_images", {"dir": dir_path, "limit": limit})
    
    def list_docs(self, dir_path: str = "/", limit: int = 100) -> Optional[Dict[str, Any]]:
        """获取文档列表"""
        return self.call_api("list_docs", {"dir": dir_path, "limit": limit})
    
    def list_videos(self, dir_path: str = "/", limit: int = 100) -> Optional[Dict[str, Any]]:
        """获取视频列表"""
        return self.call_api("list_videos", {"dir": dir_path, "limit": limit})
    
    def create_folder(self, dir_path: str, folder_name: str) -> Optional[Dict[str, Any]]:
        """创建文件夹"""
        # 使用path和rtype参数格式（与后端API规范一致）
        # 构建完整路径：dir_path + "/" + folder_name
        import posixpath
        full_path = posixpath.join(dir_path, folder_name)
        return self.call_api("mkdir", {"path": full_path, "rtype": 0})
    
    def delete_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """删除文件"""
        # 使用路径格式的filelist参数
        filelist = [file_path]
        return self.call_api("delete", {"filelist": json.dumps(filelist), "async": 1, "ondup": "overwrite"})
    
    def move_file(self, source_path: str, target_dir: str, new_name: str = None) -> Optional[Dict[str, Any]]:
        """移动文件"""
        # 使用路径格式的filelist参数
        move_item = {"path": source_path, "dest": target_dir}
        if new_name:
            move_item["newname"] = new_name
        filelist = [move_item]
        return self.call_api("move", {"filelist": json.dumps(filelist), "async": 1, "ondup": "overwrite"})
    
    def rename_file(self, file_path: str, new_name: str) -> Optional[Dict[str, Any]]:
        """重命名文件"""
        # 使用移动操作实现重命名（移动到同一目录但使用新名称）
        import posixpath
        dir_path = posixpath.dirname(file_path)
        return self.move_file(file_path, dir_path, new_name)
    
    def copy_file(self, source_path: str, target_dir: str) -> Optional[Dict[str, Any]]:
        """复制文件"""
        # 使用路径格式的filelist参数
        filelist = [{"path": source_path, "dest": target_dir}]
        return self.call_api("copy", {"filelist": json.dumps(filelist), "async": 1, "ondup": "overwrite"})
    
    def upload_local_file(self, local_path: str, remote_path: str, 
                         concurrent: int = 3) -> Optional[Dict[str, Any]]:
        """上传本地文件"""
        # 使用规范的参数格式
        return self.call_api("upload_local", {
            "local_file_path": local_path,
            "remote_path": remote_path,
            "max_concurrent": concurrent
        })

    # ---------- 公共/用户：上传（URL/文本/本地/批量） ----------
    def user_upload_url(self, url: str, dir_path: str, filename: str) -> Optional[Dict[str, Any]]:
        """用户态URL上传"""
        return self.call_api("upload_url", {"url": url, "dir": dir_path, "filename": filename})

    def public_upload_url(self, url: str, dir_path: str, filename: str) -> Optional[Dict[str, Any]]:
        return self.call_public_api("upload_url", {"url": url, "dir": dir_path, "filename": filename})

    def _calculate_file_md5(self, file_path: str) -> str:
        """计算文件的MD5值"""
        import hashlib
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"[DEBUG] MD5计算失败: {e}")
            return None

    def user_upload_local_file(self, local_path: str, remote_path: str, md5: str = None) -> Optional[Dict[str, Any]]:
        """用户态本地文件上传 - 使用POST /upload/user接口"""
        try:
            if not self.user_jwt:
                return {"status": "error", "error": "not_logged_in"}
            
            # 从remote_path中提取目录和文件名
            import posixpath
            dir_path = posixpath.dirname(remote_path)
            filename = posixpath.basename(remote_path)
            
            if not filename:
                return {"status": "error", "error": "invalid_filename"}
            
            print(f"[DEBUG] 调用 user_upload_local_file，local_path: {local_path}, remote_path: {remote_path}")
            
            # 如果没有提供MD5，自动计算
            if not md5:
                md5 = self._calculate_file_md5(local_path)
                if md5:
                    print(f"[DEBUG] 自动计算MD5: {md5}")
            
            # 使用新的用户态上传接口
            url = f"{self.base_url}/upload/user"
            with open(local_path, 'rb') as f:
                files = {
                    'file': (filename, f, 'application/octet-stream')
                }
                data = {
                    'dir': dir_path,
                    'filename': filename
                }
                # 可选：提供MD5用于去重
                if md5:
                    data['md5'] = md5
                    print(f"[DEBUG] 提供MD5用于去重: {md5}")
                
                headers = {
                    'Authorization': f'Bearer {self.user_jwt}'
                }
                # 使用requests.post避免session headers Content-Type冲突
                import requests
                resp = requests.post(url, data=data, files=files, headers=headers)
                print(f"[DEBUG] user_upload_local_file 响应状态码: {resp.status_code}")
                if resp.status_code == 200:
                    result = resp.json()
                    print(f"[DEBUG] user_upload_local_file 响应: {result}")
                    return result
                else:
                    error_result = {"status": "error", "error": f"HTTP {resp.status_code}", "response": resp.text}
                    print(f"[DEBUG] user_upload_local_file 错误响应: {error_result}")
                    return error_result
        except Exception as e:
            error_result = {"status": "error", "error": str(e)}
            print(f"[DEBUG] user_upload_local_file 异常: {error_result}")
            return error_result
    
    def user_upload_text(self, dir_path: str, filename: str, content: str) -> Optional[Dict[str, Any]]:
        """用户态文本上传"""
        print(f"[DEBUG] 调用 user_upload_text，dir: {dir_path}, filename: {filename}")
        result = self.call_api("upload_text", {"dir": dir_path, "filename": filename, "content": content})
        print(f"[DEBUG] user_upload_text 响应: {result}")
        return result
    
    def user_upload_url(self, dir_path: str, url: str, filename: str = None) -> Optional[Dict[str, Any]]:
        """用户态URL上传"""
        params = {"dir": dir_path, "url": url}
        if filename:
            params["filename"] = filename
        print(f"[DEBUG] 调用 user_upload_url，dir: {dir_path}, url: {url}, filename: {filename}")
        result = self.call_api("upload_url", params)
        print(f"[DEBUG] user_upload_url 响应: {result}")
        return result

    def public_upload_text(self, content: str, dir_path: str, filename: str) -> Optional[Dict[str, Any]]:
        return self.call_public_api("upload_text", {"content": content, "dir": dir_path, "filename": filename})

    def public_upload_local_file(self, local_path: str, remote_path: str, concurrent: int = 3) -> Optional[Dict[str, Any]]:
        return self.call_public_api("upload_local", {
            "local_path": local_path,
            "remote_path": remote_path,
            "concurrent": concurrent
        })

    def user_upload_batch_url(self, url_list: list, max_concurrent: int = 3) -> Optional[Dict[str, Any]]:
        """用户态批量URL上传"""
        # url_list: [{"url":"...","dir_path":"/用户上传/...","filename":"..."}, ...]
        return self.call_api("upload_batch_url", {"url_list": url_list, "max_concurrent": max_concurrent})

    def public_upload_batch_url(self, url_list: list) -> Optional[Dict[str, Any]]:
        return self.call_public_api("upload_batch_url", {"url_list": url_list})

    def user_upload_batch_text(self, text_list: list, max_concurrent: int = 3) -> Optional[Dict[str, Any]]:
        """用户态批量文本上传"""
        # text_list: [{"content":"...","dir_path":"/用户上传/...","filename":"..."}, ...]
        return self.call_api("upload_batch_text", {"text_list": text_list, "max_concurrent": max_concurrent})

    def public_upload_batch_text(self, text_list: list) -> Optional[Dict[str, Any]]:
        return self.call_public_api("upload_batch_text", {"text_list": text_list})

    def user_upload_batch_local(self, file_list: list, max_concurrent: int = 3) -> Optional[Dict[str, Any]]:
        """用户态批量本地文件上传"""
        # file_list: [{"local_path":"...","remote_path":"/用户上传/..."}, ...]
        return self.call_api("upload_batch_local", {"file_list": file_list, "max_concurrent": max_concurrent})

    def public_upload_batch_local(self, file_list: list) -> Optional[Dict[str, Any]]:
        return self.call_public_api("upload_batch_local", {"file_list": file_list})

    def public_upload_multipart(self, dir_path: str, local_path: str, filename: str = None, md5: str = None) -> Optional[Dict[str, Any]]:
        """公共态：multipart 文件直传到后端 /upload，强制写入 /用户上传 下（需登录）"""
        try:
            if not self.user_jwt:
                return {"status": "error", "error": "not_logged_in"}
            url = f"{self.base_url}/upload"
            fn = filename or (os.path.basename(local_path) if local_path else None)
            if not fn:
                return {"status": "error", "error": "invalid_filename"}
            with open(local_path, 'rb') as f:
                files = {
                    'file': (fn, f, 'application/octet-stream')
                }
                data = {
                    'dir': dir_path,
                    'filename': fn
                }
                # 如果提供了MD5，添加到表单数据中
                if md5:
                    data['md5'] = md5
                headers = {
                    'Authorization': f'Bearer {self.user_jwt}'
                }
                # use a plain requests.post to avoid session headers Content-Type conflict
                resp = requests.post(url, data=data, files=files, headers=headers)
                return resp.json() if resp.content else {"status": "error", "error": "empty_response"}
        except FileNotFoundError:
            return {"status": "error", "error": "local_file_not_found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def upload_url_file(self, url: str, remote_path: str) -> Optional[Dict[str, Any]]:
        """上传URL文件"""
        return self.call_api("upload_url", {
            "url": url,
            "remote_path": remote_path
        })
    
    def upload_text_file(self, content: str, remote_path: str) -> Optional[Dict[str, Any]]:
        """上传文本内容"""
        return self.call_api("upload_text", {
            "content": content,
            "remote_path": remote_path
        })
    
    def search_filename(self, keyword: str, dir_path: str = "/") -> Optional[Dict[str, Any]]:
        """按文件名搜索"""
        return self.call_api("search_filename", {
            "keyword": keyword,
            "dir": dir_path
        })
    
    def search_semantic(self, keyword: str, dir_path: str = "/") -> Optional[Dict[str, Any]]:
        """语义搜索"""
        return self.call_api("search_semantic", {
            "keyword": keyword,
            "dir": dir_path
        })
    
    def create_share_link(self, fs_id: str, password: str = "", 
                         expire_days: int = 7) -> Optional[Dict[str, Any]]:
        """创建分享链接"""
        return self.call_api("share_create", {
            "fs_id": fs_id,
            "password": password,
            "expire_days": expire_days
        })
    
    def add_offline_download(self, url: str, save_path: str) -> Optional[Dict[str, Any]]:
        """添加离线下载任务"""
        return self.call_api("offline_add", {
            "url": url,
            "save_path": save_path
        })
    
    def get_offline_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询离线下载状态"""
        return self.call_api("offline_status", {"task_id": task_id})
    
    def cancel_offline_download(self, task_id: str) -> Optional[Dict[str, Any]]:
        """取消离线下载任务"""
        return self.call_api("offline_cancel", {"task_id": task_id})
    
    def get_quota(self) -> Optional[Dict[str, Any]]:
        """获取配额信息"""
        return self.call_api("quota", {})
    
    def get_file_metas(self, fsids: List[str], thumb: bool = False, extra: bool = False) -> Optional[Dict[str, Any]]:
        """获取文件元信息"""
        return self.call_api("file_metas", {
            "fsids": fsids,
            "thumb": thumb,
            "extra": extra
        })
    
    def _fsid_to_path(self, fsid: str) -> Optional[str]:
        """将fsid转换为路径（内部辅助方法）"""
        try:
            result = self.get_file_metas([fsid])
            if result and result.get('errno') == 0:
                data = result.get('data', {})
                if data and 'list' in data and data['list']:
                    return data['list'][0].get('path')
        except Exception:
            pass
        return None
    
    def move_file_by_fsid(self, fsid: str, target_dir: str, new_name: str = None) -> Optional[Dict[str, Any]]:
        """通过fsid移动文件（兼容性方法）"""
        path = self._fsid_to_path(fsid)
        if not path:
            return {"errno": -9, "msg": "无法获取文件路径"}
        return self.move_file(path, target_dir, new_name)
    
    def copy_file_by_fsid(self, fsid: str, target_dir: str) -> Optional[Dict[str, Any]]:
        """通过fsid复制文件（兼容性方法）"""
        path = self._fsid_to_path(fsid)
        if not path:
            return {"errno": -9, "msg": "无法获取文件路径"}
        return self.copy_file(path, target_dir)
    
    def rename_file_by_fsid(self, fsid: str, new_name: str) -> Optional[Dict[str, Any]]:
        """通过fsid重命名文件（兼容性方法）"""
        path = self._fsid_to_path(fsid)
        if not path:
            return {"errno": -9, "msg": "无法获取文件路径"}
        return self.rename_file(path, new_name)
    
    def delete_file_by_fsid(self, fsid: str) -> Optional[Dict[str, Any]]:
        """通过fsid删除文件（兼容性方法）"""
        path = self._fsid_to_path(fsid)
        if not path:
            return {"errno": -9, "msg": "无法获取文件路径"}
        return self.delete_file(path)
    
    def _handle_api_error(self, response_data: Dict[str, Any]) -> str:
        """统一的API错误处理"""
        if not isinstance(response_data, dict):
            return "未知错误"
        
        data = response_data.get('data', {})
        errno = data.get('errno', 0)
        
        error_messages = {
            0: "操作成功",
            -6: "身份验证失败，请重新登录",
            -7: "文件或目录名错误或无权访问",
            -8: "文件或目录已存在",
            -9: "文件或目录不存在",
            2: "文件不存在或参数错误",
            12: "批量操作中有文件不存在",
            31045: "access_token验证未通过，请重新授权"
        }
        
        return error_messages.get(errno, f"未知错误码: {errno}")
    
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self.user_jwt is not None
    
    def refresh_token(self) -> bool:
        """刷新JWT token"""
        if not self.refresh_token_value:
            print("[DEBUG] 无refresh_token，无法刷新")
            return False
        
        try:
            # 使用刷新接口
            refresh_url = f"{self.base_url}/auth/refresh"
            headers = {
                'Content-Type': 'application/json'
            }
            
            # 发送POST请求，包含refresh_token
            response = self.session.post(refresh_url, json={"refresh_token": self.refresh_token_value}, headers=headers, timeout=10)
            
            print(f"[DEBUG] 刷新请求状态码: {response.status_code}")
            if response.content:
                print(f"[DEBUG] 刷新响应内容: {response.text[:200]}...")
            
            if response.status_code == 200:
                data = response.json()
                new_token = data.get("access_token") or data.get("token")
                new_refresh_token = data.get("refresh_token")
                if new_token:
                    # 更新token
                    self.user_jwt = new_token
                    if new_refresh_token:
                        self.refresh_token_value = new_refresh_token
                    self.session.headers.update({'Authorization': f'Bearer {self.user_jwt}'})
                    
                    # 保存到本地
                    self.save_tokens(self.user_jwt, self.baidu_token, getattr(self, 'user_info', None))
                    
                    # 更新当前账号的token
                    if hasattr(self, 'current_account_uk') and self.current_account_uk:
                        uk = self.current_account_uk
                        if hasattr(self, 'accounts') and uk in self.accounts:
                            self.accounts[uk]['jwt_token'] = new_token
                            if new_refresh_token:
                                self.accounts[uk]['refresh_token'] = new_refresh_token
                            self.save_accounts()
                    
                    print(f"[DEBUG] Token刷新成功: {new_token[:20]}...")
                    return True
                else:
                    print("[DEBUG] Token刷新失败: 响应中无access_token")
                    print(f"[DEBUG] 响应数据: {data}")
                    return False
            else:
                print(f"[DEBUG] Token刷新失败: HTTP {response.status_code}")
                if response.content:
                    try:
                        error_data = response.json()
                        print(f"[DEBUG] 错误详情: {error_data}")
                    except:
                        print(f"[DEBUG] 错误内容: {response.text}")
                return False
                
        except Exception as e:
            print(f"[DEBUG] Token刷新异常: {e}")
            return False
    
    def logout(self):
        """登出：清除内存与本地token"""
        self.user_jwt = None
        self.baidu_token = None
        if hasattr(self, 'user_info'):
            self.user_info = None
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']
        self.clear_tokens()

    def start_login_new_account(self):
        """前端入口：启动登录新账号（弹出扫码）"""
        # 仅作为语义化入口，实际由UI层弹出LoginDialog
        return True

    # ---------- 公共资源：文件数据库接口 ----------
    def files_list(self, page=1, page_size=50, file_path: str = None, category: int = None,
                   file_size_min: int = None, file_size_max: int = None,
                   status: str = None, order_by: str = None, order_desc: bool = None):
        params = {
            'page': page,
            'page_size': page_size
        }
        if file_path:
            params['file_path'] = file_path
        if category is not None:
            params['category'] = category
        if file_size_min is not None:
            params['file_size_min'] = file_size_min
        if file_size_max is not None:
            params['file_size_max'] = file_size_max
        if status:
            params['status'] = status
        if order_by:
            params['order_by'] = order_by
        if order_desc is not None:
            params['order_desc'] = int(bool(order_desc))
        try:
            url = f"{self.base_url}/files/list"
            # 使用session的全局headers，确保JWT token正确传递
            resp = self.session.get(url, params=params, timeout=10)
            
            # 添加调试信息
            print(f"[DEBUG] files_list响应状态码: {resp.status_code}")
            if resp.content:
                print(f"[DEBUG] files_list响应内容: {resp.text[:200]}...")
            
            # 检查是否需要刷新token（仅401/403错误）
            if resp.status_code in [401, 403] and self.user_jwt:
                print(f"[DEBUG] files_list失败 (HTTP {resp.status_code})，尝试刷新token...")
                if self.refresh_token():
                    # 刷新成功，重试请求（使用更新后的全局headers）
                    resp = self.session.get(url, params=params, timeout=10)
            
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"files_list失败: {e}")
            return None

    def files_stats(self):
        try:
            url = f"{self.base_url}/files/stats"
            # 使用session的全局headers，确保JWT token正确传递
            resp = self.session.get(url, timeout=10)
            
            # 检查是否需要刷新token（仅401/403错误）
            if resp.status_code in [401, 403] and self.user_jwt:
                print(f"[DEBUG] files_stats失败 (HTTP {resp.status_code})，尝试刷新token...")
                if self.refresh_token():
                    # 刷新成功，重试请求（使用更新后的全局headers）
                    resp = self.session.get(url, timeout=10)
            
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"files_stats失败: {e}")
            return None

    def files_search(self, keyword: str, limit: int = 20):
        try:
            url = f"{self.base_url}/files/search"
            headers = {}
            if self.user_jwt:
                headers['Authorization'] = f'Bearer {self.user_jwt}'
            resp = self.session.get(url, params={'keyword': keyword, 'limit': limit}, headers=headers)
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"files_search失败: {e}")
            return None

    def files_detail(self, file_id: int):
        try:
            url = f"{self.base_url}/files/{file_id}"
            headers = {}
            if self.user_jwt:
                headers['Authorization'] = f'Bearer {self.user_jwt}'
            resp = self.session.get(url, headers=headers)
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"files_detail失败: {e}")
            return None

    def files_categories(self):
        try:
            url = f"{self.base_url}/files/categories"
            headers = {}
            if self.user_jwt:
                headers['Authorization'] = f'Bearer {self.user_jwt}'
            resp = self.session.get(url, headers=headers)
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"files_categories失败: {e}")
            return None

    def files_statuses(self):
        try:
            url = f"{self.base_url}/files/statuses"
            headers = {}
            if self.user_jwt:
                headers['Authorization'] = f'Bearer {self.user_jwt}'
            resp = self.session.get(url, headers=headers)
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"files_statuses失败: {e}")
            return None

    # ---------- 公共资源举报 ----------
    def public_report_submit(self, target: str, reason: str):
        """提交公共资源举报（需登录）"""
        try:
            if not self.user_jwt:
                return {"status": "error", "error": "not_logged_in"}
            url = f"{self.base_url}/reports/public"
            params = {"target": str(target), "reason": str(reason or '')[:200]}
            headers = {"Authorization": f"Bearer {self.user_jwt}"}
            resp = self.session.post(url, params=params, headers=headers)
            return resp.json() if resp.content else {"status": "error", "error": "empty_response"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def public_report_count(self, target: str):
        """查询被举报次数（公开）"""
        try:
            url = f"{self.base_url}/reports/public/count"
            params = {"target": str(target)}
            resp = self.session.get(url, params=params)
            return resp.json() if resp.content else {"status": "error", "error": "empty_response"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def public_share_create(self, fsids: list, period: int = 7, pwd: str = "", remark: str = ""):
        """创建公共资源分享链接（使用服务态token）"""
        try:
            fsids_arr = [int(x) if str(x).isdigit() else str(x) for x in fsids]
            args = {
                'fsid_list': fsids_arr,
                'fsids': fsids_arr
            }
            if period is not None:
                args['period'] = int(period)
            if pwd:
                args['pwd'] = str(pwd)
            if remark:
                args['remark'] = remark
            resp = self.call_public_api('share_create', args)
            return resp
        except Exception as e:
            print(f"public_share_create失败: {e}")
            return None

    # ---------- 用户态：获取下载直链 ----------
    def user_download_link(self, fsid: str = None, path: str = None, expires_hint: int = 300):
        """获取短时有效的直链dlink（用户态）"""
        if not self.user_jwt:
            return {"status": "error", "error": "not_logged_in"}
        args = {}
        if fsid is not None:
            args['fsid'] = str(fsid)
        if path:
            args['path'] = path
        if expires_hint is not None:
            args['expires_hint'] = int(expires_hint)
        try:
            return self.call_api('download_link', args)
        except Exception as e:
            print(f"user_download_link失败: {e}")
            return {"status": "error", "error": str(e)}

    def user_download_ticket(self, fsid: Union[int, str] = None, path: str = None, ttl: int = 300):
        """用户态：签发后端代理下载票据（支持 fsid 或 path）。"""
        try:
            if not self.user_jwt:
                return {"status": "error", "error": "not_logged_in"}
            args: Dict[str, Any] = {}
            if fsid is not None:
                args['fsid'] = int(fsid) if str(fsid).isdigit() else fsid
            if path:
                args['path'] = path
            if 'fsid' not in args and 'path' not in args:
                # 前端防御：避免误调用导致后端返回 missing_dlink_or_fsid
                try:
                    import traceback
                    print("[DEBUG][TICKET][USER] missing fsid/path. call stack:\n" + ''.join(traceback.format_stack(limit=8)))
                except Exception:
                    pass
                return {"status": "error", "error": "missing_fsid_or_path"}
            if ttl is not None:
                args['ttl'] = int(ttl)
            payload = {"op": "download_ticket", "args": args}
            headers = {"Authorization": f"Bearer {self.user_jwt}"}
            try:
                print(f"[DEBUG][TICKET][USER] payload={payload}")
            except Exception:
                pass
            resp = self.session.post(f"{self.base_url}/mcp/user/exec", json=payload, headers=headers)
            if resp is None or not resp.content:
                return {"status": "error", "error": "empty_response"}
            try:
                print(f"[DEBUG][TICKET][USER] resp_status={resp.status_code} body={resp.text[:300]}...")
            except Exception:
                pass
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def user_download_links(self, fsids: list):
        """批量获取直链列表（用户态）"""
        if not self.user_jwt:
            return {"status": "error", "error": "not_logged_in"}
        try:
            payload = {"op": "download_links", "args": {"fsids": fsids}}
            resp = self.session.post(
                f"{self.base_url}/mcp/user/exec",
                json=payload,
                headers={"Authorization": f"Bearer {self.user_jwt}"}
            )
            return resp.json() if resp.content else {"status":"error","error":"empty_response"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def public_download_links(self, fsids: list):
        """公共态：批量获取直链列表（服务态token）"""
        try:
            args = {"fsids": fsids}
            resp = self.call_public_api('download_links', args)
            return resp
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def public_download_ticket(self, fsid: Union[int, str] = None, path: str = None, ttl: int = 300):
        """公共态：签发下载票据（支持 fsid 或 path），用于后端流式代理下载。"""
        try:
            args: Dict[str, Any] = {}
            if fsid is not None:
                args['fsid'] = int(fsid) if str(fsid).isdigit() else fsid
            if path:
                args['path'] = path
            if ttl is not None:
                args['ttl'] = int(ttl)
            payload = {"op": "download_ticket", "args": args}
            # 显式带上Authorization（公共通道也需要应用JWT）
            headers = {}
            if self.user_jwt:
                headers["Authorization"] = f"Bearer {self.user_jwt}"
            try:
                print(f"[DEBUG][TICKET][PUBLIC] payload={payload}")
            except Exception:
                pass
            resp = self.session.post(f"{self.base_url}/mcp/public/exec", json=payload, headers=headers or None)
            if resp is not None and resp.content:
                try:
                    print(f"[DEBUG][TICKET][PUBLIC] resp_status={resp.status_code} body={resp.text[:300]}...")
                except Exception:
                    pass
            data = resp.json() if (resp is not None and resp.content) else None
            if not isinstance(data, dict):
                return {"status": "error", "error": "empty_response"}
            return data
        except Exception as e:
            return {"status": "error", "error": str(e)}
