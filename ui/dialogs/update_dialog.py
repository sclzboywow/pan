"""
更新检测对话框
"""
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QFrame, QScrollArea, QWidget, QMessageBox,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QPixmap, QIcon
from typing import Optional, Dict, Any
import logging

from ui.widgets.material_button import MaterialButton
from core.update_api import UpdateApiClient, UpdateApiError

logger = logging.getLogger(__name__)


class UpdateCheckThread(QThread):
    """更新检查线程"""
    
    # 信号定义
    check_started = Signal()
    check_completed = Signal(dict)
    check_error = Signal(str)
    
    def __init__(self, api_client: UpdateApiClient, current_version: str, platform: str):
        super().__init__()
        self.api_client = api_client
        self.current_version = current_version
        self.platform = platform
        self._is_running = False
    
    def run(self):
        """运行检查"""
        self._is_running = True
        self.check_started.emit()
        
        try:
            logger.info(f"开始检查更新: {self.current_version} ({self.platform})")
            
            # 调用API检查更新
            result = self.api_client.check_update(
                client_version=self.current_version,
                client_platform=self.platform,
                user_agent="PanClient/1.0.1"
            )
            
            logger.info(f"更新检查完成: {result.get('has_update', False)}")
            self.check_completed.emit(result)
            
        except UpdateApiError as e:
            logger.error(f"更新检查API错误: {e}")
            self.check_error.emit(str(e))
        except Exception as e:
            logger.error(f"更新检查失败: {e}")
            self.check_error.emit(f"检查更新时发生错误: {str(e)}")
        finally:
            self._is_running = False
    
    def stop(self):
        """停止检查"""
        self._is_running = False
        self.quit()
        self.wait()


