import sys
import os
import time
import hashlib
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                              QTreeView, QFileDialog, QMessageBox, QProgressBar,
                              QStatusBar, QSystemTrayIcon, QMenu, QFrame,
                              QGraphicsDropShadowEffect, QHeaderView, QDialog,
                              QGroupBox, QGridLayout, QAbstractItemView, QStyle)
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
from PySide6.QtWidgets import QStyledItemDelegate
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
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
    
    def get_values(self):
        return self.period_input.text().strip(), self.pwd_input.text().strip(), self.remark_input.text().strip()

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
        
        # 默认：进入公共资源页面
        self.open_public_resources()
        
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
    
    def setup_api_connections(self):
        """设置API客户端信号连接"""
        self.api_client.login_success.connect(self.on_login_success)
        self.api_client.login_failed.connect(self.on_login_failed)
        self.api_client.auth_success.connect(self.on_auth_success)
        self.api_client.auth_failed.connect(self.on_auth_failed)
        self.api_client.api_error.connect(self.on_api_error)
    
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
        dialog = LoginDialog(self)
        dialog.login_success.connect(self.on_login_success)
        dialog.exec()
    
    def on_login_success(self, data):
        """登录成功处理"""
        self.status_label.setText("已登录")
        self.load_files()
    
    def on_login_failed(self, error_msg):
        """登录失败处理"""
        self.status_label.setText(f"登录失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"登录失败: {error_msg}")
    
    def on_auth_success(self, token_data):
        """授权成功处理"""
        self.api_client.baidu_token = token_data
        self.status_label.setText("授权成功")
        QMessageBox.information(self, "成功", "百度网盘授权成功！")
        self.load_files()
    
    def on_auth_failed(self, error_msg):
        """授权失败处理"""
        self.status_label.setText(f"授权失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"授权失败: {error_msg}")
    
    def on_api_error(self, error_msg):
        """API错误处理"""
        self.status_label.setText(f"API错误: {error_msg}")
        QMessageBox.critical(self, "错误", f"API错误: {error_msg}")
    
    def load_files(self):
        """加载文件列表"""
        if not self.api_client.is_logged_in():
            self.show_login_dialog()
            return
        
        self.is_loading = True
        self.status_label.setText("正在加载文件...")
        
        # 调用API获取文件列表
        result = self.api_client.list_files(self.current_folder, self.page_size)
        if result and result.get("status") == "ok":
            data = result.get("data", {})
            files = data.get("list", [])
            self.display_files(files)
            self.status_label.setText(f"已加载 {len(files)} 个文件")
        else:
            error_msg = result.get("error", "加载文件失败") if result else "网络连接失败"
            self.status_label.setText(f"加载失败: {error_msg}")
            QMessageBox.critical(self, "错误", f"加载文件失败: {error_msg}")
        
        self.is_loading = False
    
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
        
        content_layout.addWidget(self.file_tree)  # 将文件树添加到内容区布局
        
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
        QMessageBox.information(self, '版本检查', '版本检查功能已移除业务逻辑，仅保留界面。')

    def closeEvent(self, event):
        """重写关闭事件"""
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
        reply = QMessageBox.question(
            self,
            '退出确认',
            "确定要退出程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
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
        self.current_folder = '/'
        self.load_files()
    
    def upload_file(self):
        """上传文件对话框"""
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
        
        # 选择文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择要上传的文件", 
            "", 
            "所有文件 (*)"
        )
        
        if not file_path:
            return
        
        # 选择远程路径
        remote_path, ok = QInputDialog.getText(
            self, 
            "上传设置", 
            "请输入远程路径:", 
            text="/"
        )
        
        if not ok or not remote_path:
            return
        
        # 显示进度对话框
        self.loading_dialog.show()
        self.loading_dialog.update_status("正在上传文件...", 0)
        
        # 调用上传API
        result = self.api_client.upload_local_file(file_path, remote_path)
        if result and result.get("status") == "ok":
            self.loading_dialog.hide()
            QMessageBox.information(self, "成功", "文件上传成功！")
            self.load_files()  # 刷新文件列表
        else:
            self.loading_dialog.hide()
            error_msg = result.get("error", "上传失败") if result else "网络连接失败"
            QMessageBox.critical(self, "错误", f"上传失败: {error_msg}")
    
    def open_public_resources(self):
        """打开公共资源页（在主内容区加载）"""
        # 进入公共资源模式
        self.in_public = True
        self.public_page = 1
        self.public_has_more = True
        self.public_loading = False
        self.status_label.setText("公共资源：加载中...")
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
            if not index.isValid():
                return
            row = index.row()
            col = index.column()
            model = self.file_tree.model()
            name_item = model.item(row, 0)
            payload = name_item.data(Qt.UserRole) if name_item else {}
            fs_id = payload.get('fs_id')
            # 下载列索引5
            if col == 5:
                # 公共资源：票据+代理下载（服务态）改为异步线程
                if not fs_id:
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
                    t = self.api_client.public_download_ticket(fsid=fs_id, ttl=300)
                    if not isinstance(t, dict) or t.get('status') != 'ok':
                        raise RuntimeError((t.get('data') or {}).get('errmsg') or t.get('error') or '票据获取失败')
                    tk = (t.get('data') or {}).get('ticket')
                    if not tk:
                        raise RuntimeError('票据为空')
                    return tk
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
                    self.status_label.setText("下载失败")
                    QMessageBox.warning(self, "下载", f"下载失败：{e}")
                return
            # 分享列索引6
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
                    QMessageBox.warning(self, "分享失败", err or "未知错误")
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
            dialog.exec()
        else:
            # 未登录，显示登录对话框
            from ui.dialogs.login_dialog import LoginDialog
            dialog = LoginDialog(self)
            dialog.login_success.connect(self.on_login_success)
        dialog.exec()
    
    def open_deepseek_dialog(self):
        """打开DeepSeek对话框"""
        QMessageBox.information(self, "智能问答", "智能问答功能已移除业务逻辑，仅保留界面。")

    def show_context_menu(self, position):
        """显示上下文菜单"""
        QMessageBox.information(self, "上下文菜单", "右键菜单功能已移除业务逻辑，仅保留界面。")
    
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
        QMessageBox.information(self, "加载更多", "加载更多功能已移除业务逻辑，仅保留界面。")

    def download_selected_files(self):
        """下载选中的文件"""
        QMessageBox.information(self, "批量下载", "批量下载功能已移除业务逻辑，仅保留界面。")

    def check_version(self):
        """检查版本更新"""
        QMessageBox.information(self, '版本检查', '版本检查功能已移除业务逻辑，仅保留界面。')

    def format_size(self, size_bytes):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def show_about(self):
        """显示关于信息"""
        about_text = (
            "云栈-您身边的共享资料库 V1.0.1\n\n"
            "这是一个简化版的界面演示程序，已移除所有业务逻辑。\n"
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



