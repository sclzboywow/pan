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
        self.baidu_token: Optional[Dict[str, Any]] = None
        self.session = requests.Session()
        self.device_fingerprint = self.generate_device_fingerprint()
        
        # 设置请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PanClient/1.0.0'
        })
        
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
        """保存token与用户信息到本地"""
        try:
            data = {
                'jwt_token': jwt_token or self.user_jwt,
                'baidu_token': baidu_token or self.baidu_token,
                'user_info': user_info,
            }
            path = self.get_tokens_store_path()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"保存token失败: {e}")
    
    def load_tokens(self):
        """从本地加载token与用户信息"""
        try:
            path = self.get_tokens_store_path()
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8') or '{}')
                self.user_jwt = data.get('jwt_token') or None
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
        """从本地加载账号信息"""
        try:
            p = self._accounts_path()
            data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
            self.accounts = data.get('accounts', {})
            self.current_account_uk = data.get('current_account_uk')
        except Exception:
            self.accounts = {}
            self.current_account_uk = None

    def save_accounts(self):
        """保存账号信息到本地"""
        try:
            p = self._accounts_path()
            payload = {
                'accounts': self.accounts,
                'current_account_uk': self.current_account_uk
            }
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"保存accounts失败: {e}")

    def save_account(self, uk: str, jwt_token: str, baidu_token: Dict[str, Any], user_info: Dict[str, Any], quota: Dict[str, Any] = None):
        """保存单个账号信息"""
        if not hasattr(self, 'accounts') or self.accounts is None:
            self.accounts = {}
        self.accounts[str(uk)] = {
            'jwt_token': jwt_token,
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
                if self.user_jwt:
                    # 更新请求头
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.user_jwt}'
                    })
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
            response = self.session.post(f"{self.base_url}/oauth/device/start_auto")
            if response.status_code == 200:
                return response.json()
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
            response = self.session.post(
                f"{self.base_url}/mcp/user/exec",
                json={"op": operation, "args": args or {}}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"API调用失败: {e}")
            return None
    
    def call_public_api(self, operation: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """调用公共API（无需认证）"""
        try:
            response = self.session.post(
                f"{self.base_url}/mcp/public/exec",
                json={"op": operation, "args": args or {}}
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
        return self.call_api("mkdir", {"dir": dir_path, "folder_name": folder_name})
    
    def delete_file(self, fs_id: str) -> Optional[Dict[str, Any]]:
        """删除文件"""
        return self.call_api("delete", {"fs_id": fs_id})
    
    def move_file(self, fs_id: str, target_dir: str) -> Optional[Dict[str, Any]]:
        """移动文件"""
        return self.call_api("move", {"fs_id": fs_id, "target_dir": target_dir})
    
    def rename_file(self, fs_id: str, new_name: str) -> Optional[Dict[str, Any]]:
        """重命名文件"""
        return self.call_api("rename", {"fs_id": fs_id, "new_name": new_name})
    
    def copy_file(self, fs_id: str, target_dir: str) -> Optional[Dict[str, Any]]:
        """复制文件"""
        return self.call_api("copy", {"fs_id": fs_id, "target_dir": target_dir})
    
    def upload_local_file(self, local_path: str, remote_path: str, 
                         concurrent: int = 3) -> Optional[Dict[str, Any]]:
        """上传本地文件"""
        return self.call_api("upload_local", {
            "local_path": local_path,
            "remote_path": remote_path,
            "concurrent": concurrent
        })
    
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
    
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self.user_jwt is not None
    
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
            headers = {}
            if self.user_jwt:
                headers['Authorization'] = f'Bearer {self.user_jwt}'
            resp = self.session.get(url, params=params, headers=headers)
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"files_list失败: {e}")
            return None

    def files_stats(self):
        try:
            url = f"{self.base_url}/files/stats"
            headers = {}
            if self.user_jwt:
                headers['Authorization'] = f'Bearer {self.user_jwt}'
            resp = self.session.get(url, headers=headers)
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

    def public_download_ticket(self, fsid: Union[int, str] = None, dlink: str = None, ttl: int = 300):
        """公共态：签发下载票据，用于后端流式代理下载"""
        try:
            args: Dict[str, Any] = {}
            if fsid is not None:
                args['fsid'] = int(fsid) if str(fsid).isdigit() else fsid
            if dlink:
                args['dlink'] = dlink
            if ttl is not None:
                args['ttl'] = int(ttl)
            payload = {"op": "download_ticket", "args": args}
            # 显式带上Authorization（公共通道也需要应用JWT）
            headers = {}
            if self.user_jwt:
                headers["Authorization"] = f"Bearer {self.user_jwt}"
            resp = self.session.post(f"{self.base_url}/mcp/public/exec", json=payload, headers=headers or None)
            data = resp.json() if (resp is not None and resp.content) else None
            if not isinstance(data, dict):
                return {"status": "error", "error": "empty_response"}
            return data
        except Exception as e:
            return {"status": "error", "error": str(e)}