class UpdateNotificationDialog(QDialog):
    """更新通知对话框"""
    
    # 信号定义
    update_now = Signal(dict)  # 立即更新
    update_later = Signal(dict)  # 稍后更新
    
    def __init__(self, parent=None, update_result: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.update_result = update_result
        self.setup_ui()
        self.setup_connections()
        
        if update_result:
            self.set_update_result(update_result)
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("发现新版本")
        self.setFixedSize(520, 450)  # 增加尺寸
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(18)  # 减少间距
        layout.setContentsMargins(25, 20, 25, 20)  # 减少边距
        
        # 顶部区域 - 图标和标题
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # 更新图标
        icon_label = QLabel()
        # 尝试多个图标路径
        icon_paths = [
            "resources/icons/info.png",
            "resources/icons/logo.png", 
            "resources/icons/warning.png"
        ]
        
        icon_pixmap = None
        for path in icon_paths:
            if os.path.exists(path):
                icon_pixmap = QPixmap(path).scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                break
        
        if icon_pixmap is None:
            # 如果没有找到图标，创建一个简单的文本图标
            icon_pixmap = QPixmap(56, 56)
            icon_pixmap.fill(Qt.transparent)
            from PySide6.QtGui import QPainter
            painter = QPainter(icon_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(Qt.blue)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(8, 8, 40, 40)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 20, QFont.Bold))
            painter.drawText(icon_pixmap.rect(), Qt.AlignCenter, "i")
            painter.end()
        
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(56, 56)  # 固定图标大小
        header_layout.addWidget(icon_label)
        
        # 标题信息
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        
        self.title_label = QLabel("发现新版本")
        self.title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        self.title_label.setStyleSheet("color: #1976D2; padding: 2px 0px;")
        title_layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("有新版本可用")
        self.subtitle_label.setFont(QFont("Microsoft YaHei", 11))
        self.subtitle_label.setStyleSheet("color: #666666; padding: 2px 0px;")
        title_layout.addWidget(self.subtitle_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #E0E0E0; margin: 5px 0px;")
        layout.addWidget(line)
        
        # 版本信息区域
        version_layout = QVBoxLayout()
        version_layout.setSpacing(10)
        
        version_title = QLabel("版本信息")
        version_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        version_title.setStyleSheet("color: #333333; padding: 2px 0px;")
        version_layout.addWidget(version_title)
        
        # 版本对比
        self.version_info_widget = QWidget()
        version_info_layout = QHBoxLayout(self.version_info_widget)
        version_info_layout.setSpacing(20)  # 增加间距
        version_info_layout.setContentsMargins(10, 10, 10, 10)  # 添加边距
        
        # 当前版本
        current_layout = QVBoxLayout()
        current_layout.setSpacing(6)  # 增加间距
        current_label = QLabel("当前版本")
        current_label.setFont(QFont("Microsoft YaHei", 10))
        current_label.setStyleSheet("color: #666666; padding: 4px 0px;")
        current_layout.addWidget(current_label)
        
        self.current_version_label = QLabel("1.0.0")
        self.current_version_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))  # 增大字体
        self.current_version_label.setStyleSheet("color: #333333; padding: 4px 0px;")
        self.current_version_label.setMinimumHeight(24)  # 设置最小高度
        current_layout.addWidget(self.current_version_label)
        
        version_info_layout.addLayout(current_layout)
        
        # 箭头
        arrow_label = QLabel("→")
        arrow_label.setFont(QFont("Microsoft YaHei", 16))  # 增大箭头
        arrow_label.setStyleSheet("color: #1976D2; padding: 12px 8px;")
        arrow_label.setAlignment(Qt.AlignCenter)
        arrow_label.setMinimumWidth(30)  # 设置最小宽度
        version_info_layout.addWidget(arrow_label)
        
        # 最新版本
        latest_layout = QVBoxLayout()
        latest_layout.setSpacing(6)  # 增加间距
        latest_label = QLabel("最新版本")
        latest_label.setFont(QFont("Microsoft YaHei", 10))
        latest_label.setStyleSheet("color: #666666; padding: 4px 0px;")
        latest_layout.addWidget(latest_label)
        
        self.latest_version_label = QLabel("1.0.1")
        self.latest_version_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))  # 增大字体
        self.latest_version_label.setStyleSheet("color: #1976D2; padding: 4px 0px;")
        self.latest_version_label.setMinimumHeight(24)  # 设置最小高度
        latest_layout.addWidget(self.latest_version_label)
        
        version_info_layout.addLayout(latest_layout)
        version_info_layout.addStretch()
        
        version_layout.addWidget(self.version_info_widget)
        
        # 更新消息
        self.update_message_label = QLabel()
        self.update_message_label.setFont(QFont("Microsoft YaHei", 10))
        self.update_message_label.setStyleSheet("color: #555555; padding: 10px; background-color: #f5f5f5; border-radius: 4px; margin: 5px 0px;")
        self.update_message_label.setWordWrap(True)
        self.update_message_label.setMinimumHeight(40)  # 设置最小高度
        version_layout.addWidget(self.update_message_label)
        
        layout.addLayout(version_layout)
        
        # 发布说明区域
        notes_layout = QVBoxLayout()
        notes_layout.setSpacing(8)
        
        notes_title = QLabel("更新内容")
        notes_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        notes_title.setStyleSheet("color: #333333; padding: 2px 0px;")
        notes_layout.addWidget(notes_title)
        
        # 直接使用QTextEdit，不嵌套滚动区域
        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMaximumHeight(100)  # 限制高度
        self.notes_text.setFont(QFont("Microsoft YaHei", 9))
        self.notes_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #f9f9f9;
                padding: 8px;
                line-height: 1.4;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
        """)
        
        notes_layout.addWidget(self.notes_text)
        
        layout.addLayout(notes_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        # 稍后更新按钮
        self.later_btn = MaterialButton("稍后更新")
        self.later_btn.setFixedSize(90, 36)  # 固定按钮大小
        self.later_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666666;
                border: 1px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #ccc;
            }
        """)
        button_layout.addWidget(self.later_btn)
        
        # 立即更新按钮
        self.update_btn = MaterialButton("立即更新")
        self.update_btn.setFixedSize(90, 36)  # 固定按钮大小
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #1565c0;
            }
        """)
        button_layout.addWidget(self.update_btn)
        
        layout.addLayout(button_layout)
    
    def setup_connections(self):
        """设置信号连接"""
        self.update_btn.clicked.connect(self.on_update_now)
        self.later_btn.clicked.connect(self.on_update_later)
    
    def set_update_result(self, result: Dict[str, Any]):
        """设置更新结果"""
        self.update_result = result
        
        # 更新UI显示
        current_version = result.get('current_version', '1.0.0')
        latest_version = result.get('latest_version', '1.0.1')
        
        self.current_version_label.setText(current_version)
        self.latest_version_label.setText(latest_version)
        
        # 更新消息
        update_message = result.get('message', '')
        self.update_message_label.setText(update_message)
        
        # 发布说明
        latest_version_info = result.get('latest_version_info', {})
        release_notes = latest_version_info.get('release_notes', '')
        self.notes_text.setPlainText(release_notes)
        
        # 更新类型和按钮样式
        force_update = result.get('force_update', False)
        
        if force_update:
            self.title_label.setText("强制更新")
            self.subtitle_label.setText("必须更新才能继续使用")
            self.later_btn.setVisible(False)
            self.update_btn.setText("立即更新")
            self.update_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 4px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
            """)
        else:
            self.title_label.setText("发现新版本")
            self.subtitle_label.setText("有新版本可用")
    
    def on_update_now(self):
        """立即更新"""
        if self.update_result:
            # 获取下载链接
            latest_version_info = self.update_result.get('latest_version_info', {})
            download_url = latest_version_info.get('download_url', '')
            
            if download_url:
                # 打开下载链接
                import webbrowser
                webbrowser.open(download_url)
                
                # 显示提示
                QMessageBox.information(
                    self, 
                    "下载开始", 
                    "正在打开下载页面，请按照页面提示完成更新。\n\n更新完成后请重启应用程序。"
                )
            else:
                QMessageBox.warning(self, "下载失败", "无法获取下载链接")
            
            self.update_now.emit(self.update_result)
            self.accept()
    
    def on_update_later(self):
        """稍后更新"""
        if self.update_result:
            self.update_later.emit(self.update_result)
        self.accept()


