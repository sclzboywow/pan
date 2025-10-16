import sys
import os
import time
import hashlib
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                              QTreeView, QFileDialog, QMessageBox, QProgressBar,
                              QStatusBar, QSystemTrayIcon, QMenu, QFrame,
                              QGraphicsDropShadowEffect, QHeaderView, QDialog,
                              QGroupBox, QGridLayout, QAbstractItemView, QStyle,
                              QListWidget, QListWidgetItem, QListView, QFileIconProvider)
from PySide6.QtCore import QFileInfo
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize, QPoint, QPropertyAnimation, Property, QRectF
from PySide6.QtGui import (QStandardItemModel, QStandardItem, QIcon, QFont, 
                          QColor, QPainter, QPen, QPainterPath, QBrush, QPixmap,
                          QMovie)
from core.utils import get_icon_path
from core.api_client import APIClient
from ui.widgets.circular_progress_bar import CircularProgressBar
from ui.widgets.material_line_edit import MaterialLineEdit
from ui.widgets.material_button import MaterialButton
from ui.dialogs import UserInfoDialog, DownloadLimitDialog, LoadingDialog
from ui.dialogs.login_dialog import LoginDialog
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from datetime import datetime
from PySide6.QtWidgets import QStyledItemDelegate, QInputDialog
from PySide6.QtGui import QPalette
import requests
from urllib.parse import urlencode

class ShareDialog(QDialog):
    def __init__(self, parent=None, default_pwd=""):
        super().__init__(parent)
        self.setWindowTitle("创建分享")
        self.setFixedSize(360, 200)
        layout = QVBoxLayout(self)
        form = QGridLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(10)
        # 有效期
        form.addWidget(QLabel("有效期(天):"), 0, 0)
        self.period_input = QLineEdit("7")
        self.period_input.setPlaceholderText("仅支持 1/7/30")
        form.addWidget(self.period_input, 0, 1)
        # 提取码
        form.addWidget(QLabel("提取码(4位):"), 1, 0)
        self.pwd_input = QLineEdit(default_pwd)
        self.pwd_input.setPlaceholderText("a1b2")
        form.addWidget(self.pwd_input, 1, 1)
        # 备注
        form.addWidget(QLabel("备注:"), 2, 0)
        self.remark_input = QLineEdit("感谢您使用云栈分享")
        form.addWidget(self.remark_input, 2, 1)
        layout.addLayout(form)
        # 按钮
        btns = QHBoxLayout()
        ok = MaterialButton("确定")
        cancel = MaterialButton("取消")
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
    
    def get_values(self):
        return self.period_input.text().strip(), self.pwd_input.text().strip(), self.remark_input.text().strip()

class ExitConfirmDialog(QDialog):
    """退出确认对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("确认退出")
        self.setFixedSize(400, 200)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 图标和标题
        title_layout = QHBoxLayout()
        
        # 添加问号图标
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(get_icon_path('warning.png')).pixmap(48, 48))
        title_layout.addWidget(icon_label)
        
        # 标题文本
        title_text = QLabel("确定要退出程序吗？")
        title_text.setFont(QFont("Microsoft YaHei", 14))
        title_text.setStyleSheet("color: #333333;")
        title_layout.addWidget(title_text)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 说明文本
        desc_label = QLabel("程序将完全关闭，所有未保存的数据可能会丢失。")
        desc_label.setFont(QFont("Microsoft YaHei", 10))
        desc_label.setStyleSheet("color: #666666;")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 取消按钮（默认选中）
        cancel_btn = MaterialButton("取消")
        cancel_btn.setDefault(True)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # 确定退出按钮（红色样式）
        exit_btn = MaterialButton("确定")
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 8px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
        """)
        exit_btn.clicked.connect(self.accept)
        button_layout.addWidget(exit_btn)
        
        layout.addLayout(button_layout)

class ActionCellDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, text_color="#333333"):
        super().__init__(parent)
        self.text_color = QColor(text_color)
        self.hover_bg = QColor(self.text_color)
        self.hover_bg.setAlpha(18)
        self.border_color = QColor(self.text_color)
        self.border_color.setAlpha(80)
        self.radius = 10
        self.padding_h = 10
        self.padding_v = 4

    def paint(self, painter, option, index):
        opt = option
        rect = opt.rect.adjusted(6, 4, -6, -4)
        hover = bool(opt.state & QStyle.State_MouseOver)
        if hover:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setBrush(QBrush(self.hover_bg))
            pen = QPen(self.border_color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, self.radius, self.radius)
            painter.restore()
        # 绘制文本
        painter.save()
        painter.setPen(self.text_color)
        painter.drawText(rect, Qt.AlignCenter, index.data())
        painter.restore()

