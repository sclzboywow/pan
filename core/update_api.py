"""
更新检测API客户端
"""
import requests
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class UpdateApiError(Exception):
    """更新API错误"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class UpdateApiClient:
    """更新检测API客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PanClient/1.0.1'
        })
    
    def check_update(self, client_version: str, client_platform: str = "desktop", 
                    user_agent: Optional[str] = None) -> Dict[str, Any]:
        """
        检查更新 - 使用GET方式（推荐）
        
        Args:
            client_version: 客户端版本号
            client_platform: 客户端平台 (web, desktop, mobile, android, ios)
            user_agent: 用户代理字符串
            
        Returns:
            更新检查结果
        """
        try:
            # 构建查询参数
            params = {
                'client_version': client_version,
                'client_platform': client_platform
            }
            
            if user_agent:
                params['user_agent'] = user_agent
            
            # 发送GET请求
            response = self.session.get(
                f"{self.base_url}/update/check",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise UpdateApiError(
                    f"API请求失败: HTTP {response.status_code}",
                    response.status_code
                )
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise UpdateApiError(f"网络请求失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise UpdateApiError(f"响应解析失败: {str(e)}")
    
    def check_update_post(self, client_version: str, client_platform: str = "desktop",
                         user_agent: Optional[str] = None) -> Dict[str, Any]:
        """
        检查更新 - 使用POST方式
        
        Args:
            client_version: 客户端版本号
            client_platform: 客户端平台
            user_agent: 用户代理字符串
            
        Returns:
            更新检查结果
        """
        try:
            data = {
                'client_version': client_version,
                'client_platform': client_platform
            }
            
            if user_agent:
                data['user_agent'] = user_agent
            
            response = self.session.post(
                f"{self.base_url}/update/check",
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise UpdateApiError(
                    f"API请求失败: HTTP {response.status_code}",
                    response.status_code
                )
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise UpdateApiError(f"网络请求失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise UpdateApiError(f"响应解析失败: {str(e)}")
    
    def get_latest_version(self, platform: str) -> Dict[str, Any]:
        """
        获取最新版本信息
        
        Args:
            platform: 平台类型
            
        Returns:
            最新版本信息
        """
        try:
            response = self.session.get(
                f"{self.base_url}/update/latest",
                params={'platform': platform},
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise UpdateApiError(
                    f"API请求失败: HTTP {response.status_code}",
                    response.status_code
                )
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise UpdateApiError(f"网络请求失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise UpdateApiError(f"响应解析失败: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取服务状态
        
        Returns:
            服务状态信息
        """
        try:
            response = self.session.get(
                f"{self.base_url}/update/status",
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise UpdateApiError(
                    f"API请求失败: HTTP {response.status_code}",
                    response.status_code
                )
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise UpdateApiError(f"网络请求失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise UpdateApiError(f"响应解析失败: {str(e)}")


class VersionComparator:
    """版本比较器"""
    
    @staticmethod
    def parse_version(version: str) -> tuple:
        """
        解析版本号
        返回: (主版本, 次版本, 补丁版本)
        """
        # 移除v前缀
        version = version.lstrip('vV')
        
        # 分离预发布标识
        prerelease = ""
        if '-' in version:
            version, prerelease = version.split('-', 1)
        
        # 解析主版本号
        import re
        parts = re.findall(r'\d+', version)
        version_numbers = [int(part) for part in parts]
        
        # 确保至少有3个部分
        while len(version_numbers) < 3:
            version_numbers.append(0)
        
        return version_numbers[:3], prerelease
    
    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """
        比较两个版本号
        返回: -1 (v1 < v2), 0 (v1 == v2), 1 (v1 > v2)
        """
        v1_nums, v1_prerelease = VersionComparator.parse_version(version1)
        v2_nums, v2_prerelease = VersionComparator.parse_version(version2)
        
        # 比较主版本号
        for i in range(3):
            if v1_nums[i] < v2_nums[i]:
                return -1
            elif v1_nums[i] > v2_nums[i]:
                return 1
        
        # 主版本号相同，比较预发布标识
        if not v1_prerelease and not v2_prerelease:
            return 0
        elif not v1_prerelease:
            return 1  # 正式版本 > 预发布版本
        elif not v2_prerelease:
            return -1  # 预发布版本 < 正式版本
        else:
            return -1 if v1_prerelease < v2_prerelease else (1 if v1_prerelease > v2_prerelease else 0)
    
    @staticmethod
    def is_newer_version(current: str, latest: str) -> bool:
        """检查latest是否比current更新"""
        return VersionComparator.compare_versions(current, latest) < 0
    
    @staticmethod
    def get_version_diff(current: str, latest: str) -> str:
        """获取版本差异描述"""
        v1_nums, v1_prerelease = VersionComparator.parse_version(current)
        v2_nums, v2_prerelease = VersionComparator.parse_version(latest)
        
        # 检查主版本号差异
        if v1_nums[0] != v2_nums[0]:
            return "主版本更新"
        elif v1_nums[1] != v2_nums[1]:
            return "次版本更新"
        elif v1_nums[2] != v2_nums[2]:
            return "补丁更新"
        elif v1_prerelease != v2_prerelease:
            return "预发布版本更新"
        else:
            return "版本相同"


# 默认API客户端实例
_default_api_client: Optional[UpdateApiClient] = None


def get_default_api_client() -> UpdateApiClient:
    """获取默认API客户端"""
    global _default_api_client
    if _default_api_client is None:
        _default_api_client = UpdateApiClient()
    return _default_api_client


def set_default_api_client(api_client: UpdateApiClient):
    """设置默认API客户端"""
    global _default_api_client
    _default_api_client = api_client