class UpdateCheckDialog(QDialog):
    """更新检查对话框"""
    
    check_completed = Signal(dict)
    check_error = Signal(str)
    
    def __init__(self, parent=None, api_client: Optional[UpdateApiClient] = None, 
                 current_version: str = "1.0.0", platform: str = "desktop"):
        super().__init__(parent)
        self.api_client = api_client or UpdateApiClient()
        self.current_version = current_version
        self.platform = platform
        self.check_thread: Optional[UpdateCheckThread] = None
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("检查更新")
        self.setFixedSize(350, 180)  # 增加高度和宽度
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)  # 减少间距
        layout.setContentsMargins(25, 20, 25, 20)  # 减少边距
        
        # 图标和文本
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(15)  # 图标和文本间距
        
        icon_label = QLabel()
        # 尝试多个图标路径
        icon_paths = [
            "resources/icons/info.png",
            "resources/icons/logo.png", 
            "resources/icons/warning.png"
        ]
        
        icon_pixmap = None
        for path in icon_paths:
            if os.path.exists(path):
                icon_pixmap = QPixmap(path).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                break
        
        if icon_pixmap is None:
            # 如果没有找到图标，创建一个简单的文本图标
            icon_pixmap = QPixmap(40, 40)
            icon_pixmap.fill(Qt.transparent)
            from PySide6.QtGui import QPainter
            painter = QPainter(icon_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(Qt.blue)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(4, 4, 32, 32)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 16, QFont.Bold))
            painter.drawText(icon_pixmap.rect(), Qt.AlignCenter, "i")
            painter.end()
        
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(40, 40)  # 固定图标大小
        icon_layout.addWidget(icon_label)
        
        # 文本区域
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        
        self.text_label = QLabel("正在检查更新...")
        self.text_label.setFont(QFont("Microsoft YaHei", 11))
        self.text_label.setStyleSheet("color: #333333; padding: 2px 0px;")
        self.text_label.setWordWrap(True)  # 允许文字换行
        text_layout.addWidget(self.text_label)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #666666; padding: 2px 0px;")
        self.status_label.setWordWrap(True)
        text_layout.addWidget(self.status_label)
        
        icon_layout.addLayout(text_layout)
        icon_layout.addStretch()
        
        layout.addLayout(icon_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.progress_bar.setFixedHeight(20)  # 固定进度条高度
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                text-align: center;
                background-color: #f5f5f5;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #2196f3;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = MaterialButton("取消")
        self.cancel_btn.setFixedSize(100, 36)  # 增加按钮宽度和高度
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #ccc;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def setup_connections(self):
        """设置信号连接"""
        pass
    
    def start_check(self):
        """开始检查"""
        if self.check_thread and self.check_thread.isRunning():
            return
        
        # 创建检查线程
        self.check_thread = UpdateCheckThread(
            self.api_client, self.current_version, self.platform
        )
        
        # 连接信号
        self.check_thread.check_started.connect(self.on_check_started)
        self.check_thread.check_completed.connect(self.on_check_completed)
        self.check_thread.check_error.connect(self.on_check_error)
        
        # 启动线程
        self.check_thread.start()
    
    def on_check_started(self):
        """检查开始"""
        self.text_label.setText("正在检查更新...")
        self.status_label.setText("正在连接服务器...")
        self.progress_bar.setRange(0, 0)
        self.cancel_btn.setText("取消")
    
    def on_check_completed(self, result: Dict[str, Any]):
        """检查完成"""
        has_update = result.get('has_update', False)
        if has_update:
            self.text_label.setText("发现新版本")
            self.status_label.setText(f"最新版本: {result.get('latest_version', 'N/A')}")
        else:
            self.text_label.setText("检查完成")
            self.status_label.setText("当前已是最新版本")
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.cancel_btn.setText("关闭")
        
        # 延迟关闭对话框
        QTimer.singleShot(3000, self.accept)
        
        # 发出信号
        self.check_completed.emit(result)
    
    def on_check_error(self, error: str):
        """检查错误"""
        self.text_label.setText("检查失败")
        self.status_label.setText("网络连接异常")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.cancel_btn.setText("关闭")
        
        # 发出信号
        self.check_error.emit(error)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.check_thread and self.check_thread.isRunning():
            self.check_thread.stop()
        event.accept()