class ProxyDownloadWorker(QThread):
    progress = Signal(float)
    status = Signal(str)
    finished = Signal(str)  # save_path
    failed = Signal(str)

    def __init__(self, base_url: str, ticket: str, save_path: str, tmp_path: str, size_expect: int = 0, app_jwt: str = None, resume_pos: int = 0, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip('/')
        self.ticket = ticket
        self.save_path = save_path
        self.tmp_path = tmp_path
        self.size_expect = size_expect or 0
        self.app_jwt = app_jwt
        self.resume_pos = resume_pos or 0
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _do_request(self, ticket: str):
        headers = {}
        if self.resume_pos > 0:
            headers['Range'] = f'bytes={self.resume_pos}-'
        if self.app_jwt:
            headers['Authorization'] = f"Bearer {self.app_jwt}"
        req_kwargs = {
            'headers': headers,
            'stream': True,
            'timeout': 60,
            'allow_redirects': True,
            'proxies': {"http": None, "https": None}
        }
        proxy_url = f"{self.base_url}/files/proxy_download?ticket={ticket}"
        return requests.get(proxy_url, **req_kwargs)

    def run(self):
        try:
            # 首次请求
            r = self._do_request(self.ticket)
            if r.status_code in (401, 403):
                try:
                    body = r.text[:500]
                except Exception:
                    body = ''
                self.status.emit(f"票据无效，重试中...")
                # 由UI侧在启动前确保ticket有效；这里进行一次重试需要新票据，交由UI侧传入
                # 为保持线程内自洽，这里不自行刷新票据，直接失败返回，由UI层决定是否换票重启线程
                r.close()
                self.failed.emit(f"HTTP {r.status_code}: {body}")
                return
            r.raise_for_status()
            total = int(r.headers.get('Content-Length') or self.size_expect or 0)
            downloaded = self.resume_pos
            mode = 'ab' if self.resume_pos > 0 else 'wb'
            with open(self.tmp_path, mode) as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if self._stopped:
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and downloaded % (256*1024) == 0:
                            pct = downloaded / total * 100
                            self.progress.emit(pct)
            os.replace(self.tmp_path, self.save_path)
            self.finished.emit(self.save_path)
        except Exception as e:
            self.failed.emit(str(e))

class FileManagerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化API客户端
        self.api_client = APIClient()
        
        # 初始化更新检测管理器
        self.init_update_manager()
        
        # 公共资源模式与分页
        self.in_public = False
        self.public_page = 1
        self.public_page_size = 100
        self.public_loading = False
        self.public_has_more = True
        self.public_search_mode = False
        self.public_search_keyword = ""
        self.public_ui_inited = False
        self.public_downloading = False
        
        # 用户态表格初始化标志，避免重复连接信号
        self.user_ui_inited = False
        
        # 初始化UI相关属性
        self.is_vip = True  # 默认为VIP用户体验，以便启用多选等功能

        # 初始化用户信息对话框
        self._user_info_dialog = None
        
        # 初始化分页相关属性
        self.page_size = 1000  # 每页显示数量
        self.current_page = 1
        self.has_more = True
        self.is_loading = False
        self.current_folder = '/'  # 设置默认文件夹
        
        self.initUI()
        self.setup_api_connections()
        
        # 检查登录状态，决定进入哪个页面
        self.check_login_status_and_navigate()
        
        # 设置窗口图标
        self.setWindowIcon(QIcon(get_icon_path('logo.png')))
        
        # 创建系统托盘
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(get_icon_path('logo.png')))
        self.create_tray_icon()
        
        # 设置任务栏图标（Windows系统）
        try:
            import ctypes
            myappid = 'mycompany.sharealbum.app.1.0.1'  # 应用程序ID
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"设置任务栏图标失败: {e}")
        
        # 添加加载对话框
        self.loading_dialog = LoadingDialog(self)
        
        # 连接滚动信号
        self.file_tree.verticalScrollBar().valueChanged.connect(self.check_scroll_position)
        
        # 异步上传任务列表，避免线程被GC回收
        self.active_upload_workers = []
    
    def _friendly_error(self, err_text: str, scene: str = "操作") -> str:
        """将常见错误码转为更友好的中文提示。"""
        t = (err_text or '').lower()
        # 公共态配额
        if 'daily_quota_exceeded' in t or 'http 429' in t or '429' in t:
            return f"{scene}失败：今日公共资源配额已用尽，请明日再试；或者切换到‘我的网盘’在用户态继续{scene}。"
        # 未登录
        if 'not_logged_in' in t or 'login required' in t:
            return f"{scene}失败：需要登录，请先登录后再试。"
        # 用户态百度授权缺失
        if 'user_baidu_token_missing' in t or 'user_not_authorized' in t:
            return f"{scene}失败：需要完成百度网盘授权，请在‘我的信息’中扫码授权后重试。"
        # 403/401 常见情况
        if '403(31045)' in t or '31045' in t:
            return f"{scene}失败：上游风控拦截（31045）。请稍后重试，或更换网络环境。"
        if '31064' in t or 'file is not authorized' in t or 'failed check pr auth' in t:
            return f"{scene}失败：文件受限（31064），上游未授权访问。可稍后重试，或切换到‘我的网盘’在用户态尝试{scene}。"
        if '31326' in t:
            return f"{scene}失败：上游风控（31326）。请稍后重试或更换网络环境。"
        if 'http 403' in t or '403 forbidden' in t:
            return f"{scene}失败：无权限或访问受限（403）。请稍后重试。"
        if 'http 401' in t or 'unauthorized' in t:
            return f"{scene}失败：登录已过期，请重新登录或稍后重试。"
        # 网络与超时
        if 'timeout' in t:
            return f"{scene}失败：网络超时，请检查网络后再试。"
        if 'failed to establish a new connection' in t or 'proxyerror' in t or 'connection' in t:
            return f"{scene}失败：网络连接异常，请检查系统代理或网络设置后再试。"
        # 其它
        return f"{scene}失败：{err_text}"

    def _ensure_mode(self, require_public: bool, scene: str = "操作") -> bool:
        """确保当前处于期望态；不满足时提示并可一键切换。
        返回 True 表示已在期望态；False 表示已触发切换或用户取消。
        """
        try:
            if require_public and not self.in_public:
                reply = QMessageBox.question(
                    self,
                    "模式不匹配",
                    f"当前在‘我的网盘’用户态，需在‘公共资源’完成{scene}。是否切换到公共资源？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.open_public_resources()
                return False
            if (not require_public) and self.in_public:
                reply = QMessageBox.question(
                    self,
                    "模式不匹配",
                    f"当前在‘公共资源’，需在‘我的网盘’完成{scene}。是否切换到我的网盘？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.go_home()
                return False
            return True
        except Exception:
            return require_public == self.in_public

    def setup_api_connections(self):
        """设置API客户端信号连接"""
        self.api_client.login_success.connect(self.on_login_success)
        self.api_client.login_failed.connect(self.on_login_failed)
        self.api_client.auth_success.connect(self.on_auth_success)
        self.api_client.auth_failed.connect(self.on_auth_failed)
        self.api_client.api_error.connect(self.on_api_error)
    
    def check_login_status_and_navigate(self):
        """检查登录状态并导航到相应页面。
        规则更新：程序默认进入公共态，无论是否已登录；用户可通过导航按钮在公共态与用户态间切换。
        """
        if self.api_client.is_logged_in():
            print("[DEBUG] 用户已登录，默认进入公共资源页面")
            self.status_label.setText("已登录 - 公共资源")
            self.open_public_resources()
        else:
            print("[DEBUG] 用户未登录，进入公共资源页面（演示模式）")
            self.status_label.setText("演示模式 - 点击用户信息进行登录")
            self.open_public_resources()
    
    def check_login_status(self):
        """检查登录状态"""
        if self.api_client.is_logged_in():
            # 已登录，加载文件列表
            self.status_label.setText("已登录")
            self.load_files()
        else:
            # 未登录，显示演示数据
            self.status_label.setText("演示模式 - 点击用户信息进行登录")
            self.load_demo_files()
    
    def show_login_dialog(self):
        """显示登录对话框"""
        print(f"[DEBUG] 主界面: API客户端实例ID = {id(self.api_client)}")
        dialog = LoginDialog(self, self.api_client)
        dialog.login_success.connect(self.on_login_success)
        dialog.exec()
    
    def on_login_success(self, data):
        """登录成功处理：保持当前视图（默认公共态），仅更新状态栏"""
        print("[DEBUG] 登录成功，保持当前视图")
        try:
            if self.in_public:
                self.status_label.setText("已登录 - 公共资源")
            else:
                self.status_label.setText("已登录 - 我的网盘")
        except Exception:
            self.status_label.setText("已登录")
    
    def on_login_failed(self, error_msg):
        """登录失败处理"""
        self.status_label.setText(f"登录失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"登录失败: {error_msg}")
    
    def on_auth_success(self, token_data):
        """授权成功处理：保持当前视图（默认公共态），仅更新状态栏"""
        print(f"[DEBUG] on_auth_success: user_jwt={'exists' if self.api_client.user_jwt else 'None'}")
        try:
            if self.in_public:
                self.status_label.setText("已登录 - 公共资源")
            else:
                self.status_label.setText("已登录 - 我的网盘")
        except Exception:
            self.status_label.setText("已登录")
        QMessageBox.information(self, "成功", "百度网盘授权成功！")
    
    def on_auth_failed(self, error_msg):
        """授权失败处理"""
        self.status_label.setText(f"授权失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"授权失败: {error_msg}")
    
    def on_api_error(self, error_msg):
        """API错误处理"""
        self.status_label.setText(f"API错误: {error_msg}")
        QMessageBox.critical(self, "错误", f"API错误: {error_msg}")
    
    def load_files(self):
        """加载文件列表（用户态：使用与公共态相同的表格布局）"""
        # 检查登录状态，添加调试信息
        is_logged_in = self.api_client.is_logged_in()
        user_jwt_info = f"exists (len={len(self.api_client.user_jwt)})" if self.api_client.user_jwt else 'None'
        print(f"[DEBUG] load_files: is_logged_in={is_logged_in}, user_jwt={user_jwt_info}")
        
        if not is_logged_in:
            print("[DEBUG] 用户未登录，进入公共资源页面（演示模式）")
            # 未登录时进入公共资源页面，而不是显示登录对话框
            self.status_label.setText("演示模式 - 点击用户信息进行登录")
            self.open_public_resources()
            return
        
        # 切换为用户态并显示表格视图（与公共态一致的表头）
        self.in_public = False
        try:
            self.file_tree.show()
            self.icon_grid.hide()
        except Exception:
            pass

        self.is_loading = True
        try:
            cur_path = self.current_folder or '/'
            self.status_label.setText(f"用户态：正在加载 {cur_path}")
        except Exception:
            self.status_label.setText("用户态：正在加载文件...")
        
        # 调用API获取文件列表（兼容多种返回格式）
        result = self.api_client.list_files(self.current_folder, self.page_size)
        ok_flag = False
        files = []
        if isinstance(result, dict):
            status_val = str(result.get("status", "")).lower()
            ok_flag = (status_val in ("ok", "success")) or ("data" in result) or ("list" in result)
            data = result.get("data") if isinstance(result.get("data"), dict) else result
            files = (data or {}).get("list") or (data or {}).get("files") or (data or {}).get("items") or []
        elif isinstance(result, list):
            ok_flag = True
            files = result

        if ok_flag:
            try:
                self.display_user_files(files, append=False)
                try:
                    cur_path = self.current_folder or '/'
                    self.status_label.setText(f"用户态：{cur_path} 已加载 {len(files)} 项")
                except Exception:
                    self.status_label.setText(f"用户态：已加载 {len(files)} 项")
            except Exception as e:
                self.status_label.setText(f"显示失败: {e}")
                QMessageBox.critical(self, "错误", f"显示失败: {e}")
        else:
            error_msg = (result or {}).get("error", "加载文件失败") if isinstance(result, dict) else "网络连接失败"
            self.status_label.setText(f"加载失败: {error_msg}")
            QMessageBox.critical(self, "错误", f"加载文件失败: {error_msg}")
        
        self.is_loading = False

    def display_user_files(self, files, append: bool = False):
        """在主列表控件内显示用户态文件列表，表格布局与公共态一致，但操作列改为“打开/下载/分享/删除”。"""
        from PySide6.QtGui import QStandardItem, QStandardItemModel
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QBrush
        try:
            if not append:
                model = QStandardItemModel()
                model.setHorizontalHeaderLabels(["文件名称", "大小", "类别", "修改时间", "打开", "下载", "分享", "删除"])
                self.file_tree.setModel(model)
                try:
                    model.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    for col in range(1, 8):
                        it = model.horizontalHeaderItem(col)
                        if it:
                            it.setTextAlignment(Qt.AlignCenter)
                except Exception:
                    pass
                # 用户态动作点击：安全断开公共态槽，再连接用户态槽
                try:
                    self.file_tree.clicked.disconnect(self.on_public_cell_clicked)
                except Exception:
                    pass
                try:
                    self.file_tree.clicked.disconnect(self.on_user_cell_clicked)
                except Exception:
                    pass
                self.file_tree.clicked.connect(self.on_user_cell_clicked)
                self.user_ui_inited = True
            else:
                model = self.file_tree.model()
                if model is None:
                    model = QStandardItemModel()
                    model.setHorizontalHeaderLabels(["文件名称", "大小", "类别", "修改时间", "打开", "下载", "分享", "删除"])
                    self.file_tree.setModel(model)
                # 确保信号连接一次
                if not self.user_ui_inited:
                    try:
                        self.file_tree.clicked.disconnect(self.on_public_cell_clicked)
                    except Exception:
                        pass
                    try:
                        self.file_tree.clicked.disconnect(self.on_user_cell_clicked)
                    except Exception:
                        pass
                    self.file_tree.clicked.connect(self.on_user_cell_clicked)
                    self.user_ui_inited = True
            for f in files:
                name = f.get('server_filename') or f.get('file_name') or f.get('name') or ''
                size = f.get('size') or f.get('file_size') or 0
                is_dir = int(f.get('isdir') or 0) == 1
                # 类型：文件夹或由后缀推断
                type_text = self._user_file_type_text(f)
                mtime = f.get('server_mtime') or f.get('mtime') or f.get('update_time') or f.get('ctime') or 0
                # 路径：优先后端给出的path；否则用当前目录+文件名拼接
                path_val = f.get('path') or f.get('server_path') or ''
                if not path_val:
                    try:
                        base = self.current_folder or '/'
                        if not base.endswith('/'):
                            base = base + '/'
                        path_val = base + name
                    except Exception:
                        path_val = '/' + name
                fs_id = f.get('fs_id') or f.get('fsid') or f.get('id')
                try:
                    if isinstance(mtime, (int, float)):
                        mtime_str = datetime.fromtimestamp(float(mtime)).strftime('%Y-%m-%d %H:%M')
                    else:
                        mtime_str = str(mtime)
                except Exception:
                    mtime_str = "-"
                name_item = QStandardItem(str(name))
                name_item.setData({'path': path_val, 'raw': f, 'fsid': fs_id}, Qt.UserRole)
                size_item = QStandardItem("-" if is_dir else self.format_size(float(size)))
                cat_item = QStandardItem(type_text)
                time_item = QStandardItem(mtime_str)
                open_item = QStandardItem("打开")
                download_item = QStandardItem("下载")
                share_item = QStandardItem("分享")
                delete_item = QStandardItem("删除")
                for it in (size_item, cat_item, time_item, open_item, download_item, share_item, delete_item):
                    it.setTextAlignment(Qt.AlignCenter)
                open_item.setForeground(QBrush(QColor("#333333")))
                download_item.setForeground(QBrush(QColor("#2E86AB")))
                share_item.setForeground(QBrush(QColor("#FF9F43")))
                delete_item.setForeground(QBrush(QColor("#E74C3C")))
                model.appendRow([name_item, size_item, cat_item, time_item, open_item, download_item, share_item, delete_item])
            try:
                self.file_tree.setColumnWidth(0, 480)
                self.file_tree.setColumnWidth(1, 100)
                self.file_tree.setColumnWidth(2, 80)
                self.file_tree.setColumnWidth(3, 150)
                self.file_tree.setColumnWidth(4, 60)
                self.file_tree.setColumnWidth(5, 60)
                self.file_tree.setColumnWidth(6, 60)
                self.file_tree.setColumnWidth(7, 60)
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "我的网盘", f"显示失败：{e}")

    def _user_file_type_text(self, file_info) -> str:
        """用户态类型显示：文件夹或根据文件后缀推断类型标签。"""
        try:
            if int(file_info.get('isdir') or 0) == 1:
                return "文件夹"
            name = (file_info.get('server_filename') or file_info.get('file_name') or file_info.get('name') or '').lower()
            from pathlib import Path
            ext = Path(name).suffix.lstrip('.')
            if not ext:
                return "文件"
            image_ext = {"jpg","jpeg","png","gif","bmp","webp","svg"}
            video_ext = {"mp4","mkv","avi","mov","flv","wmv","m4v"}
            audio_ext = {"mp3","wav","flac","aac","ogg","ape","m4a"}
            doc_pdf = {"pdf"}
            doc_word = {"doc","docx"}
            doc_excel = {"xls","xlsx","csv"}
            doc_ppt = {"ppt","pptx"}
            doc_text = {"txt","md","rtf","json","xml","html","htm"}
            archive_ext = {"zip","rar","7z","tar","gz","bz2","iso"}
            code_ext = {"py","js","ts","java","go","c","cpp","cs","php","rb","rs"}
            if ext in image_ext:
                return "图片"
            if ext in video_ext:
                return "视频"
            if ext in audio_ext:
                return "音频"
            if ext in doc_pdf:
                return "PDF"
            if ext in doc_word:
                return "Word"
            if ext in doc_excel:
                return "Excel"
            if ext in doc_ppt:
                return "PPT"
            if ext in doc_text:
                return "文本"
            if ext in archive_ext:
                return "压缩包"
            if ext in code_ext:
                return "代码"
            return ext.upper()
        except Exception:
            return "文件"

    def on_user_cell_clicked(self, index):
        """处理用户态表格的单元格点击（打开/下载/分享/删除）"""
        try:
            # 进入用户态事件处理上下文，防止标志位不同步
            self.in_public = False
            # 态校验：必须在用户态
            if not self._ensure_mode(False, "网盘操作"):
                return
            if not index.isValid():
                return
            row = index.row()
            col = index.column()
            model = self.file_tree.model()
            name_item = model.item(row, 0)
            payload = name_item.data(Qt.UserRole) if name_item else {}
            file_raw = (payload or {}).get('raw') or {}
            # 若 file_raw 缺失 fsid，则尝试从 payload.fsid 或公共列推断
            if not file_raw.get('fs_id') and not file_raw.get('fsid'):
                try:
                    fsid_guess = payload.get('fsid')
                    if fsid_guess:
                        file_raw['fsid'] = fsid_guess
                except Exception:
                    pass
            is_dir = int(file_raw.get('isdir') or 0) == 1
            path_val = payload.get('path') or '/'
            # 打开
            if col == 4:
                if is_dir:
                    self.current_folder = path_val
                    self.load_files()
                else:
                    self.open_file_preview(file_raw)
                return
            # 下载
            if col == 5:
                self.download_user_file(file_raw)
                return
            # 分享
            if col == 6:
                self.share_user_file(file_raw)
                return
            # 删除
            if col == 7:
                self.delete_user_item(file_raw, row)
                return
        except Exception as e:
            QMessageBox.warning(self, "我的网盘", f"操作失败：{e}")

    def open_file_preview(self, file_info: dict):
        """用户态：临时下载后用系统默认程序打开（小文件适用）。"""
        try:
            if int(file_info.get('isdir') or 0) == 1:
                return
            # 改为后端签票 + 代理下载再打开
            import tempfile, os
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            filename = file_info.get('server_filename') or file_info.get('file_name') or 'preview.bin'
            tmp_path = os.path.join(tempfile.gettempdir(), filename)
            fsid = file_info.get('fs_id') or file_info.get('fsid')
            path_val = file_info.get('path') or file_info.get('server_path')
            # 调试输出
            try:
                print(f"[DEBUG][USER][OPEN] fsid={fsid}, path={path_val}")
            except Exception:
                pass
            self._proxy_download_to_path(fsid=fsid, path=path_val, save_path=tmp_path, ttl=300)
            QDesktopServices.openUrl(QUrl.fromLocalFile(tmp_path))
        except Exception as e:
            QMessageBox.warning(self, "打开", f"打开失败：{e}")

    def download_user_file(self, file_info: dict):
        """用户态：下载到本地目录（简化为直链直接下载）。"""
        try:
            if int(file_info.get('isdir') or 0) == 1:
                QMessageBox.information(self, "下载", "文件夹下载请在右键菜单中使用打包下载（待实现）。")
                return
            from PySide6.QtWidgets import QFileDialog
            save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录")
            if not save_dir:
                return
            import os
            filename = file_info.get('server_filename') or file_info.get('file_name') or 'download.bin'
            save_path = os.path.join(save_dir, filename)
            fsid = file_info.get('fs_id') or file_info.get('fsid')
            path_val = file_info.get('path') or file_info.get('server_path')
            try:
                print(f"[DEBUG][USER][DL] fsid={fsid}, path={path_val}, save={save_path}")
            except Exception:
                pass
            self._proxy_download_to_path(fsid=fsid, path=path_val, save_path=save_path, ttl=600)
            QMessageBox.information(self, "下载", f"已保存到：{save_path}")
        except Exception as e:
            QMessageBox.warning(self, "下载", f"下载失败：{e}")

    def _resolve_user_dlink(self, file_info: dict, expires_hint: int = 300) -> str:
        """多策略获取用户态直链，返回可下载URL或抛出包含详细信息的异常。"""
        try:
            # 预处理标识
            fsid = file_info.get('fs_id') or file_info.get('fsid') or file_info.get('id')
            name = file_info.get('server_filename') or file_info.get('file_name') or file_info.get('name') or ''
            path_val = file_info.get('path') or file_info.get('server_path') or ''
            if not path_val and name:
                base = self.current_folder or '/'
                if not base.endswith('/'):
                    base += '/'
                path_val = base + name
            # 尝试1：fsid 优先
            if fsid:
                resp = self.api_client.user_download_link(fsid=str(fsid), expires_hint=expires_hint)
                if isinstance(resp, dict):
                    data = resp.get('data') or {}
                    dlink = data.get('dlink') or resp.get('dlink')
                    if dlink:
                        return dlink
                    # 记录错误信息
                    err = (data.get('errmsg') or data.get('error') or resp.get('error'))
                    if err:
                        print(f"[DEBUG] fsid直链失败: {err}")
            # 尝试2：path
            if path_val:
                resp2 = self.api_client.user_download_link(path=path_val, expires_hint=expires_hint)
                if isinstance(resp2, dict):
                    data2 = resp2.get('data') or {}
                    dlink2 = data2.get('dlink') or resp2.get('dlink')
                    if dlink2:
                        return dlink2
                    err2 = (data2.get('errmsg') or data2.get('error') or resp2.get('error'))
                    if err2:
                        print(f"[DEBUG] path直链失败: {err2}")
            # 尝试3：批量接口
            if fsid:
                resp3 = self.api_client.user_download_links([fsid])
                if isinstance(resp3, dict):
                    data3 = resp3.get('data') or {}
                    items = data3.get('list') or data3.get('items') or []
                    if items:
                        d = items[0]
                        dlink3 = d.get('dlink') or d.get('url')
                        if dlink3:
                            return dlink3
                    err3 = (data3.get('errmsg') or resp3.get('error'))
                    if err3:
                        print(f"[DEBUG] 批量直链失败: {err3}")
            raise RuntimeError('获取直链失败')
        except Exception as e:
            raise

    def _proxy_download_to_path(self, fsid=None, save_path: str = None, ttl: int = 300, path: str = None):
        """通过后端签票 + 代理下载到本地；统一处理403、31045与用户百度token缺失提示。
        支持断点续传：若已存在同名文件，则从其大小处继续下载。
        """
        import requests
        # 先签票
        def sign_ticket() -> str:
            if not (fsid or path):
                raise RuntimeError('缺少fsid/path')
            tk = self.api_client.user_download_ticket(fsid=fsid if fsid else None, path=path if path else None, ttl=ttl)
            if not isinstance(tk, dict):
                raise RuntimeError('签票响应异常')
            if str(tk.get('status')).lower() != 'ok':
                data = tk.get('data') or {}
                err = tk.get('error') or data.get('error') or data.get('errmsg') or ''
                # 后端约定：未授权或用户token缺失
                if err in ('user_baidu_token_missing', 'user_not_authorized'):
                    raise RuntimeError('需要扫码授权，请在“用户信息”中重新授权后重试')
                # 透传百度errno
                be = data.get('baidu_errno') or data.get('errno')
                if be is not None:
                    raise RuntimeError(f"百度错误 errno={be}")
                raise RuntimeError(err or '签票失败')
            # 兼容 ticket 位置
            ticket = tk.get('ticket') or (tk.get('data') or {}).get('ticket') or ((tk.get('data') or {}).get('data') or {}).get('ticket')
            if not ticket:
                try:
                    print(f"[DEBUG][USER][TICKET] empty ticket, raw={tk}")
                except Exception:
                    pass
                raise RuntimeError('票据为空')
            return ticket
        def do_download(ticket: str):
            base = self.api_client.base_url.rstrip('/')
            url = f"{base}/files/proxy_download?ticket={ticket}"
            headers = {"Authorization": f"Bearer {self.api_client.user_jwt}"}
            # 断点支持：若文件已部分存在，从已有大小续传
            resume_from = 0
            try:
                import os
                if os.path.exists(save_path):
                    resume_from = os.path.getsize(save_path)
            except Exception:
                resume_from = 0
            if resume_from > 0:
                headers['Range'] = f'bytes={resume_from}-'
            r = requests.get(url, stream=True, timeout=60, headers=headers, proxies={"http": None, "https": None}, allow_redirects=True)
            if r.status_code == 403:
                # 尝试读取JSON体，检查errno 31045
                errno = None
                try:
                    body = r.json()
                    data_b = body.get('data') or {}
                    errno = data_b.get('errno') or body.get('errno')
                    msg = body.get('error') or body.get('message') or data_b.get('errmsg') or ''
                except Exception:
                    msg = r.text[:200]
                if errno == 31045:
                    raise RuntimeError('403(31045)')
                raise RuntimeError(msg or '403 Forbidden')
            # 非2xx（且非403）也尽量解析JSON错误体
            if r.status_code not in (200, 206):
                try:
                    body = r.json()
                    data_b = body.get('data') or {}
                    msg = body.get('error') or body.get('message') or data_b.get('errmsg') or ''
                except Exception:
                    msg = r.text[:200]
                raise RuntimeError(f"HTTP {r.status_code}: {msg}")
            mode = 'ab' if resume_from > 0 else 'wb'
            with open(save_path, mode) as f:
                for chunk in r.iter_content(chunk_size=256*1024):
                    if chunk:
                        f.write(chunk)
        # 流程：签票→下载；若下载报403(31045)或401/403，尝试刷新JWT后重签一次
        try:
            t1 = sign_ticket()
            do_download(t1)
        except Exception as e:
            msg = str(e)
            if '403' in msg or '401' in msg:
                # 刷新JWT后重试一次（后端应使用用户token兜底，无服务态）
                if self.api_client.refresh_token():
                    t2 = sign_ticket()
                    do_download(t2)
                    return
            # 其余错误直接抛出
            raise

    def share_user_file(self, file_info: dict):
        """用户态：分享（占位，展示未实现或跳转公共分享逻辑）。"""
        try:
            QMessageBox.information(self, "分享", "用户态分享接口暂未开放，后续接入后端API后启用。")
        except Exception as e:
            QMessageBox.warning(self, "分享", f"分享失败：{e}")

    def delete_user_item(self, file_info: dict, row: int = None):
        """用户态：删除文件/目录（基于fs_id）。删除后轮询后端，直至条目消失或超时。"""
        try:
            fsid = file_info.get('fs_id') or file_info.get('fsid')
            if not fsid:
                raise RuntimeError('缺少fs_id')
            ret = self.api_client.delete_file(str(fsid))
            if isinstance(ret, dict) and (ret.get('status') in ('ok','success')):
                # UI先行移除该行，随后轻量刷新
                try:
                    if row is not None:
                        mdl = self.file_tree.model()
                        if mdl:
                            mdl.removeRow(row)
                except Exception:
                    pass
                # 启动轮询确认（最多约10秒）
                start_ts = time.time()
                target_id = str(fsid)
                disappeared = False
                while time.time() - start_ts < 10:
                    try:
                        lst = self.api_client.list_files(self.current_folder, limit=200)
                        items = []
                        if isinstance(lst, dict):
                            data = lst.get('data') or lst
                            items = data.get('list') or data.get('files') or data.get('items') or []
                        elif isinstance(lst, list):
                            items = lst
                        present = False
                        for it in items:
                            cur = str(it.get('fs_id') or it.get('fsid') or '')
                            if cur and cur == target_id:
                                present = True
                                break
                        if not present:
                            disappeared = True
                            break
                        QApplication.processEvents()
                        time.sleep(0.4)
                    except Exception:
                        break
                # 最终刷新一次
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self.load_files)
                QMessageBox.information(self, "删除", "已删除" if disappeared else "已提交删除（后台处理可能稍有延迟）")
            else:
                err = ''
                try:
                    err = (ret or {}).get('error') or ((ret or {}).get('data') or {}).get('errmsg') or ''
                except Exception:
                    pass
                raise RuntimeError(err or '删除失败')
        except Exception as e:
            QMessageBox.warning(self, "删除", f"删除失败：{e}")
    
    def load_demo_files(self):
        """加载演示文件数据"""
        try:
            # 创建一个新的标准项模型，并设置列标题
            self.model = QStandardItemModel()
            self.model.setHorizontalHeaderLabels(['文件名称', '文件大小', '文件类型', '上传时间', '下载', '分享', '举报'])
            self.file_tree.setModel(self.model)
            
            # 设置列宽
            header = self.file_tree.header()
            header.resizeSection(0, 550)  # 文件名列
            header.resizeSection(1, 100)  # 文件大小列
            header.resizeSection(2, 80)   # 文件类型列
            header.resizeSection(3, 130)  # 上传时间列
            header.resizeSection(4, 60)   # 下载列
            header.resizeSection(5, 60)   # 分享列
            header.resizeSection(6, 60)   # 举报列
            
            # 添加演示数据
            demo_files = [
                {"server_filename": "示例文档1.pdf", "category": 4, "size": 1024*1024, "fs_id": "12345"},
                {"server_filename": "示例图片1.jpg", "category": 3, "size": 512*1024, "fs_id": "23456"},
                {"server_filename": "示例视频1.mp4", "category": 1, "size": 10*1024*1024, "fs_id": "34567"},
                {"server_filename": "示例音频1.mp3", "category": 2, "size": 5*1024*1024, "fs_id": "45678"},
                {"server_filename": "示例文档2.docx", "category": 4, "size": 2*1024*1024, "fs_id": "56789"},
            ]
            
            self.display_files(demo_files)
            self.status_label.setText("演示模式 - 点击用户信息进行登录")
            
        except Exception as e:
            QMessageBox.warning(self, "加载失败", f"演示加载失败: {str(e)}")

    def generate_machine_code(self):
        """生成机器码（演示用）"""
        return "DEMO-MACHINE-CODE-12345"

    def initUI(self):
        """初始化界面"""
        self.setWindowTitle('云栈-您身边的共享资料库 V1.0.1')
        self.resize(1200, 800)
        self.setFixedSize(1200, 800)
        
        # 设置窗口标志，移除拖动手柄
        self.setWindowFlags(Qt.Window | Qt.MSWindowsFixedSizeDialogHint)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1: 0, y1: 0,
                    x2: 1, y2: 1,
                    stop: 0 #F5F7FA,
                    stop: 1 #E4E9F2
                );
            }
        """)
        
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建左侧导航栏
        nav_bar = QFrame()  # 创建一个框架组件作为导航栏容器
        nav_bar.setObjectName("navBar")  # 设置对象名称，用于CSS样式选择器
        nav_bar.setStyleSheet("""
            QFrame#navBar {  # 使用ID选择器指定样式
                background: #2C3E50;
                border-right: 1px solid #34495E;
            }
        """)
        nav_bar.setFixedWidth(80)  # 调整宽度以适应垂直图标
        nav_layout = QVBoxLayout(nav_bar)  # 创建垂直布局
        nav_layout.setContentsMargins(15, 25, 15, 25)  # 设置布局的内边距（左、上、右、下）
        nav_layout.setSpacing(10)  # 设置垂直布局中各个控件之间的间距为10像素
        
        # 添加Logo
        logo_frame = QFrame()  # 创建一个框架组件作为Logo容器
        logo_layout = QVBoxLayout(logo_frame)  # 创建垂直布局
        logo_layout.setContentsMargins(0, 0, 0, 20)  # 设置Logo区域的内边距（左、上、右、下）
        
        logo_icon = QLabel()
        logo_icon.setPixmap(QIcon(get_icon_path('logo.png')).pixmap(32,32))
        logo_text = QLabel("云栈")
        logo_text.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        logo_text.setStyleSheet("color: #1976D2;")
        
        logo_layout.addWidget(logo_icon, alignment=Qt.AlignCenter)  # 将Logo图标添加到Logo区域  
        logo_layout.addWidget(logo_text, alignment=Qt.AlignCenter)  # 将Logo文本添加到Logo区域
        nav_layout.addWidget(logo_frame)  # 将Logo容器添加到导航栏布局
        
        # 添加导航按钮
        nav_buttons = [
            ("首页", self.go_home, "home.png"),
            ("公共资源", self.open_public_resources, "public.png"),
            ("上传文档", self.upload_file, "upload.png"),
            ("我的信息", self.show_my_info, "user.png"),
            ("智能问答", self.open_deepseek_dialog, "deepseek.png")  # 添加DeepSeek按钮
        ]
        
        for text, slot, icon in nav_buttons:
            btn = MaterialButton("", icon, self)  # 仅显示图标
            btn.setFixedSize(50, 50)  # 调整按钮大小
            btn.clicked.connect(slot)  # 将按钮的点击事件连接到相应的槽函数
            btn.setToolTip(text)  # 添加工具提示，显示按钮功能
            nav_layout.addWidget(btn, alignment=Qt.AlignCenter)  # 将按钮添加到导航栏布局
        
        nav_layout.addStretch()  # 添加一个伸缩空间，使按钮靠右对齐
        main_layout.addWidget(nav_bar)  # 将导航栏添加到主布局
        
        # 创建右侧内容区
        content_area = QFrame()  # 创建一个框架组件作为内容区容器
        content_area.setObjectName("contentArea")  # 设置对象名称，用于CSS样式选择器
        content_area.setStyleSheet("""
            QFrame#contentArea {
                background: #FFFFFF;
                border-radius: 12px; 
                margin: 5px;
            }
        """)
        
        # 添加内容区阴影
        shadow = QGraphicsDropShadowEffect(content_area)  # 创建阴影效果
        shadow.setBlurRadius(20)  # 设置阴影的模糊半径为20像素  
        shadow.setColor(QColor(0, 0, 0, 25))  # 设置阴影的颜色和透明度
        shadow.setOffset(0, 2)  # 设置阴影的偏移量（水平和垂直）
        content_area.setGraphicsEffect(shadow)
        
        content_layout = QVBoxLayout(content_area)  # 创建垂直布局
        content_layout.setContentsMargins(5, 5, 5, 5)  # 设置布局的内边距（左、上、右、下）
        content_layout.setSpacing(20)  # 设置垂直布局中各个控件之间的间距为20像素
        
        # 添加搜索栏
        search_frame = QFrame()  # 创建一个框架组件作为搜索栏容器
        search_layout = QHBoxLayout(search_frame)  # 创建水平布局
        search_layout.setContentsMargins(0, 0, 0, 0)  # 设置布局的内边距（左、上、右、下）
        
        self.search_input = MaterialLineEdit("请输入您要搜索的文件编号或名称...")
        self.search_input.returnPressed.connect(self.search_files)  # 添加回车键支持
        
        search_btn = MaterialButton("搜索", "search.png")
        search_btn.setFixedWidth(100)  # 设置搜索按钮的宽度为120像素
        search_btn.clicked.connect(self.search_files)  # 将搜索按钮的点击事件连接到搜索文件的槽函数
        
        search_layout.addWidget(self.search_input)  # 将搜索输入框添加到搜索栏布局
        search_layout.addWidget(search_btn)  # 将搜索按钮添加到搜索栏布局
        content_layout.addWidget(search_frame)  # 将搜索栏容器添加到内容区布局
        
        # 创建文件列表
        self.file_tree = QTreeView()
        # 根据VIP状态设置选择模式
        if self.is_vip:
            self.file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)  # VIP用户可以多选
        else:
            self.file_tree.setSelectionMode(QAbstractItemView.SingleSelection)  # 非VIP用户单选
        
        # 移除序号列
        self.file_tree.setRootIsDecorated(False)  # 不显示根节点的装饰（即不显示展开/折叠图标）
        self.file_tree.setItemsExpandable(False)  # 禁止项目展开
        
        self.file_tree.setEditTriggers(QTreeView.NoEditTriggers)  # 禁用编辑
        self.file_tree.setStyleSheet("""
            QTreeView {
                background: white; 
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 10px;
                outline: none;  /* 移除焦点框 */
                show-decoration-selected: 0;  /* 移除选中项的装饰 */
            }
            QTreeView::item {
                height: 40px;
                border: none;  /* 移除项目边框 */
                border-radius: 4px;
                margin: 2px 0;
            }
            QTreeView::branch {
                background: transparent;  /* 移除树状图分支线 */
                border: none;
            }
            QTreeView::item:hover {
                background: #F5F5F5;
            }
            QTreeView::item:selected {
                background: #E3F2FD;
                color: #1976D2;
            }
            /* 垂直滚动条样式 */
            QScrollBar:vertical {
                border: none;
                background: #F5F5F5;
                width: 10px;
                margin: 40px 0 0 0;  /* 顶部margin设置为表头高度 */
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9E9E9E;
            }
            QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            /* 水平滚动条样式 */
            QScrollBar:horizontal {
                border: none;
                background: #F5F5F5;
                height: 10px;
                margin: 0 10px 0 0;  /* 右侧margin留出垂直滚动条的宽度 */
            }
            QScrollBar::handle:horizontal {
                background: #BDBDBD;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #9E9E9E;
            }
            QScrollBar::add-line:horizontal {
                width: 0px;
            }
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        
        # 修改模型标题，添加分享列
        self.model = QStandardItemModel()   
        self.model.setHorizontalHeaderLabels(['文件名称', '文件大小', '文件类型', '上传时间', '下载', '分享', '举报'])  
        self.file_tree.setModel(self.model)  
        
        # 设置列宽和对齐方式
        header = self.file_tree.header()
        header.setStretchLastSection(False)  # 禁用最后一列自动拉伸
        
        # 设置固定列宽和对齐方式
        header.resizeSection(0, 550)  # 文件名列 - 左对齐（默认）
        header.resizeSection(1, 100)  # 文件大小列
        header.resizeSection(2, 80)  # 文件类型列
        header.resizeSection(3, 130)  # 上传时间列
        header.resizeSection(4, 60)   # 下载列
        header.resizeSection(5, 60)   # 分享列
        header.resizeSection(6, 60)   # 举报列

        # 设置对齐方式
        self.model.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 文件名左对齐
        self.model.horizontalHeaderItem(1).setTextAlignment(Qt.AlignCenter)  # 文件大小居中
        self.model.horizontalHeaderItem(2).setTextAlignment(Qt.AlignCenter)  # 文件类型居中
        self.model.horizontalHeaderItem(3).setTextAlignment(Qt.AlignCenter)  # 上传时间居中
        self.model.horizontalHeaderItem(4).setTextAlignment(Qt.AlignCenter)  # 下载居中
        self.model.horizontalHeaderItem(5).setTextAlignment(Qt.AlignCenter)  # 分享居中
        self.model.horizontalHeaderItem(6).setTextAlignment(Qt.AlignCenter)  # 举报居中
        
        # 防止用户手动调整列宽
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        
        # 设置右键菜单
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)  # 设置右键菜单策略为自定义上下文菜单
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)  # 将自定义上下文菜单请求事件连接到show_context_menu槽函数
        
        # 设置表头样式
        header = self.file_tree.header()  # 获取文件树的表头
        header.setStyleSheet("""
            QHeaderView::section {
                background: white;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #E0E0E0;
                font-family: "Microsoft YaHei";  /* 使用微软雅黑字体 */
                font-size: 12px;                 /* 设置字体大小 */
                font-weight: 500;                /* 调整字重，不要太粗 */
                color: #333333;                  /* 更深的文字颜色 */
                letter-spacing: 0.5px;           /* 增加字间距 */
            }
            QHeaderView::section:hover {
                background: #F5F5F5;          /* 悬停时背景颜色为浅灰色 */
            }
        """)
        
        # 图标网格（用户态主页）
        self.icon_grid = QListWidget()
        self.icon_grid.setViewMode(QListView.IconMode)
        self.icon_grid.setResizeMode(QListView.Adjust)
        self.icon_grid.setMovement(QListView.Static)
        self.icon_grid.setIconSize(QSize(64, 64))
        self.icon_grid.setGridSize(QSize(120, 120))
        self.icon_grid.setSpacing(12)
        self.icon_grid.setUniformItemSizes(True)
        self.icon_grid.setWordWrap(True)
        self.icon_grid.setSelectionMode(QAbstractItemView.SingleSelection)
        self.icon_grid.itemDoubleClicked.connect(self.on_grid_item_double_clicked)
        self.icon_grid.hide()
        # 去掉选中边框与焦点虚线
        self.icon_grid.setStyleSheet(
            """
            QListWidget { border: none; outline: none; }
            QListWidget::item { border: none; }
            QListWidget::item:selected { background: #E3F2FD; border: none; color: #1976D2; }
            /* 垂直滚动条样式（与公共资源一致） */
            QScrollBar:vertical {
                border: none;
                background: #F5F5F5;
                width: 10px;
                margin: 0 0 0 0;
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9E9E9E;
            }
            QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            /* 水平滚动条样式（与公共资源一致） */
            QScrollBar:horizontal {
                border: none;
                background: #F5F5F5;
                height: 10px;
                margin: 0 10px 0 0;
            }
            QScrollBar::handle:horizontal {
                background: #BDBDBD;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover { background: #9E9E9E; }
            QScrollBar::add-line:horizontal { width: 0px; }
            QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
            """
        )

        content_layout.addWidget(self.file_tree)  # 将文件树添加到内容区布局
        content_layout.addWidget(self.icon_grid)  # 用户态图标网格
        
        main_layout.addWidget(content_area)
        
        # 创建状态栏
        self.statusBar = QStatusBar()  # 创建状态栏
        self.statusBar.setStyleSheet("""
            QStatusBar {                              /* 状态栏整体样式 */
                background: white;                   /* 背景色为白色 */
                border-top: 1px solid #E0E0E0;      /* 上边框颜色为灰色 */  
            }
            QStatusBar QLabel {
                color: #424242;                  /* 文本颜色为深灰色 */
                padding: 3px;                     /* 内边距为3px */
            }
        """)
        self.setStatusBar(self.statusBar)  # 将状态栏设置为窗口的状态栏
        
        # 添加状态标签
        self.status_label = QLabel()
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.statusBar.addWidget(self.status_label)
        
        # 添加进度条到状态栏
        self.progress_bar = CircularProgressBar()
        self.progress_bar.setFixedSize(16, 16)  # 调整为更小的尺寸
        self.progress_bar.hide()  # 默认隐藏
        self.statusBar.addPermanentWidget(self.progress_bar)
        
       
    def create_tray_icon(self):
        """创建系统托盘"""
        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #E3F2FD;
                color: #2196F3;
            }
            QMenu::separator {
                height: 1px;
                background: #E0E0E0;
                margin: 5px 0;
            }
        """)
        
        show_action = tray_menu.addAction("显示界面")
        show_action.triggered.connect(self.show)
        
        tray_menu.addSeparator()
        
        # 添加版本检测
        check_version_action = tray_menu.addAction("检查更新")
        check_version_action.triggered.connect(self._check_version_from_tray)  # 直接连接，不用 lambda
        
        # 添加关于信息
        about_action = tray_menu.addAction("关于")
        about_action.triggered.connect(self.show_about)
        
        tray_menu.addSeparator()
        
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
        self.tray_icon.setToolTip('云栈')

    def _check_version_from_tray(self):
        """从系统托盘触发的版本检查"""
        from core.update_manager import get_global_update_manager
        update_manager = get_global_update_manager()
        if update_manager:
            update_manager.manual_check()
        else:
            QMessageBox.warning(self, '检查更新', '更新检测器未初始化')

    def closeEvent(self, event):
        """重写关闭事件"""
        # 优雅停止活动的上传线程
        try:
            for w in list(getattr(self, 'active_upload_workers', []) or []):
                try:
                    if w.isRunning():
                        w.stop()
                        w.wait(2000)
                except Exception:
                    pass
        except Exception:
            pass
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "云栈",
            "程序已最小化到系统托盘\n双击托盘图标可以重新打开",
            QSystemTrayIcon.Information,
            2000
        )

    def tray_icon_activated(self, reason):
        """处理托盘图标事件"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isHidden():
                self.show()
                self.activateWindow()
            else:
                self.hide()

    def quit_application(self):
        """退出应用"""
        dialog = ExitConfirmDialog(self)
        if dialog.exec() == QDialog.Accepted:
            try:
                # 隐藏托盘图标并退出应用
                self.tray_icon.hide()
                QApplication.quit()
            except Exception as e:
                # 记录错误后继续退出
                print(f"退出时出错: {e}")
                self.tray_icon.hide()
                QApplication.quit()

    def go_home(self):
        """返回主页"""
        # 切回用户态并加载网盘根目录（表格视图，与公共态一致排版）
        self.in_public = False
        try:
            self.file_tree.show()
            self.icon_grid.hide()
        except Exception:
            pass
        self.current_folder = '/'
        self.status_label.setText("用户态：正在进入根目录 /")
        self.load_files()

    def populate_icon_grid(self, files):
        """将文件列表填充到图标网格"""
        try:
            self.icon_grid.clear()
            provider = QFileIconProvider()
            for it in files:
                name = it.get('server_filename') or it.get('file_name') or it.get('name') or ''
                isdir = int(it.get('isdir') or 0)
                # 使用系统文件图标：目录/文件
                if isdir == 1:
                    icon = provider.icon(QFileIconProvider.Folder)
                else:
                    # 通过文件名后缀推断系统图标
                    fi = QFileInfo(name)
                    icon = provider.icon(fi)
                item = QListWidgetItem(icon, name)
                item.setData(Qt.UserRole, it)
                item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
                self.icon_grid.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "主页", f"填充失败：{e}")

    def on_grid_item_double_clicked(self, item):
        """双击图标：目录进入下一级，文件预留后续操作"""
        try:
            payload = item.data(Qt.UserRole) or {}
            isdir = int(payload.get('isdir') or 0)
            path = payload.get('path') or '/'
            if isdir == 1:
                self.current_folder = path
                self.load_files()
            else:
                QMessageBox.information(self, "文件", f"文件：{payload.get('server_filename') or payload.get('name')}")
        except Exception as e:
            QMessageBox.warning(self, "打开", f"失败：{e}")
    
    def upload_file(self):
        """上传文件对话框"""
        try:
            if not self.api_client.is_logged_in():
                reply = QMessageBox.question(
                    self, 
                    "需要登录", 
                    "上传文件需要先登录，是否现在登录？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.show_my_info()
                return
            # 选择上传通道：公共资源 / 我的网盘（自定义对话框：中文按钮）
            def _choose_scope():
                dlg = QDialog(self)
                dlg.setWindowTitle("选择上传通道")
                dlg.setFixedSize(320, 140)
                lay = QVBoxLayout(dlg)
                tip = QLabel("请选择上传通道：")
                lay.addWidget(tip)
                from PySide6.QtWidgets import QComboBox
                cmb = QComboBox(dlg)
                cmb.addItems(["公共资源", "我的网盘"])
                lay.addWidget(cmb)
                btns = QHBoxLayout()
                ok_btn = QPushButton("确定")
                cancel_btn = QPushButton("取消")
                btns.addStretch(1)
                btns.addWidget(ok_btn)
                btns.addWidget(cancel_btn)
                lay.addLayout(btns)
                ok_btn.clicked.connect(dlg.accept)
                cancel_btn.clicked.connect(dlg.reject)
                if dlg.exec() == QDialog.Accepted:
                    return cmb.currentText()
                return None
            scope = _choose_scope()
            if not scope:
                return
            is_public = (scope == "公共资源")

            # 仅支持：本地文件上传
            # 支持批量选择
            paths, _ = QFileDialog.getOpenFileNames(self, "选择要上传的文件(可多选)", "", "所有文件 (*)")
            if not paths:
                return
            # 过滤不存在
            paths = [p for p in paths if os.path.exists(p)]
            if not paths:
                QMessageBox.warning(self, "上传", "所选文件均不存在")
                return

            # 异步批量上传
            if is_public:
                from ui.threads.upload_thread import UploadWorker
                worker = UploadWorker(self.api_client, paths, is_public=True)
                self.progress_bar.show()
                self.status_label.setText("上传中...")
                def _on_prog(text, done, total):
                    self.status_label.setText(f"{text} ({done}/{total})")
                def _on_finished(okc, failc, skipc):
                    self.progress_bar.hide()
                    QMessageBox.information(self, "上传", f"成功 {okc} 个，失败 {failc} 个，已存在跳过 {skipc} 个")
                    if okc and not self.in_public:
                        self.load_files()
                worker.progress.connect(_on_prog)
                def _finish_and_cleanup(okc, failc, skipc):
                    try:
                        _on_finished(okc, failc, skipc)
                    finally:
                        try:
                            self.active_upload_workers.remove(worker)
                        except Exception:
                            pass
                        worker.deleteLater()
                worker.finished.connect(_finish_and_cleanup)
                self.active_upload_workers.append(worker)
                worker.start()
            else:
                # 我的网盘：从根目录开始加载目录，供用户选择
                def _choose_user_dir(start_dir: str = "/"):
                    dlg = QDialog(self)
                    dlg.setWindowTitle("选择保存目录（我的网盘）")
                    dlg.setFixedSize(480, 520)
                    lay = QVBoxLayout(dlg)
                    path_label = QLabel(start_dir)
                    path_label.setStyleSheet("font-weight:bold;color:#1976D2;")
                    lay.addWidget(path_label)
                    lst = QListWidget()
                    lay.addWidget(lst)
                    btns = QHBoxLayout()
                    btn_up = QPushButton("上级")
                    btn_ok = QPushButton("选择此目录")
                    btn_cancel = QPushButton("取消")
                    btns.addWidget(btn_up)
                    btns.addStretch(1)
                    btns.addWidget(btn_ok)
                    btns.addWidget(btn_cancel)
                    lay.addLayout(btns)

                    current_dir = {"path": start_dir}

                    def _load(dir_path: str):
                        path_label.setText(dir_path)
                        lst.clear()
                        # 加载该目录下的子目录
                        result = self.api_client.list_files(dir_path, 1000)
                        items = []
                        if isinstance(result, dict):
                            data = result.get("data") if isinstance(result.get("data"), dict) else result
                            files = (data or {}).get("list") or (data or {}).get("files") or []
                            items = [it for it in files if int(it.get('isdir') or 0) == 1]
                        for it in items:
                            name = it.get('server_filename') or it.get('file_name') or it.get('name') or ''
                            item = QListWidgetItem(f"[目录] {name}")
                            item.setData(Qt.UserRole, it)
                            lst.addItem(item)

                    def _enter():
                        it = lst.currentItem()
                        if not it:
                            return
                        payload = it.data(Qt.UserRole) or {}
                        next_path = payload.get('path') or (current_dir['path'].rstrip('/') + '/' + (payload.get('server_filename') or ''))
                        current_dir['path'] = next_path
                        _load(current_dir['path'])

                    def _up():
                        p = current_dir['path']
                        if p == '/' or not p:
                            return
                        parent = p.rstrip('/')
                        parent = parent[:parent.rfind('/')] or '/'
                        current_dir['path'] = parent
                        _load(current_dir['path'])

                    lst.itemDoubleClicked.connect(lambda _: _enter())
                    btn_up.clicked.connect(_up)
                    btn_ok.clicked.connect(dlg.accept)
                    btn_cancel.clicked.connect(dlg.reject)

                    _load(current_dir['path'])
                    if dlg.exec() == QDialog.Accepted:
                        return current_dir['path'] or '/'
                    return None

                dir_path = _choose_user_dir("/")
                if not dir_path:
                    return
                from ui.threads.upload_thread import UploadWorker
                worker = UploadWorker(self.api_client, paths, is_public=False, user_dir=dir_path)
                self.progress_bar.show()
                self.status_label.setText("上传中...")
                def _on_prog(text, done, total):
                    self.status_label.setText(f"{text} ({done}/{total})")
                def _on_finished(okc, failc, skipc):
                    self.progress_bar.hide()
                    QMessageBox.information(self, "上传", f"成功 {okc} 个，失败 {failc} 个，已存在跳过 {skipc} 个")
                    if okc and not self.in_public:
                        self.load_files()
                worker.progress.connect(_on_prog)
                def _finish_and_cleanup2(okc, failc, skipc):
                    try:
                        _on_finished(okc, failc, skipc)
                    finally:
                        try:
                            self.active_upload_workers.remove(worker)
                        except Exception:
                            pass
                        worker.deleteLater()
                worker.finished.connect(_finish_and_cleanup2)
                self.active_upload_workers.append(worker)
                worker.start()
        except Exception as e:
            QMessageBox.warning(self, "上传", f"失败：{e}")
    
    def open_public_resources(self):
        """打开公共资源页（在主内容区加载）"""
        # 进入公共资源模式
        self.in_public = True
        self.public_page = 1
        self.public_has_more = True
        self.public_loading = False
        self.status_label.setText("公共资源：加载中...")
        # 视图切换：显示树表，隐藏图标网格
        try:
            self.file_tree.show()
            self.icon_grid.hide()
        except Exception:
            pass
        # 清空并加载第一页
        try:
            self.display_public_files([], append=False)
        except Exception:
            pass
        self.load_public_resources(load_more=False)
        self.refresh_public_stats()

    def refresh_public_stats(self):
        """拉取文件数据库统计并显示到状态栏"""
        try:
            stats = self.api_client.files_stats() or {}
            total = stats.get('total_files') or stats.get('total_count') or stats.get('total') or ''
            total_size = stats.get('total_size') or ''
            # 类别统计取前两项
            categories = stats.get('categories') or stats.get('by_category') or []
            cat_str = ''
            try:
                if isinstance(categories, dict):
                    items = list(categories.items())[:2]
                    cat_str = ' | '.join([f"类别{k}:{v}" for k, v in items])
                elif isinstance(categories, list):
                    # 期望 [{"category":4, "count":165334}, ...]
                    items = categories[:2]
                    cat_str = ' | '.join([f"类别{(it.get('category') or it.get('id') or '?')}:{(it.get('count') or it.get('value') or 0)}" for it in items])
            except Exception:
                pass
            size_text = ''
            try:
                size_val = float(total_size)
                size_text = f"，总大小 {self.format_size(size_val)}"
            except Exception:
                if total_size:
                    size_text = f"，总大小 {total_size}"
            base = f"公共资源：共 {total} 个文件{size_text}"
            if cat_str:
                base += f" | {cat_str}"
            self.status_label.setText(base)
        except Exception as e:
            # 失败不打断主流程
            pass

    def load_public_resources(self, keyword: str = None, load_more: bool = False):
        """加载公共资源文件列表（滚动加载）"""
        if self.public_loading:
            return
        self.public_loading = True
        try:
            # 处理搜索模式与页码
            if keyword is not None:
                self.public_search_mode = True
                self.public_search_keyword = keyword
            page = self.public_page if load_more else 1
            files = []
            result = None
            if self.public_search_mode and self.public_search_keyword:
                # 使用 /files/list + file_path 以支持分页
                result = self.api_client.files_list(
                    page=page,
                    page_size=self.public_page_size,
                    file_path=self.public_search_keyword
                )
            else:
                result = self.api_client.files_list(page=page, page_size=self.public_page_size)
            if isinstance(result, dict):
                files = result.get('files') or (result.get('data') or {}).get('files') or (result.get('data') or {}).get('items') or []
                has_next = result.get('has_next')
                if has_next is None:
                    has_next = len(files) >= self.public_page_size
                self.public_has_more = bool(has_next)
                total = result.get('total') or ''
            else:
                files = result or []
                self.public_has_more = len(files) >= self.public_page_size
                total = ''
            # 显示
            self.display_public_files(files, append=load_more)
            # 翻页
            if self.public_has_more:
                self.public_page = page + 1
            # 状态栏
            if self.public_search_mode and self.public_search_keyword:
                total_text = f"共 {total} 条" if total != '' else ""
                page_text = f"当前第 {page} 页"
                if total_text:
                    self.status_label.setText(f"公共资源-搜索 '{self.public_search_keyword}'：{total_text}，{page_text}")
                else:
                    self.status_label.setText(f"公共资源-搜索 '{self.public_search_keyword}'：{page_text}")
            else:
                self.refresh_public_stats()
        except Exception as e:
            self.status_label.setText(f"公共资源加载失败：{e}")
        finally:
            self.public_loading = False

    def display_public_files(self, files, append: bool = False):
        """在主列表控件内显示公共资源列表，支持追加"""
        from PySide6.QtGui import QStandardItem
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QHeaderView
        from PySide6.QtGui import QColor, QBrush
        try:
            if not append:
                model = QStandardItemModel()
                model.setHorizontalHeaderLabels(["文件名称", "大小", "类别", "创建时间", "阅读", "下载", "分享", "举报"])
                self.file_tree.setModel(model)
                # 表头对齐
                try:
                    from PySide6.QtCore import Qt
                    model.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    for col in range(1, 8):
                        item = model.horizontalHeaderItem(col)
                        if item:
                            item.setTextAlignment(Qt.AlignCenter)
                except Exception:
                    pass
                # 初始化一次交互（避免重复连接导致需点两次）
                if not self.public_ui_inited:
                    self.file_tree.clicked.connect(self.on_public_cell_clicked)
                    self.file_tree.setMouseTracking(True)
                    self.file_tree.viewport().installEventFilter(self)
                    self.file_tree.setItemDelegateForColumn(4, ActionCellDelegate(self.file_tree, text_color="#333333"))
                    self.file_tree.setItemDelegateForColumn(5, ActionCellDelegate(self.file_tree, text_color="#2E86AB"))
                    self.file_tree.setItemDelegateForColumn(6, ActionCellDelegate(self.file_tree, text_color="#FF9F43"))
                    self.file_tree.setItemDelegateForColumn(7, ActionCellDelegate(self.file_tree, text_color="#E74C3C"))
                    self.public_ui_inited = True
            else:
                model = self.file_tree.model()
                if model is None:
                    model = QStandardItemModel()
                    model.setHorizontalHeaderLabels(["文件名称", "大小", "类别", "创建时间", "阅读", "下载", "分享", "举报"])
                    self.file_tree.setModel(model)
                    try:
                        from PySide6.QtCore import Qt
                        model.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        for col in range(1, 8):
                            item = model.horizontalHeaderItem(col)
                            if item:
                                item.setTextAlignment(Qt.AlignCenter)
                    except Exception:
                        pass
                    if not self.public_ui_inited:
                        self.file_tree.setMouseTracking(True)
                        self.file_tree.viewport().installEventFilter(self)
                        self.file_tree.setItemDelegateForColumn(4, ActionCellDelegate(self.file_tree, text_color="#333333"))
                        self.file_tree.setItemDelegateForColumn(5, ActionCellDelegate(self.file_tree, text_color="#2E86AB"))
                        self.file_tree.setItemDelegateForColumn(6, ActionCellDelegate(self.file_tree, text_color="#FF9F43"))
                        self.file_tree.setItemDelegateForColumn(7, ActionCellDelegate(self.file_tree, text_color="#E74C3C"))
                        self.file_tree.clicked.connect(self.on_public_cell_clicked)
                        self.public_ui_inited = True
            for f in files:
                name = f.get('file_name') or f.get('server_filename') or f.get('name') or ''
                size = f.get('file_size') or f.get('size') or 0
                category = f.get('category') or f.get('category_id') or f.get('type') or ''
                ctime = f.get('create_time') or f.get('ctime') or 0
                fs_id = f.get('fs_id') or f.get('fsid') or f.get('id')  # 需要fs_id用于分享
                try:
                    if isinstance(ctime, (int, float)):
                        ctime_str = datetime.fromtimestamp(float(ctime)).strftime('%Y-%m-%d %H:%M')
                    else:
                        ctime_str = str(ctime)
                except Exception:
                    ctime_str = "-"
                name_item = QStandardItem(str(name))
                # 将原始数据存到第一列，便于取fs_id
                name_item.setData({'fs_id': fs_id, 'file_name': name}, Qt.UserRole)
                size_item = QStandardItem(self.format_size(float(size)))
                cat_item = QStandardItem(self.map_category_to_type(int(category)) if str(category).isdigit() else str(category))
                ctime_item = QStandardItem(ctime_str)
                read_item = QStandardItem("阅读")
                download_item = QStandardItem("下载")
                share_item = QStandardItem("分享")
                report_item = QStandardItem("举报")
                # 对齐：除文件名称外其它列居中
                for it in (size_item, cat_item, ctime_item, read_item, download_item, share_item, report_item):
                    it.setTextAlignment(Qt.AlignCenter)
                # 设置列文字颜色
                read_item.setForeground(QBrush(QColor("#333333")))     # 深灰
                download_item.setForeground(QBrush(QColor("#2E86AB"))) # 中蓝
                share_item.setForeground(QBrush(QColor("#FF9F43")))    # 浅橙
                report_item.setForeground(QBrush(QColor("#E74C3C")))   # 淡红
                model.appendRow([name_item, size_item, cat_item, ctime_item, read_item, download_item, share_item, report_item])
            # 固定列宽
            try:
                self.file_tree.setColumnWidth(0, 480)
                self.file_tree.setColumnWidth(1, 100)
                self.file_tree.setColumnWidth(2, 80)
                self.file_tree.setColumnWidth(3, 150)
                self.file_tree.setColumnWidth(4, 60)
                self.file_tree.setColumnWidth(5, 60)
                self.file_tree.setColumnWidth(6, 60)
                self.file_tree.setColumnWidth(7, 60)
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "公共资源", f"显示失败：{e}")

    def eventFilter(self, obj, event):
        # 为动作列设置手型光标
        try:
            if obj is self.file_tree.viewport():
                if event.type() == event.MouseMove:
                    idx = self.file_tree.indexAt(event.pos())
                    if idx.isValid() and idx.column() in (4, 5, 6, 7):
                        self.file_tree.viewport().setCursor(Qt.PointingHandCursor)
                    else:
                        self.file_tree.viewport().setCursor(Qt.ArrowCursor)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def on_public_cell_clicked(self, index):
        """处理公共资源表格的单元格点击（分享/下载/阅读/举报）"""
        try:
            # 进入公共态事件处理上下文，防止标志位不同步
            self.in_public = True
            # 态校验：必须在公共态
            if not self._ensure_mode(True, "公共资源操作"):
                return
            if not index.isValid():
                return
            row = index.row()
            col = index.column()
            model = self.file_tree.model()
            name_item = model.item(row, 0)
            payload = name_item.data(Qt.UserRole) if name_item else {}
            fs_id = payload.get('fs_id')
            # 阅读列索引4：下载到临时目录并用系统默认程序打开
            if col == 4:
                # 调试输出当前点击行的关键信息
                try:
                    print(f"[DEBUG][READ] payload={payload}")
                    print(f"[DEBUG][READ] fs_id={fs_id}, path={payload.get('file_path') or payload.get('path')} ")
                except Exception:
                    pass
                if not fs_id and not (payload.get('file_path') or payload.get('path')):
                    QMessageBox.warning(self, "阅读", "无法获取fs_id")
                    return
                import tempfile
                def _get_meta():
                    resp = self.api_client.public_download_links([int(fs_id)])
                    if not isinstance(resp, dict) or resp.get('status') != 'ok':
                        raise RuntimeError((resp.get('data') or {}).get('errmsg') or resp.get('error') or '未知错误')
                    data = resp.get('data') or {}
                    items = data.get('list') or []
                    if not items:
                        raise RuntimeError('未获取到直链元信息')
                    return items[0]
                def _get_ticket():
                    # 优先 fsid，失败或空票据时，若存在 path 则回退用 path 再试一次
                    def _extract_ticket(resp_dict):
                        data1 = resp_dict.get('ticket')
                        data2 = (resp_dict.get('data') or {}).get('ticket')
                        data3 = ((resp_dict.get('data') or {}).get('data') or {}).get('ticket')
                        return data1 or data2 or data3
                    # 尝试 fsid
                    t = self.api_client.public_download_ticket(fsid=fs_id, ttl=300) if fs_id else None
                    if isinstance(t, dict):
                        try:
                            print(f"[DEBUG][READ] sign fsid status={t.get('status')} raw={t}")
                        except Exception:
                            pass
                    if isinstance(t, dict) and str(t.get('status')).lower() == 'ok':
                        tk = _extract_ticket(t)
                        if tk:
                            try:
                                print(f"[DEBUG][READ] ticket(from fsid)={tk[:32]}...")
                            except Exception:
                                pass
                            return tk
                    # 回退 path
                    p = payload.get('file_path') or payload.get('path')
                    if p:
                        t2 = self.api_client.public_download_ticket(path=p, ttl=300)
                        if isinstance(t2, dict):
                            try:
                                print(f"[DEBUG][READ] sign path status={t2.get('status')} raw={t2}")
                            except Exception:
                                pass
                        if isinstance(t2, dict) and str(t2.get('status')).lower() == 'ok':
                            tk2 = _extract_ticket(t2)
                            if tk2:
                                try:
                                    print(f"[DEBUG][READ] ticket(from path)={tk2[:32]}...  path={p}")
                                except Exception:
                                    pass
                                return tk2
                        err2 = (t2.get('data') or {}).get('errmsg') or t2.get('error') if isinstance(t2, dict) else None
                        raise RuntimeError(err2 or '票据获取失败')
                    err = (t.get('data') or {}).get('errmsg') or t.get('error') if isinstance(t, dict) else None
                    raise RuntimeError(err or '票据获取失败')
                try:
                    self.status_label.setText("阅读：准备中...")
                    meta = _get_meta()
                    real_name = meta.get('filename') or meta.get('server_filename') or (payload.get('file_name') or 'preview.bin')
                    # 保存到临时目录
                    tmp_dir = tempfile.gettempdir()
                    base = self.api_client.base_url.rstrip('/')
                    save_path = os.path.join(tmp_dir, real_name)
                    tmp_path = save_path + '.part'
                    size_expect = meta.get('size')
                    ticket = _get_ticket()
                    try:
                        print(f"[DEBUG][READ] final ticket={ticket[:48]}...  jwt_present={bool(app_jwt)}")
                    except Exception:
                        pass
                    app_jwt = getattr(self.api_client, 'user_jwt', None)
                    # 启动下载线程
                    self.progress_bar.show()
                    self.status_label.setText("阅读：下载中...")
                    self.download_worker = ProxyDownloadWorker(
                        base_url=base,
                        ticket=ticket,
                        save_path=save_path,
                        tmp_path=tmp_path,
                        size_expect=size_expect,
                        app_jwt=app_jwt,
                        resume_pos=0,
                        parent=self
                    )
                    def _on_finished(path):
                        self.progress_bar.hide()
                        self.status_label.setText("阅读：打开中...")
                        try:
                            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                            self.status_label.setText("阅读：已打开")
                        except Exception as e:
                            self.status_label.setText(f"阅读失败：{e}")
                            QMessageBox.warning(self, "阅读", f"打开失败：{e}")
                    def _on_failed(err):
                        self.progress_bar.hide()
                        # 限额友好提示
                        msg = str(err)
                        if '429' in msg or 'daily_quota_exceeded' in msg:
                            self.status_label.setText("阅读失败：今日额度已用尽")
                            QMessageBox.information(self, "阅读", "今日总额度已用尽，请明日再试或升级会员。")
                        else:
                            self.status_label.setText("阅读失败")
                            QMessageBox.warning(self, "阅读", f"下载失败：{err}")
                    self.download_worker.finished.connect(_on_finished)
                    self.download_worker.failed.connect(lambda e: _on_failed(e))
                    self.download_worker.start()
                except Exception as e:
                    self.progress_bar.hide()
                    msg = self._friendly_error(str(e), "阅读")
                    self.status_label.setText("阅读失败")
                    QMessageBox.information(self, "阅读", msg)
                return
            # 下载列索引5
            if col == 5:
                # 公共资源：票据+代理下载（服务态）改为异步线程
                try:
                    print(f"[DEBUG][DL] in_public={self.in_public}, payload={payload}")
                except Exception:
                    pass
                if not fs_id and not (payload.get('file_path') or payload.get('path')):
                    QMessageBox.warning(self, "下载", "无法获取fs_id")
                    return
                if self.public_downloading:
                    QMessageBox.information(self, "下载", "当前已有下载进行中，请稍候…")
                    return
                save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录")
                if not save_dir:
                    return
                def _get_meta():
                    resp = self.api_client.public_download_links([int(fs_id)])
                    if not isinstance(resp, dict) or resp.get('status') != 'ok':
                        raise RuntimeError((resp.get('data') or {}).get('errmsg') or resp.get('error') or '未知错误')
                    data = resp.get('data') or {}
                    items = data.get('list') or []
                    if not items:
                        raise RuntimeError('未获取到直链元信息')
                    return items[0]
                def _get_ticket():
                    # 优先 fsid，失败或空票据时，若存在 path 则回退用 path 再试一次
                    def _extract_ticket(resp_dict):
                        data1 = resp_dict.get('ticket')
                        data2 = (resp_dict.get('data') or {}).get('ticket')
                        data3 = ((resp_dict.get('data') or {}).get('data') or {}).get('ticket')
                        return data1 or data2 or data3
                    t = self.api_client.public_download_ticket(fsid=fs_id, ttl=300) if fs_id else None
                    if isinstance(t, dict):
                        try:
                            print(f"[DEBUG][DL] sign fsid status={t.get('status')} raw={t}")
                        except Exception:
                            pass
                    if isinstance(t, dict) and str(t.get('status')).lower() == 'ok':
                        tk = _extract_ticket(t)
                        if tk:
                            return tk
                    p = payload.get('file_path') or payload.get('path')
                    if p:
                        t2 = self.api_client.public_download_ticket(path=p, ttl=300)
                        if isinstance(t2, dict):
                            try:
                                print(f"[DEBUG][DL] sign path status={t2.get('status')} raw={t2}")
                            except Exception:
                                pass
                        if isinstance(t2, dict) and str(t2.get('status')).lower() == 'ok':
                            tk2 = _extract_ticket(t2)
                            if tk2:
                                return tk2
                        err2 = (t2.get('data') or {}).get('errmsg') or t2.get('error') if isinstance(t2, dict) else None
                        raise RuntimeError(err2 or '票据获取失败')
                    err = (t.get('data') or {}).get('errmsg') or t.get('error') if isinstance(t, dict) else None
                    raise RuntimeError(err or '票据获取失败')
                try:
                    self.public_downloading = True
                    meta = _get_meta()
                    real_name = meta.get('filename') or meta.get('server_filename') or (payload.get('file_name') or 'download.bin')
                    size_expect = meta.get('size')
                    ticket = _get_ticket()
                    base = self.api_client.base_url.rstrip('/')
                    save_path = os.path.join(save_dir, real_name)
                    tmp_path = save_path + '.part'
                    resume_pos = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0

                    # 启动下载线程
                    self.status_label.setText("下载中...")
                    self.progress_bar.show()
                    app_jwt = getattr(self.api_client, 'user_jwt', None)
                    self.download_worker = ProxyDownloadWorker(
                        base_url=base,
                        ticket=ticket,
                        save_path=save_path,
                        tmp_path=tmp_path,
                        size_expect=size_expect,
                        app_jwt=app_jwt,
                        resume_pos=resume_pos,
                        parent=self
                    )
                    def _on_progress(p):
                        self.status_label.setText(f"下载中... {p:.1f}%")
                    def _on_status(s):
                        self.status_label.setText(s)
                    def _on_finished(path):
                        self.progress_bar.hide()
                        self.public_downloading = False
                        self.status_label.setText("下载完成")
                        QMessageBox.information(self, "下载", f"已保存到: {path}")
                    def _on_failed(err):
                        # 如果是401/403由线程上报，这里尝试换票一次并重启线程
                        msg = str(err)
                        if any(x in msg for x in ('HTTP 401', 'HTTP 403')):
                            try:
                                new_ticket = _get_ticket()
                                self.download_worker = ProxyDownloadWorker(
                                    base_url=base,
                                    ticket=new_ticket,
                                    save_path=save_path,
                                    tmp_path=tmp_path,
                                    size_expect=size_expect,
                                    app_jwt=app_jwt,
                                    resume_pos=os.path.getsize(tmp_path) if os.path.exists(tmp_path) else resume_pos,
                                    parent=self
                                )
                                self.download_worker.progress.connect(_on_progress)
                                self.download_worker.status.connect(_on_status)
                                self.download_worker.finished.connect(_on_finished)
                                self.download_worker.failed.connect(lambda e: _on_failed(e))
                                self.download_worker.start()
                                return
                            except Exception:
                                pass
                        self.progress_bar.hide()
                        self.public_downloading = False
                        # 限额友好提示
                        if '429' in msg or 'daily_quota_exceeded' in msg:
                            self.status_label.setText("下载失败：今日额度已用尽")
                            QMessageBox.information(self, "下载", "今日总额度已用尽，请明日再试或升级会员。")
                        else:
                            self.status_label.setText("下载失败")
                            QMessageBox.warning(self, "下载", f"下载失败：{err}")

                    self.download_worker.progress.connect(_on_progress)
                    self.download_worker.status.connect(_on_status)
                    self.download_worker.finished.connect(_on_finished)
                    self.download_worker.failed.connect(lambda e: _on_failed(e))
                    self.download_worker.start()
                except Exception as e:
                    self.progress_bar.hide()
                    self.public_downloading = False
                    msg = self._friendly_error(str(e), "下载")
                    self.status_label.setText("下载失败")
                    QMessageBox.information(self, "下载", msg)
                return
            # 分享列索引6（保留原逻辑）
            if col == 6:
                # 默认生成4位密码
                import random, string
                default_pwd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                dlg = ShareDialog(self, default_pwd)
                if dlg.exec() != QDialog.Accepted:
                    return
                period_str, pwd, remark = dlg.get_values()
                try:
                    period = int(period_str)
                except Exception:
                    QMessageBox.warning(self, "分享", "有效期仅支持 1/7/30")
                    return
                if period not in (1, 7, 30):
                    QMessageBox.warning(self, "分享", "有效期仅支持 1/7/30")
                    return
                import re
                if not re.fullmatch(r"[a-z0-9]{4}", pwd or ""):
                    QMessageBox.warning(self, "分享", "提取码需为4位小写字母+数字")
                    return
                if not remark:
                    remark = "感谢您使用云栈分享"
                resp = self.api_client.public_share_create(fsids=[fs_id], period=period, pwd=pwd, remark=remark)
                if isinstance(resp, dict) and resp.get('status') == 'ok':
                    data = ((resp.get('data') or {}).get('data')) or {}
                    link = data.get('link') or data.get('short_url') or ''
                    pwd_out = data.get('pwd') or pwd
                    from datetime import datetime
                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
                    text = f"链接: {link}\n提取码: {pwd_out}\n日期: {now_str}\n备注: {remark}"
                    try:
                        QApplication.clipboard().setText(text)
                        QMessageBox.information(self, "分享成功", text + "\n\n已复制到剪贴板")
                    except Exception:
                        QMessageBox.information(self, "分享成功", text)
                else:
                    err = None
                    if isinstance(resp, dict):
                        err = (resp.get('data') or {}).get('errmsg') or resp.get('error')
                    # 限额友好提示
                    if err and ('daily_quota_exceeded' in str(err)):
                        QMessageBox.information(self, "分享", "今日总额度已用尽，请明日再试或升级会员。")
                    else:
                        QMessageBox.warning(self, "分享失败", err or "未知错误")
                return
            # 举报列索引7
            if col == 7:
                if not fs_id:
                    QMessageBox.warning(self, "举报", "无法获取fs_id 作为 target")
                    return
                # 选择/输入原因（简单输入框，限制长度）
                reason, ok = QInputDialog.getText(self, "举报", "请输入举报原因（简述）:", text="违规/侵权")
                if not ok:
                    return
                reason = (reason or '').strip()
                if len(reason) > 200:
                    reason = reason[:200]
                resp = self.api_client.public_report_submit(str(fs_id), reason)
                if isinstance(resp, dict) and resp.get('status') == 'ok':
                    data = resp.get('data') or {}
                    count = data.get('count')
                    QMessageBox.information(self, "举报", f"举报已提交，当前该目标累计 {count} 次")
                else:
                    err = (resp or {}).get('error') if isinstance(resp, dict) else '未知错误'
                    if err and (('429' in str(err)) or ('report_daily_limit' in str(err))):
                        QMessageBox.information(self, "举报", "今日举报次数已达上限，请明日再试")
                    elif err and ('report_too_frequent' in str(err)):
                        QMessageBox.information(self, "举报", "操作过于频繁，请稍后再试")
                    elif err and ('not_logged_in' in str(err)):
                        QMessageBox.information(self, "举报", "请先登录后再举报")
                    else:
                        QMessageBox.warning(self, "举报", err or "举报失败")
                return
        except Exception as e:
            QMessageBox.warning(self, "操作", f"失败：{e}")
    
    def search_files(self):
        """搜索文件"""
        search_text = self.search_input.text().strip()
        if not search_text:
            return
        
        if self.in_public:
            # 公共资源搜索：清空并分页加载
            self.status_label.setText("公共资源：搜索中...")
            self.public_page = 1
            self.public_has_more = True
            self.public_loading = False
            self.public_search_mode = True
            self.public_search_keyword = search_text
            self.display_public_files([], append=False)
            self.load_public_resources(keyword=search_text, load_more=False)
            self.search_input.setText("")
            return
        
        # 原有私有网盘搜索
        if not self.api_client.is_logged_in():
            reply = QMessageBox.question(
                self, 
                "需要登录", 
                "搜索文件需要先登录，是否现在登录？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.show_my_info()
            return
        
        self.is_loading = True
        self.status_label.setText("正在搜索...")
        
        # 调用搜索API
        result = self.api_client.search_filename(search_text, self.current_folder)
        if result and result.get("status") == "ok":
            data = result.get("data", {})
            files = data.get("list", [])
            self.display_files(files)
            self.status_label.setText(f"找到 {len(files)} 个匹配文件")
        else:
            error_msg = result.get("error", "搜索失败") if result else "网络连接失败"
            self.status_label.setText(f"搜索失败: {error_msg}")
            QMessageBox.critical(self, "错误", f"搜索失败: {error_msg}")
        
        self.is_loading = False
        self.search_input.setText("")
    
    def show_my_info(self):
        """显示用户信息对话框"""
        if self.api_client.is_logged_in():
            # 已登录，直接展示用户信息UI
            from ui.dialogs.user_info_dialog import UserInfoDialog
            dialog = UserInfoDialog(self, api_client=self.api_client)
            # 优先使用持久化的 user_info
            ui_data = getattr(self.api_client, 'user_info', None)
            if not ui_data:
                # 如果没有缓存，尝试从后端 /auth/me 获取基本资料
                me = self.api_client.get_user_info()
                if me:
                    self.api_client.user_info = {
                        'username': me.get('username'),
                    }
                    ui_data = self.api_client.user_info
            if ui_data:
                dialog.set_user_info(ui_data)
        else:
            # 未登录，显示登录对话框
            from ui.dialogs.login_dialog import LoginDialog
            dialog = LoginDialog(self, self.api_client)  # 传入API客户端实例
            dialog.login_success.connect(self.on_login_success)
        dialog.exec()
    
    def open_deepseek_dialog(self):
        """打开DeepSeek对话框"""
        QMessageBox.information(self, "智能问答", "智能问答功能研发中。")

    def show_context_menu(self, position):
        """显示右键菜单。
        - 公共资源模式：阅读/下载/分享/举报
        - 用户态模式：打开/刷新/新建文件夹/重命名/移动/复制/删除/上传
        """
        try:
            # 公共资源模式
            if self.in_public:
                index = self.file_tree.indexAt(position)
                if not index.isValid():
                    return
                row = index.row()
                model = self.file_tree.model()
                if model is None:
                    return
                menu = QMenu(self)
                act_read = menu.addAction("阅读")
                act_download = menu.addAction("下载")
                act_share = menu.addAction("分享")
                act_report = menu.addAction("举报")
                menu.addSeparator()
                act_about = menu.addAction("关于")
                global_pos = self.file_tree.viewport().mapToGlobal(position)
                action = menu.exec(global_pos)
                if action is None:
                    return
                if action == act_read:
                    self.on_public_cell_clicked(model.index(row, 4))
                elif action == act_download:
                    self.on_public_cell_clicked(model.index(row, 5))
                elif action == act_share:
                    self.on_public_cell_clicked(model.index(row, 6))
                elif action == act_report:
                    self.on_public_cell_clicked(model.index(row, 7))
                elif action == act_about:
                    self.show_about()
                return

            # 用户态模式
            index = self.file_tree.indexAt(position)
            if not index.isValid():
                return
            row = index.row()
            model = self.file_tree.model()
            if model is None:
                return
            name_item = model.item(row, 0)
            file_info = name_item.data(Qt.UserRole) if name_item else {}
            fs_id = (file_info or {}).get('fs_id') or (file_info or {}).get('fsid') or (file_info or {}).get('id')

            menu = QMenu(self)
            act_open = menu.addAction("打开")
            act_refresh = menu.addAction("刷新")
            menu.addSeparator()
            act_new_folder = menu.addAction("新建文件夹")
            act_rename = menu.addAction("重命名")
            act_move = menu.addAction("移动到...")
            act_copy = menu.addAction("复制到...")
            act_delete = menu.addAction("删除")
            menu.addSeparator()
            act_upload_local = menu.addAction("上传本地文件...")
            act_upload_text = menu.addAction("上传文本...")
            act_upload_url = menu.addAction("通过URL上传...")

            global_pos = self.file_tree.viewport().mapToGlobal(position)
            action = menu.exec(global_pos)
            if action is None:
                return

            if action == act_open:
                QMessageBox.information(self, "打开", "打开功能即将支持。")
                return
            if action == act_refresh:
                self.refresh_user_files()
                return
            if action == act_new_folder:
                text, ok = QInputDialog.getText(self, "新建文件夹", "名称：")
                if ok and text.strip():
                    resp = self.api_client.create_folder(self.current_folder or '/', text.strip())
                    self._show_result_msg(resp, "新建文件夹")
                    self.refresh_user_files()
                return
            if action == act_rename:
                if not fs_id:
                    QMessageBox.warning(self, "重命名", "请选择一个文件/夹")
                    return
                new_name, ok = QInputDialog.getText(self, "重命名", "新名称：")
                if ok and new_name.strip():
                    resp = self.api_client.rename_file(str(fs_id), new_name.strip())
                    self._show_result_msg(resp, "重命名")
                    self.refresh_user_files()
                return
            if action == act_move:
                if not fs_id:
                    QMessageBox.warning(self, "移动", "请选择一个文件/夹")
                    return
                target, ok = QInputDialog.getText(self, "移动到", "目标目录：", text=self.current_folder or '/')
                if ok and target.strip():
                    resp = self.api_client.move_file(str(fs_id), target.strip())
                    self._show_result_msg(resp, "移动")
                    self.refresh_user_files()
                return
            if action == act_copy:
                if not fs_id:
                    QMessageBox.warning(self, "复制", "请选择一个文件/夹")
                    return
                target, ok = QInputDialog.getText(self, "复制到", "目标目录：", text=self.current_folder or '/')
                if ok and target.strip():
                    resp = self.api_client.copy_file(str(fs_id), target.strip())
                    self._show_result_msg(resp, "复制")
                    self.refresh_user_files()
                return
            if action == act_delete:
                if not fs_id:
                    QMessageBox.warning(self, "删除", "请选择一个文件/夹")
                    return
                if QMessageBox.question(self, "删除", "确定要删除所选项吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
                    resp = self.api_client.delete_file(str(fs_id))
                    self._show_result_msg(resp, "删除")
                    self.refresh_user_files()
                return
            if action == act_upload_local:
                path = QFileDialog.getOpenFileName(self, "选择文件")[0]
                if path:
                    resp = self.api_client.upload_local_file(path, os.path.join(self.current_folder or '/', os.path.basename(path)))
                    self._show_result_msg(resp, "上传文件")
                    self.refresh_user_files()
                return
            if action == act_upload_text:
                text, ok = QInputDialog.getMultiLineText(self, "上传文本", "内容：")
                if ok and text:
                    name, ok2 = QInputDialog.getText(self, "文件名", "例如 note.txt：", text="note.txt")
                    if ok2 and name.strip():
                        resp = self.api_client.upload_text_file(text, os.path.join(self.current_folder or '/', name.strip()))
                        self._show_result_msg(resp, "上传文本")
                        self.refresh_user_files()
                return
            if action == act_upload_url:
                url, ok = QInputDialog.getText(self, "通过URL上传", "资源URL：")
                if ok and url:
                    name, ok2 = QInputDialog.getText(self, "保存为", "文件名：")
                    if ok2 and name.strip():
                        resp = self.api_client.user_upload_url(url.strip(), self.current_folder or '/', name.strip())
                        self._show_result_msg(resp, "URL上传")
                        self.refresh_user_files()
                return
        except Exception as e:
            try:
                QMessageBox.warning(self, "菜单", f"操作失败：{e}")
            except Exception:
                pass

    def _show_result_msg(self, resp, action_name: str):
        """统一提示后端结果。"""
        try:
            ok = isinstance(resp, dict) and (resp.get('status') == 'ok' or resp.get('success') is True or resp.get('errno') in (0, '0'))
            if ok:
                self.status_label.setText(f"{action_name}成功")
            else:
                err = None
                if isinstance(resp, dict):
                    err = resp.get('error') or (resp.get('data') or {}).get('errmsg')
                QMessageBox.warning(self, action_name, err or f"{action_name}失败")
        except Exception:
            pass

    def refresh_user_files(self):
        """刷新用户态当前目录文件列表。"""
        try:
            if not self.api_client.is_logged_in():
                QMessageBox.information(self, "刷新", "请先登录")
                return
            result = self.api_client.list_files(self.current_folder or '/', limit=1000)
            files = []
            if isinstance(result, dict):
                data = result.get('data') or {}
                files = result.get('list') or result.get('files') or data.get('list') or data.get('files') or []
            elif isinstance(result, list):
                files = result
            self.display_files(files, append=False)
            self.status_label.setText("已刷新")
        except Exception as e:
            QMessageBox.warning(self, "刷新", f"失败：{e}")
    
    def check_scroll_position(self, value):
        """检查滚动位置，到底时加载更多"""
        scrollbar = self.file_tree.verticalScrollBar()
        # 公共资源模式：到底自动加载下一页
        if self.in_public:
            if value == scrollbar.maximum() and not self.public_loading and self.public_has_more:
                self.load_public_resources(load_more=True)
            return
        # 原有逻辑（网盘文件）
        # 当滚动到底部且不在加载状态且还有更多数据时
        if (value == scrollbar.maximum() and 
            not self.is_loading and 
            self.has_more):
            self.load_more_files()
        elif value == scrollbar.maximum() and not self.has_more:
            # 当滚动到底部但没有更多数据时显示提示
            self.status_label.setText("已加载全部文件")
    
    def load_more_files(self):
        """加载更多文件"""
        self.is_loading = True
        self.status_label.setText("正在加载更多文件...")
        self.current_page += 1
        
        try:
            # 构造请求参数
            params = {
                'method': 'list',
                'access_token': self.access_token,
                'dir': self.current_folder,
                'order': 'time',
                'desc': 1,
                'start': (self.current_page - 1) * self.page_size,
                'limit': self.page_size
            }
            
            # 调用百度网盘API
            response = requests.get(
                'https://pan.baidu.com/rest/2.0/xpan/file',
                params=params
            )
            
            result = response.json()
            if result.get('errno') == 0:
                files = result.get('list', [])
                
                # 如果返回的文件数小于页大小，说明没有更多数据了
                if len(files) < self.page_size:
                    self.has_more = False
                    self.status_label.setText("已加载全部文件")
                
                # 添加新的文件到列表
                if files:
                    self.display_files(files, append=True)
                    if self.has_more:
                        self.status_label.setText(f"已加载第 {self.current_page} 页")
                else:
                    self.has_more = False
                    self.status_label.setText("已加载全部文件")
            else:
                self.status_label.setText(f"加载失败：错误码 {result.get('errno')}")
                
        except Exception as e:
            self.status_label.setText(f"加载失败：{str(e)}")
        finally:
            self.is_loading = False

    def download_selected_files(self):
        """批量下载选择的文件"""
        if not self.is_vip:
            QMessageBox.warning(self, "提示", "批量下载功能仅对VIP用户开放")
            return

        # 检查是否有正在进行的下载任务
        if (self.download_worker and self.download_worker.isRunning()) or \
           (hasattr(self, 'batch_download_worker') and self.batch_download_worker and self.batch_download_worker.isRunning()):
            QMessageBox.warning(self, "提示", "有正在进行的下载任务，请等待当前下载完成。")
            return

        # 获取所有选中的项目
        selected_indexes = self.file_tree.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "提示", "请先选择要下载的文件")
            return

        # 获取保存目录
        save_dir = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not save_dir:
            return

        try:
            # 创建下载队列
            download_queue = []
            for index in selected_indexes:
                file_info = self.model.item(index.row(), 0).data(Qt.UserRole)
                if file_info:
                    fs_id = file_info.get('fs_id')
                    file_name = file_info.get('server_filename')
                    if fs_id:
                        save_path = os.path.join(save_dir, file_name)
                        download_queue.append((fs_id, save_path, file_name))

            if not download_queue:
                return

            # 显示进度条
            self.progress_bar.show()
            self.status_label.setText(f"准备下载 {len(download_queue)} 个文件...")

            # 创建批量下载线程
            self.batch_download_worker = BatchDownloadWorker(
                self.access_token,
                download_queue
            )
            self.batch_download_worker.progress.connect(self.update_batch_download_progress)
            self.batch_download_worker.finished.connect(self.batch_download_finished)
            self.batch_download_worker.start()

        except Exception as e:
            self.status_label.setText(f"批量下载失败: {str(e)}")
            self.progress_bar.hide()

    def update_batch_download_progress(self, current, total, file_name):
        """更新批量下载进度"""
        pass

    def batch_download_finished(self):
        """批量下载完成"""
        pass

    def pay_once_download(self, file_info):
        """单次付费下载"""
        QMessageBox.information(self, "付费下载", "付费下载功能已移除业务逻辑，仅保留界面。")

    def start_actual_download(self, file_info):
        """实际开始下载文件（付费下载后调用）"""
        QMessageBox.information(self, "下载", "下载功能已移除业务逻辑，仅保留界面。")

    def check_vip_status(self):
        """检查用户VIP状态（本地）"""
        pass
        
    def set_vip_status(self, is_vip: bool):
        """设置用户VIP状态（本地）"""
        self.is_vip = is_vip
        # 更新文件树的选择模式
        if is_vip:
            self.file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        else:
            self.file_tree.setSelectionMode(QAbstractItemView.SingleSelection)

    def start_download(self, file_info):
        """开始下载文件"""
        QMessageBox.information(self, "下载", "下载功能已移除业务逻辑，仅保留界面。")

    def on_download_finished(self, success, file_name):
        """处理下载完成的逻辑"""
        QMessageBox.information(self, "下载完成", "下载功能已移除业务逻辑，仅保留界面。")

    def share_file(self, file_info):
        """分享文件信息"""
        QMessageBox.information(self, "分享", "分享功能已移除业务逻辑，仅保留界面。")

    def show_report_dialog(self, file_info):
        """显示举报对话框"""
        QMessageBox.information(self, "举报", "举报功能已移除业务逻辑，仅保留界面。")

    def format_size(self, size_bytes):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def init_update_manager(self):
        """初始化更新检测管理器"""
        try:
            from core.update_manager import init_update_manager
            
            # 初始化更新管理器
            self.update_manager = init_update_manager(
                parent=self,
                api_base_url="http://118.24.67.10",  # 使用您的实际API地址
                current_version="1.0.1",
                platform="desktop"
            )
            
            # 连接信号
            self.update_manager.update_available.connect(self.on_update_available)
            self.update_manager.check_error.connect(self.on_update_check_error)
            
            # 启动自动检查
            self.update_manager.start_auto_check(30 * 60 * 1000)  # 30分钟检查一次
            
            print("[DEBUG] 更新检测管理器初始化成功")
            
        except Exception as e:
            print(f"[DEBUG] 更新检测管理器初始化失败: {e}")
            self.update_manager = None

    def on_update_available(self, result):
        """处理更新可用信号"""
        print(f"[DEBUG] 发现更新: {result.get('message', '')}")
        # 更新管理器会自动显示更新对话框，这里可以添加额外的处理逻辑
        
    def on_update_check_error(self, error):
        """处理更新检查错误信号"""
        print(f"[DEBUG] 更新检查错误: {error}")
        # 可以在这里添加错误处理逻辑，比如显示状态栏消息等

    def show_about(self):
        """显示关于信息"""
        about_text = (
            "云栈-您身边的共享资料库 V1.0.1\n\n"
            "支持多账号管理、文件分享、下载、上传、举报等功能。\n"
            "微信：LOOKHX\n"
            "© 2023 云栈团队 保留所有权利。"
        )
        QMessageBox.about(self, "关于云栈", about_text)

    def load_shared_folder(self):
        """加载共享文件夹内容（演示用）"""
        try:
            # 创建一个新的标准项模型，并设置列标题
            self.model = QStandardItemModel()
            self.model.setHorizontalHeaderLabels(["名称", "类型", "大小", "ID", "分类"])
            self.file_tree.setModel(self.model)
            
            # 设置列宽
            self.file_tree.setColumnWidth(0, 300)  # 名称列宽
            self.file_tree.setColumnWidth(1, 100)  # 类型列宽
            self.file_tree.setColumnWidth(2, 100)  # 大小列宽
            self.file_tree.setColumnWidth(3, 80)   # ID列宽
            
            # 添加演示数据
            demo_files = [
                {"server_filename": "示例文档1.pdf", "category": 4, "size": 1024*1024, "fs_id": "12345"},
                {"server_filename": "示例图片1.jpg", "category": 3, "size": 512*1024, "fs_id": "23456"},
                {"server_filename": "示例视频1.mp4", "category": 1, "size": 10*1024*1024, "fs_id": "34567"},
                {"server_filename": "示例音频1.mp3", "category": 2, "size": 5*1024*1024, "fs_id": "45678"},
                {"server_filename": "示例文档2.docx", "category": 4, "size": 2*1024*1024, "fs_id": "56789"},
            ]
            
            self.display_files(demo_files)
            
        except Exception as e:
            QMessageBox.warning(self, "加载失败", f"演示加载失败: {str(e)}")
    
    def display_files(self, files, append=False):
        """显示文件列表"""
        try:
            # 如果不是追加模式且当前有行，则先清空
            if not append and self.model.rowCount() > 0:
                self.model.removeRows(0, self.model.rowCount())
            
            # 添加每个文件项
            for file in files:
                # 创建名称列
                name_item = QStandardItem(QIcon(get_icon_path(self.get_file_icon(file))), file.get("server_filename", ""))
                name_item.setData(file, Qt.UserRole)
                
                # 创建其他列
                type_item = QStandardItem(self.map_category_to_type(file.get("category", 0)))
                size_item = QStandardItem(self.format_size(file.get("size", 0)))
                id_item = QStandardItem(str(file.get("fs_id", "")))
                category_item = QStandardItem(str(file.get("category", 0)))
                
                # 将这一行添加到模型中
                self.model.appendRow([name_item, type_item, size_item, id_item, category_item])
                
            # 更新界面状态
            if not append:
                # 滚动到顶部
                self.file_tree.scrollToTop()
            
        except Exception as e:
            QMessageBox.warning(
                self, 
                "显示文件失败", 
                f"显示文件失败: {str(e)}"
            )
    
    def get_file_icon(self, file_info):
        """根据文件类型返回对应的图标名称"""
        category = file_info.get("category", 0)
        filename = file_info.get("server_filename", "").lower()
        
        if category == 1:  # 视频
            return "video.png"
        elif category == 2:  # 音频
            return "audio.png"
        elif category == 3:  # 图片
            return "image.png"
        elif category == 4:  # 文档
            if filename.endswith(".pdf"):
                return "pdf.png"
            elif filename.endswith((".doc", ".docx")):
                return "word.png"
            elif filename.endswith((".xls", ".xlsx")):
                return "excel.png"
            elif filename.endswith((".ppt", ".pptx")):
                return "ppt.png"
            else:
                return "document.png"
        else:
            return "file.png"  # 默认文件图标
    
    def format_size(self, size_bytes):
        """格式化文件大小为人类可读格式"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def map_category_to_type(self, category):
        """映射分类ID到文件类型名称"""
        categories = {
            1: "视频",
            2: "音频",
            3: "图片",
            4: "文档",
            5: "应用",
            6: "其他",
            7: "种子"
        }
        return categories.get(category, "未知")

    def download_file(self, file_info):
        """下载文件"""
        QMessageBox.information(self, "下载文件", "下载功能已移除业务逻辑，仅保留界面。")

    def update_upload_progress(self, status, value):
        """更新上传进度"""
        pass
        
    def update_progress(self, message, percent):
        """更新进度对话框"""
        if hasattr(self, 'loading_dialog'):
            self.loading_dialog.update_status(message, percent)
            
    def upload_finished(self, success, message, failed_files):
        """上传完成的处理"""
        pass

    def check_scroll_position(self, value):
        """检查滚动位置，到底时加载更多"""
        scrollbar = self.file_tree.verticalScrollBar()
        # 公共资源模式：到底自动加载下一页
        if self.in_public:
            if value == scrollbar.maximum() and not self.public_loading and self.public_has_more:
                self.load_public_resources(load_more=True)
            return
        # 原有逻辑（网盘文件）
        # 当滚动到底部且不在加载状态且还有更多数据时
        if (value == scrollbar.maximum() and 
            not self.is_loading and 
            self.has_more):
            self.load_more_files()
        elif value == scrollbar.maximum() and not self.has_more:
            # 当滚动到底部但没有更多数据时显示提示
            self.status_label.setText("已加载全部文件")

    def load_more_files(self):
        """加载更多文件"""
        self.is_loading = True
        self.status_label.setText("正在加载更多文件...")
        self.current_page += 1
        
        try:
            # 构造请求参数
            params = {
                'method': 'list',
                'access_token': self.access_token,
                'dir': self.current_folder,
                'order': 'time',
                'desc': 1,
                'start': (self.current_page - 1) * self.page_size,
                'limit': self.page_size
            }
            
            # 调用百度网盘API
            response = requests.get(
                'https://pan.baidu.com/rest/2.0/xpan/file',
                params=params
            )
            
            result = response.json()
            if result.get('errno') == 0:
                files = result.get('list', [])
                
                # 如果返回的文件数小于页大小，说明没有更多数据了
                if len(files) < self.page_size:
                    self.has_more = False
                    self.status_label.setText("已加载全部文件")
                
                # 添加新的文件到列表
                if files:
                    self.display_files(files, append=True)
                    if self.has_more:
                        self.status_label.setText(f"已加载第 {self.current_page} 页")
                else:
                    self.has_more = False
                    self.status_label.setText("已加载全部文件")
            else:
                self.status_label.setText(f"加载失败：错误码 {result.get('errno')}")
                
        except Exception as e:
            self.status_label.setText(f"加载失败：{str(e)}")
        finally:
            self.is_loading = False

    def download_selected_files(self):
        """批量下载选择的文件"""
        if not self.is_vip:
            QMessageBox.warning(self, "提示", "批量下载功能仅对VIP用户开放")
            return

        # 检查是否有正在进行的下载任务
        if (self.download_worker and self.download_worker.isRunning()) or \
           (hasattr(self, 'batch_download_worker') and self.batch_download_worker and self.batch_download_worker.isRunning()):
            QMessageBox.warning(self, "提示", "有正在进行的下载任务，请等待当前下载完成。")
            return

        # 获取所有选中的项目
        selected_indexes = self.file_tree.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "提示", "请先选择要下载的文件")
            return

        # 获取保存目录
        save_dir = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not save_dir:
            return

        try:
            # 创建下载队列
            download_queue = []
            for index in selected_indexes:
                file_info = self.model.item(index.row(), 0).data(Qt.UserRole)
                if file_info:
                    fs_id = file_info.get('fs_id')
                    file_name = file_info.get('server_filename')
                    if fs_id:
                        save_path = os.path.join(save_dir, file_name)
                        download_queue.append((fs_id, save_path, file_name))

            if not download_queue:
                return

            # 显示进度条
            self.progress_bar.show()
            self.status_label.setText(f"准备下载 {len(download_queue)} 个文件...")

            # 创建批量下载线程
            self.batch_download_worker = BatchDownloadWorker(
                self.access_token,
                download_queue
            )
            self.batch_download_worker.progress.connect(self.update_batch_download_progress)
            self.batch_download_worker.finished.connect(self.batch_download_finished)
            self.batch_download_worker.start()

        except Exception as e:
            self.status_label.setText(f"批量下载失败: {str(e)}")
            self.progress_bar.hide()

    def update_batch_download_progress(self, current, total, file_name):
        """更新批量下载进度"""
        pass

    def batch_download_finished(self):
        """批量下载完成"""
        pass

    def pay_once_download(self, file_info):
        """单次付费下载"""
        QMessageBox.information(self, "付费下载", "付费下载功能已移除业务逻辑，仅保留界面。")

    def start_actual_download(self, file_info):
        """实际开始下载文件（付费下载后调用）"""
        QMessageBox.information(self, "下载", "下载功能已移除业务逻辑，仅保留界面。")

    def check_vip_status(self):
        """检查用户VIP状态（本地）"""
        pass
        
    def set_vip_status(self, is_vip: bool):
        """设置用户VIP状态（本地）"""
        self.is_vip = is_vip
        # 更新文件树的选择模式
        if is_vip:
            self.file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        else:
            self.file_tree.setSelectionMode(QAbstractItemView.SingleSelection)

    def start_download(self, file_info):
        """开始下载文件"""
        QMessageBox.information(self, "下载", "下载功能已移除业务逻辑，仅保留界面。")

    def on_download_finished(self, success, file_name):
        """处理下载完成的逻辑"""
        QMessageBox.information(self, "下载完成", "下载功能已移除业务逻辑，仅保留界面。")

    def share_file(self, file_info):
        """分享文件信息"""
        QMessageBox.information(self, "分享", "分享功能已移除业务逻辑，仅保留界面。")

    def show_report_dialog(self, file_info):
        """显示举报对话框"""
        QMessageBox.information(self, "举报", "举报功能已移除业务逻辑，仅保留界面。")



