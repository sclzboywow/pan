#!/usr/bin/env python3
"""
登录对话框
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QLineEdit, QPushButton, QTabWidget, QWidget,
                              QMessageBox, QGroupBox, QGridLayout)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from core.api_client import APIClient
from ui.widgets.material_line_edit import MaterialLineEdit
from ui.widgets.material_button import MaterialButton
from core.utils import get_icon_path


class LoginDialog(QDialog):
    """登录对话框"""
    
    login_success = Signal(dict)  # 登录成功信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = APIClient()
        self.auth_thread = None
        
        self.setWindowTitle("用户登录")
        self.setFixedSize(500, 600)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        # 关闭即销毁，避免残留阻塞
        try:
            from PySide6.QtCore import Qt as _Qt
            self.setAttribute(_Qt.WA_DeleteOnClose, True)
        except Exception:
            pass
        
        self.init_ui()
        self.setup_connections()
        
        # 自动启动扫码授权
        self.auth_status_label.setText("正在生成二维码...")
        self.start_auth()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = QLabel("云栈登录")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #1976D2; margin-bottom: 20px;")
        layout.addWidget(title_label)
        
        # 直接显示扫码授权界面
        auth_tab = self.create_auth_tab()
        layout.addWidget(auth_tab)
    
    def create_login_tab(self) -> QWidget:
        """创建登录标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 登录表单
        login_group = QGroupBox("用户登录")
        login_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        login_layout = QGridLayout(login_group)
        login_layout.setSpacing(15)
        
        # 用户名
        login_layout.addWidget(QLabel("用户名:"), 0, 0)
        self.username_edit = MaterialLineEdit("请输入用户名")
        self.username_edit.setText("testuser")
        login_layout.addWidget(self.username_edit, 0, 1)
        
        # 密码
        login_layout.addWidget(QLabel("密码:"), 1, 0)
        self.password_edit = MaterialLineEdit("请输入密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setText("testpass")
        login_layout.addWidget(self.password_edit, 1, 1)
        
        # 登录按钮
        self.login_btn = MaterialButton("登录", "user.png")
        self.login_btn.setFixedHeight(40)
        login_layout.addWidget(self.login_btn, 2, 0, 1, 2)
        
        layout.addWidget(login_group)
        layout.addStretch()
        
        return widget
    
    def create_register_tab(self) -> QWidget:
        """创建注册标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 注册表单
        register_group = QGroupBox("用户注册")
        register_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        register_layout = QGridLayout(register_group)
        register_layout.setSpacing(15)
        
        # 用户名
        register_layout.addWidget(QLabel("用户名:"), 0, 0)
        self.reg_username_edit = MaterialLineEdit("请输入用户名")
        register_layout.addWidget(self.reg_username_edit, 0, 1)
        
        # 密码
        register_layout.addWidget(QLabel("密码:"), 1, 0)
        self.reg_password_edit = MaterialLineEdit("请输入密码")
        self.reg_password_edit.setEchoMode(QLineEdit.Password)
        register_layout.addWidget(self.reg_password_edit, 1, 1)
        
        # 确认密码
        register_layout.addWidget(QLabel("确认密码:"), 2, 0)
        self.reg_confirm_edit = MaterialLineEdit("请再次输入密码")
        self.reg_confirm_edit.setEchoMode(QLineEdit.Password)
        register_layout.addWidget(self.reg_confirm_edit, 2, 1)
        
        # 注册按钮
        self.register_btn = MaterialButton("注册", "user.png")
        self.register_btn.setFixedHeight(40)
        register_layout.addWidget(self.register_btn, 3, 0, 1, 2)
        
        layout.addWidget(register_group)
        layout.addStretch()
        
        return widget
    
    def create_auth_tab(self) -> QWidget:
        """创建授权标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 授权说明
        info_label = QLabel("使用百度网盘APP扫描二维码完成登录授权")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 10px; font-size: 14px;")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 二维码区域
        from ui.widgets.qr_code_widget import QRCodeWidget
        self.qr_widget = QRCodeWidget()
        layout.addWidget(self.qr_widget, alignment=Qt.AlignCenter)
        
        # 用户码显示
        self.user_code_label = QLabel("请使用百度网盘APP扫码")
        self.user_code_label.setAlignment(Qt.AlignCenter)
        self.user_code_label.setStyleSheet("font-weight: bold; color: #1976D2;")
        layout.addWidget(self.user_code_label)
        
        # 状态显示
        self.auth_status_label = QLabel("安全提示：二维码仅用于百度网盘授权，服务器不会保存任何个人信息。请在手机端扫码授权。")
        self.auth_status_label.setAlignment(Qt.AlignCenter)
        self.auth_status_label.setStyleSheet("color: #666;")
        self.auth_status_label.setWordWrap(True)
        layout.addWidget(self.auth_status_label)
        
        # 重新生成二维码按钮（无图标）
        from PySide6.QtWidgets import QPushButton
        self.start_auth_btn = QPushButton("重新生成二维码")
        self.start_auth_btn.setFixedHeight(36)
        layout.addWidget(self.start_auth_btn)
        
        layout.addStretch()
        
        return widget
    
    def setup_connections(self):
        """设置信号连接"""
        # 仅绑定扫码授权按钮
        self.start_auth_btn.clicked.connect(self.start_auth)
        
        # API客户端信号连接
        self.api_client.login_success.connect(self.on_login_success)
        self.api_client.login_failed.connect(self.on_login_failed)
        self.api_client.auth_success.connect(self.on_auth_success)
        self.api_client.auth_failed.connect(self.on_auth_failed)
        self.api_client.api_error.connect(self.on_api_error)
    
    def login(self):
        """用户登录"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入用户名和密码")
            return
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        
        # 异步登录
        self.api_client.login(username, password)
    
    def register(self):
        """用户注册"""
        username = self.reg_username_edit.text().strip()
        password = self.reg_password_edit.text().strip()
        confirm_password = self.reg_confirm_edit.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入用户名和密码")
            return
        
        if password != confirm_password:
            QMessageBox.warning(self, "警告", "两次输入的密码不一致")
            return
        
        self.register_btn.setEnabled(False)
        self.register_btn.setText("注册中...")
        
        # 异步注册
        success = self.api_client.register(username, password)
        if success:
            QMessageBox.information(self, "成功", "注册成功！请切换到登录标签页登录")
            self.register_btn.setText("注册")
            self.register_btn.setEnabled(True)
        else:
            self.register_btn.setText("注册")
            self.register_btn.setEnabled(True)
    
    def start_auth(self):
        """开始扫码授权"""
        # 使用自动授权，无需登录
        auth_data = self.api_client.start_auto_qr_auth()
        if not auth_data:
            QMessageBox.critical(self, "错误", "启动授权失败")
            return
        
        # 兼容后端两种返回结构：顶层字段或 data 内字段
        payload = auth_data.get("data") if isinstance(auth_data, dict) and isinstance(auth_data.get("data"), dict) else auth_data
        
        # 仅使用 scan_qr_url（若后端暂未提供则回退 qrcode_url），不再使用 verification_url
        qr_url = payload.get("scan_qr_url") or payload.get("qrcode_url") or ""
        self.qr_widget.set_qr_code(qr_url)
        
        # 显示用户码，便于人工输入备选
        self.user_code_label.setText(f"用户码: {payload.get('user_code', '')}")
        
        # 开始轮询
        device_code = payload.get("device_code")
        if device_code:
            from ui.threads.auth_thread import AutoAuthThread
            self.auth_thread = AutoAuthThread(self.api_client, device_code)
            self.auth_thread.auth_success.connect(self.on_auth_success)
            self.auth_thread.auth_failed.connect(self.on_auth_failed)
            self.auth_thread.status_update.connect(self.auth_status_label.setText)
            self.auth_thread.start()
    
    def on_login_success(self, data):
        """登录成功处理"""
        self.login_btn.setText("登录")
        self.login_btn.setEnabled(True)
        self.start_auth_btn.setEnabled(True)
        self.auth_status_label.setText("登录成功，可以开始授权")
        QMessageBox.information(self, "成功", "登录成功！")
    
    def on_login_failed(self, error_msg):
        """登录失败处理"""
        self.login_btn.setText("登录")
        self.login_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"登录失败: {error_msg}")
    
    def on_auth_success(self, token_data):
        """授权成功处理"""
        # 显示用户信息
        user_info = token_data.get("user_info", {})
        username = token_data.get("username", "未知用户")
        
        # 更新状态显示
        self.auth_status_label.setText(f"登录成功！欢迎 {username}")
        
        # 向父级发送登录成功信号（刷新主界面等）
        self.login_success.emit(token_data)
        
        # 安全停止轮询线程并断开信号
        if self.auth_thread:
            try:
                self.auth_thread.auth_success.disconnect()
                self.auth_thread.auth_failed.disconnect()
                self.auth_thread.status_update.disconnect()
            except Exception:
                pass
            try:
                if self.auth_thread.isRunning():
                    self.auth_thread.stop()
                    self.auth_thread.wait(500)
            except Exception:
                pass
            self.auth_thread = None
        
        # 异步关闭对话框，避免与当前槽冲突
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.accept)
        except Exception:
            self.accept()
    
    def on_auth_failed(self, error_msg):
        """授权失败处理"""
        self.auth_status_label.setText(f"授权失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"授权失败: {error_msg}")
    
    def on_api_error(self, error_msg):
        """API错误处理"""
        QMessageBox.critical(self, "错误", f"API错误: {error_msg}")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.auth_thread and self.auth_thread.isRunning():
            self.auth_thread.stop()
            self.auth_thread.wait()
        event.accept()
