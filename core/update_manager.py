"""
更新检测管理器
"""
import logging
from typing import Optional, Dict, Any, Callable
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from core.update_api import UpdateApiClient, UpdateApiError, get_default_api_client, set_default_api_client
from ui.dialogs.update_dialog import UpdateNotificationDialog, UpdateCheckDialog

logger = logging.getLogger(__name__)


class UpdateManager(QObject):
    """更新检测管理器"""
    
    # 信号定义
    update_available = Signal(dict)  # 发现更新
    no_update = Signal(dict)  # 无更新
    check_error = Signal(str)  # 检查错误
    check_started = Signal()  # 开始检查
    check_completed = Signal(dict)  # 检查完成
    
    def __init__(self, parent=None, api_base_url: str = "http://localhost:8000", 
                 current_version: str = "1.0.1", platform: str = "desktop"):
        super().__init__(parent)
        
        # 初始化API客户端
        self.api_client = UpdateApiClient(base_url=api_base_url, timeout=10)
        set_default_api_client(self.api_client)
        
        # 应用信息
        self.current_version = current_version
        self.platform = platform
        
        # 状态管理
        self._is_checking = False
        self._last_check_result: Optional[Dict[str, Any]] = None
        
        # 自动检查定时器
        self.auto_check_timer: Optional[QTimer] = None
        self.auto_check_interval = 30 * 60 * 1000  # 30分钟
        
        # 事件监听器
        self._event_listeners: Dict[str, list] = {}
        
        logger.info(f"更新管理器初始化: {current_version} ({platform})")
    
    def add_event_listener(self, event_type: str, callback: Callable):
        """添加事件监听器"""
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(callback)
    
    def remove_event_listener(self, event_type: str, callback: Callable):
        """移除事件监听器"""
        if event_type in self._event_listeners:
            try:
                self._event_listeners[event_type].remove(callback)
            except ValueError:
                pass
    
    def _emit_event(self, event_type: str, data: Any = None):
        """触发事件"""
        # 触发Qt信号
        if event_type == "check_start":
            self.check_started.emit()
        elif event_type == "check_complete":
            self.check_completed.emit(data)
        elif event_type == "update_available":
            self.update_available.emit(data)
        elif event_type == "no_update":
            self.no_update.emit(data)
        elif event_type == "error":
            self.check_error.emit(data if isinstance(data, str) else str(data))
        
        # 触发Python回调
        if event_type in self._event_listeners:
            for callback in self._event_listeners[event_type]:
                try:
                    callback(event_type, data)
                except Exception as e:
                    logger.error(f"事件监听器错误 ({event_type}): {e}")
    
    def check_update(self, show_dialog: bool = True) -> Optional[Dict[str, Any]]:
        """
        检查更新
        
        Args:
            show_dialog: 是否显示检查进度对话框
            
        Returns:
            更新检查结果
        """
        if self._is_checking:
            logger.info("更新检查正在进行中，跳过本次检查")
            return self._last_check_result
        
        if show_dialog:
            self.show_check_dialog()
        else:
            self._perform_check()
        
        return self._last_check_result
    
    def show_check_dialog(self):
        """显示检查进度对话框"""
        dialog = UpdateCheckDialog(
            self.parent(), 
            self.api_client, 
            self.current_version, 
            self.platform
        )
        
        # 连接信号
        dialog.check_completed.connect(self.on_check_dialog_completed)
        dialog.check_error.connect(self.on_check_dialog_error)
        
        # 开始检查
        dialog.start_check()
        dialog.exec()
    
    def on_check_dialog_completed(self, result: Dict[str, Any]):
        """检查对话框完成"""
        if result.get('has_update', False):
            self.on_update_available(result)
        else:
            self.on_no_update(result)
    
    def on_check_dialog_error(self, error: str):
        """检查对话框错误"""
        self.on_check_error(error)
    
    def _perform_check(self):
        """执行检查"""
        self._is_checking = True
        self._emit_event("check_start")
        
        try:
            logger.info("开始检查更新...")
            
            # 调用API检查更新
            result = self.api_client.check_update(
                client_version=self.current_version,
                client_platform=self.platform,
                user_agent="PanClient/1.0.1"
            )
            
            self._last_check_result = result
            
            if result.get('has_update', False):
                logger.info(f"发现新版本: {result.get('message', '')}")
                self.on_update_available(result)
            else:
                logger.info("当前已是最新版本")
                self.on_no_update(result)
            
            self._emit_event("check_complete", result)
            
        except UpdateApiError as e:
            logger.error(f"更新检查API错误: {e}")
            error_result = {
                'has_update': False,
                'current_version': self.current_version,
                'latest_version': None,
                'message': '',
                'force_update': False,
                'error': str(e)
            }
            self._last_check_result = error_result
            self.on_check_error(str(e))
            
        except Exception as e:
            logger.error(f"更新检查失败: {e}")
            error_result = {
                'has_update': False,
                'current_version': self.current_version,
                'latest_version': None,
                'message': '',
                'force_update': False,
                'error': str(e)
            }
            self._last_check_result = error_result
            self.on_check_error(str(e))
            
        finally:
            self._is_checking = False
    
    def on_update_available(self, result: Dict[str, Any]):
        """发现更新"""
        logger.info(f"发现更新: {result.get('message', '')}")
        
        # 发出信号
        self.update_available.emit(result)
        
        # 显示更新对话框
        self.show_update_dialog(result)
    
    def on_no_update(self, result: Dict[str, Any]):
        """无更新"""
        logger.info("当前已是最新版本")
        
        # 发出信号
        self.no_update.emit(result)
        
        # 可选：显示无更新提示
        if hasattr(self, 'show_no_update_message') and self.show_no_update_message:
            QMessageBox.information(
                self.parent() if self.parent() else QApplication.activeWindow(),
                "检查更新",
                "当前已是最新版本"
            )
    
    def on_check_error(self, error: str):
        """检查错误"""
        logger.error(f"更新检查错误: {error}")
        
        # 发出信号
        self.check_error.emit(error)
        
        # 显示错误对话框
        QMessageBox.warning(
            self.parent() if self.parent() else QApplication.activeWindow(),
            "检查更新失败",
            f"检查更新时发生错误：\n{error}"
        )
    
    def show_update_dialog(self, result: Dict[str, Any]):
        """显示更新对话框"""
        dialog = UpdateNotificationDialog(self.parent(), result)
        
        # 连接信号
        dialog.update_now.connect(self.on_update_now)
        dialog.update_later.connect(self.on_update_later)
        
        # 显示对话框
        dialog.exec()
    
    def on_update_now(self, result: Dict[str, Any]):
        """立即更新"""
        logger.info("用户选择立即更新")
        
        # 获取下载链接
        latest_version_info = result.get('latest_version_info', {})
        download_url = latest_version_info.get('download_url', '')
        
        if download_url:
            # 打开下载链接
            import webbrowser
            webbrowser.open(download_url)
            
            # 显示提示
            QMessageBox.information(
                self.parent() if self.parent() else QApplication.activeWindow(),
                "下载开始",
                "正在打开下载页面，请按照页面提示完成更新。\n\n更新完成后请重启应用程序。"
            )
        else:
            QMessageBox.warning(
                self.parent() if self.parent() else QApplication.activeWindow(),
                "下载失败",
                "无法获取下载链接，请稍后重试或联系技术支持。"
            )
    
    def on_update_later(self, result: Dict[str, Any]):
        """稍后更新"""
        logger.info("用户选择稍后更新")
    
    def start_auto_check(self, interval_ms: Optional[int] = None):
        """启动自动检查"""
        if interval_ms:
            self.auto_check_interval = interval_ms
        
        if self.auto_check_timer:
            self.auto_check_timer.stop()
        
        self.auto_check_timer = QTimer()
        self.auto_check_timer.timeout.connect(lambda: self.check_update(show_dialog=False))
        self.auto_check_timer.start(self.auto_check_interval)
        
        logger.info(f"启动自动更新检查，间隔: {self.auto_check_interval}ms")
    
    def stop_auto_check(self):
        """停止自动检查"""
        if self.auto_check_timer:
            self.auto_check_timer.stop()
            self.auto_check_timer = None
            logger.info("停止自动更新检查")
    
    def manual_check(self):
        """手动检查更新"""
        logger.info("用户手动检查更新")
        self.check_update(show_dialog=True)
    
    def get_last_check_result(self) -> Optional[Dict[str, Any]]:
        """获取最后检查结果"""
        return self._last_check_result
    
    def is_checking(self) -> bool:
        """是否正在检查更新"""
        return self._is_checking
    
    def destroy(self):
        """销毁更新管理器"""
        logger.info("销毁更新管理器")
        
        # 停止自动检查
        self.stop_auto_check()
        
        # 清理事件监听器
        self._event_listeners.clear()
        self._last_check_result = None


# 全局更新管理器实例
_global_update_manager: Optional[UpdateManager] = None


def get_global_update_manager() -> Optional[UpdateManager]:
    """获取全局更新管理器"""
    return _global_update_manager


def init_update_manager(parent=None, api_base_url: str = "http://localhost:8000",
                       current_version: str = "1.0.1", platform: str = "desktop") -> UpdateManager:
    """初始化更新管理器"""
    global _global_update_manager
    
    if _global_update_manager:
        _global_update_manager.destroy()
    
    _global_update_manager = UpdateManager(parent, api_base_url, current_version, platform)
    return _global_update_manager


def cleanup_update_manager():
    """清理更新管理器"""
    global _global_update_manager
    
    if _global_update_manager:
        _global_update_manager.destroy()
        _global_update_manager = None


# 便捷函数
def check_update_now():
    """立即检查更新"""
    manager = get_global_update_manager()
    if manager:
        manager.manual_check()


def get_update_status() -> Optional[Dict[str, Any]]:
    """获取更新状态"""
    manager = get_global_update_manager()
    if manager:
        return manager.get_last_check_result()
    return None


def is_update_checking() -> bool:
    """是否正在检查更新"""
    manager = get_global_update_manager()
    if manager:
        return manager.is_checking()
    return False

