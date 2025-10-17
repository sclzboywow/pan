from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, 
                              QFrame, QPushButton, QApplication, QMessageBox, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont, QPixmap
from core.utils import get_icon_path
from ui.widgets.material_button import MaterialButton

class UserInfoDialog(QDialog):
    def __init__(self, parent=None, api_client=None):
        super().__init__(parent)
        self.setWindowTitle("我的信息")
        self.setFixedSize(560, 360)
        self.machine_code = "DEMO-MACHINE-CODE-12345"
        self.user_info = None
        self.api_client = api_client
        
        # 头像/昵称/VIP/配额显示控件
        self.avatar_label = None
        self.baidu_name_label = None
        self.vip_label = None
        self.quota_label = None
        self.today_quota_label = None
        
        self.setup_ui()
        
        # 打开即刷新配额
        try:
            if self.api_client and self.api_client.is_logged_in():
                self.api_client.refresh_and_cache_user_quota()
                if hasattr(self.api_client, 'user_info') and self.api_client.user_info:
                    self.set_user_info(self.api_client.user_info)
        except Exception:
            pass

    def set_user_info(self, user_info):
        self.user_info = user_info
        self.update_display()

    def _fmt_bytes(self, b):
        try:
            b = float(b or 0)
        except Exception:
            b = 0.0
        for u in ['B','KB','MB','GB','TB','PB']:
            if b < 1024:
                return f"{b:.2f} {u}"
            b /= 1024
        return f"{b:.2f} EB"

    def update_display(self):
        if not self.user_info:
            return
        # 显示百度网盘昵称（主展示）
        if self.baidu_name_label:
            self.baidu_name_label.setText(self.user_info.get('baidu_name') or "-")
        # VIP
        if self.vip_label:
            self.vip_label.setText(f"VIP: {self.user_info.get('vip_type', 0)}")
        # 头像
        if self.avatar_label:
            avatar_url = self.user_info.get('avatar_url')
            if avatar_url:
                try:
                    import requests
                    # 禁用代理，添加User-Agent，允许重定向
                    headers = {"User-Agent": "PanClient/1.0.0"}
                    resp = requests.get(
                        avatar_url, 
                        timeout=8,
                        headers=headers,
                        proxies={"http": None, "https": None},
                        allow_redirects=True
                    )
                    if resp.status_code == 200:
                        pix = QPixmap()
                        if pix.loadFromData(resp.content):
                            self.avatar_label.setPixmap(pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        else:
                            print(f"[DEBUG] 头像图片格式不支持: {avatar_url}")
                    else:
                        print(f"[DEBUG] 头像请求失败: {resp.status_code}")
                except Exception as e:
                    print(f"[DEBUG] 头像加载异常: {e}")
        # 配额
        if self.quota_label:
            quota = self.user_info.get('quota') or {}
            total = quota.get('total', 0) or 0
            used = quota.get('used', 0) or 0
            free = quota.get('free', None)
            if free is None or float(free) <= 0:
                free = max(float(total) - float(used), 0)
            self.quota_label.setText(
                f"空间: 已用 {self._fmt_bytes(used)} / 总计 {self._fmt_bytes(total)}  （剩余 {self._fmt_bytes(free)}）"
            )
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(14)

        # 头像（居中）
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(80, 80)
        self.avatar_label.setStyleSheet("border-radius:40px; background:#f5f5f5;")
        self.avatar_label.setAlignment(Qt.AlignCenter)
        # 点击头像复制前端用户名（服务器用户名）
        try:
            self.avatar_label.setCursor(Qt.PointingHandCursor)
            def _on_avatar_click(evt):
                self.copy_frontend_username()
            self.avatar_label.mousePressEvent = _on_avatar_click
            self.avatar_label.setToolTip("点击复制前端用户名")
        except Exception:
            pass
        main_layout.addWidget(self.avatar_label, alignment=Qt.AlignHCenter)

        # 百度网盘昵称（主标题）
        self.baidu_name_label = QLabel("-")
        self.baidu_name_label.setStyleSheet("font-size:18px; font-weight:bold; color:#333;")
        self.baidu_name_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.baidu_name_label)

        # VIP 行
        self.vip_label = QLabel("VIP: 0")
        self.vip_label.setStyleSheet("color:#1976D2;")
        self.vip_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.vip_label)

        # 配额（总空间）
        self.quota_label = QLabel("空间: 加载中...")
        self.quota_label.setStyleSheet("color:#666;")
        self.quota_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.quota_label)

        # 今日额度
        self.today_quota_label = QLabel("今日额度: 加载中...")
        self.today_quota_label.setStyleSheet("color:#1976D2;")
        self.today_quota_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.today_quota_label)
        # 共用额度说明
        quota_note = QLabel("说明：阅读 / 下载 / 分享 共用每日总额度")
        quota_note.setAlignment(Qt.AlignCenter)
        quota_note.setStyleSheet("color:#999; font-size:12px;")
        main_layout.addWidget(quota_note)

        # 操作按钮区
        btn_row = QHBoxLayout()
        refresh_space_btn = MaterialButton("刷新空间配额")
        refresh_space_btn.clicked.connect(self.refresh_quota)
        btn_row.addWidget(refresh_space_btn)
        refresh_today_btn = MaterialButton("刷新今日额度")
        refresh_today_btn.clicked.connect(self.refresh_today_quota)
        btn_row.addWidget(refresh_today_btn)
        
        switch_btn = MaterialButton("切换账号")
        switch_btn.clicked.connect(self.on_switch_account)
        btn_row.addWidget(switch_btn)
        
        manage_btn = MaterialButton("删除账号")
        manage_btn.clicked.connect(self.on_remove_account)
        btn_row.addWidget(manage_btn)
        
        main_layout.addLayout(btn_row)

        main_layout.addStretch()
        self.setLayout(main_layout)

        # 初次拉取今日额度
        QTimer.singleShot(0, self.refresh_today_quota)

    def refresh_quota(self):
        if not self.api_client:
            QMessageBox.warning(self, "提示", "API 未初始化")
            return
        self.api_client.refresh_and_cache_user_quota()
        if hasattr(self.api_client, 'user_info') and self.api_client.user_info:
            self.set_user_info(self.api_client.user_info)

    def refresh_today_quota(self):
        if not self.api_client or not self.api_client.is_logged_in():
            if self.today_quota_label:
                self.today_quota_label.setText("今日额度: 未登录")
            return
        data = self.api_client.get_quota_today()
        if isinstance(data, dict) and data.get('status') == 'ok':
            q = data.get('data') or {}
            role = q.get('role') or '-'
            used = q.get('used') or 0
            total = q.get('total') or 0
            left = q.get('left') if q.get('left') is not None else max(int(total) - int(used), 0)
            if self.today_quota_label:
                self.today_quota_label.setText(f"今日额度（{role}）: 已用 {used} / 总计 {total}，剩余 {left}")
        else:
            err = (data or {}).get('error') if isinstance(data, dict) else 'unknown'
            if self.today_quota_label:
                self.today_quota_label.setText(f"今日额度: 获取失败（{err}）")

    def copy_machine_code(self, code):
        """复制机器码到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(code)
        QMessageBox.information(self, "复制成功", "机器码已复制到剪贴板") 

    def copy_frontend_username(self):
        """复制服务器端前端用户名（非百度昵称）"""
        try:
            username = None
            if self.api_client:
                # 优先从 user_info 取用户名
                ui = getattr(self.api_client, 'user_info', None) or {}
                username = ui.get('username') or None
                if not username:
                    me = self.api_client.get_user_info()
                    if isinstance(me, dict):
                        username = me.get('username')
            if not username:
                QMessageBox.information(self, "复制失败", "未获取到前端用户名")
                return
            QApplication.clipboard().setText(str(username))
            QMessageBox.information(self, "复制成功", f"已复制前端用户名：{username}")
        except Exception as e:
            QMessageBox.warning(self, "复制失败", str(e))

    def on_logout(self):
        if not self.api_client:
            return
        self.api_client.logout()
        QMessageBox.information(self, "提示", "已注销登录")
        self.accept()
        # 通知父窗口刷新UI
        if self.parent() and hasattr(self.parent(), 'status_label'):
            self.parent().status_label.setText("演示模式 - 点击用户信息进行登录")
        if self.parent() and hasattr(self.parent(), 'load_demo_files'):
            self.parent().load_demo_files()

    def on_switch_account(self):
        if not self.api_client:
            return
        self.api_client.load_accounts()
        accounts = getattr(self.api_client, 'accounts', {}) or {}
        if not accounts:
            QMessageBox.information(self, "提示", "暂无已登录账号，请先登录新账号")
            return
        # 弹出选择对话框
        dlg = QDialog(self)
        dlg.setWindowTitle("切换账号")
        dlg.setFixedSize(400, 380)
        v = QVBoxLayout(dlg)
        
        # 添加说明文字
        info_label = QLabel("选择要切换的账号，或添加新账号：")
        info_label.setStyleSheet("color: #666; font-size: 12px; margin-bottom: 10px;")
        v.addWidget(info_label)
        
        lst = QListWidget()
        for uk, data in accounts.items():
            ui = data.get('user_info') or {}
            name = ui.get('baidu_name') or ui.get('username') or uk
            item = QListWidgetItem(f"{name}  (uk: {uk})")
            item.setData(0x0100, uk)  # Qt.UserRole
            lst.addItem(item)
        v.addWidget(lst)
        btns = QHBoxLayout()
        add_new = MaterialButton("添加新账号")
        # 为添加新账号按钮设置特殊样式
        add_new.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 8px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        ok = MaterialButton("确定")
        cancel = MaterialButton("取消")
        btns.addWidget(add_new)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        v.addLayout(btns)
        
        chosen = { 'uk': None }
        def _accept():
            it = lst.currentItem()
            if not it:
                return
            chosen['uk'] = it.data(0x0100)
            dlg.accept()
        def _on_new_account_login(data):
            """新账号登录成功处理"""
            QMessageBox.information(self, "成功", "新账号登录成功！")
            # 刷新用户信息显示
            if hasattr(self.api_client, 'user_info') and self.api_client.user_info:
                self.set_user_info(self.api_client.user_info)
            # 通知父窗口更新状态
            if self.parent() and hasattr(self.parent(), 'status_label'):
                name = (self.api_client.user_info or {}).get('baidu_name') or '已登录'
                self.parent().status_label.setText(f"已登录：{name}")
        
        def _add_new_account():
            """添加新账号"""
            dlg.reject()  # 关闭当前对话框
            # 打开登录对话框添加新账号
            from ui.dialogs.login_dialog import LoginDialog
            login_dialog = LoginDialog(self, self.api_client)
            login_dialog.login_success.connect(_on_new_account_login)
            login_dialog.exec()
        
        add_new.clicked.connect(_add_new_account)
        ok.clicked.connect(_accept)
        cancel.clicked.connect(dlg.reject)
        lst.itemDoubleClicked.connect(lambda it: (chosen.__setitem__('uk', it.data(0x0100)), dlg.accept()))
        
        if dlg.exec() == QDialog.Accepted and chosen['uk']:
            if self.api_client.switch_account(chosen['uk']):
                # 切换成功：刷新本弹窗与父界面
                self.set_user_info(self.api_client.user_info or {})
                if self.parent() and hasattr(self.parent(), 'status_label'):
                    name = (self.api_client.user_info or {}).get('baidu_name') or '已登录'
                    self.parent().status_label.setText(f"已登录：{name}")
                QMessageBox.information(self, "提示", "已切换账号")
            else:
                QMessageBox.warning(self, "提示", "切换失败")

    def on_remove_account(self):
        if not self.api_client or not getattr(self.api_client, 'accounts', None):
            return
        if not self.api_client.current_account_uk:
            return
        uk = self.api_client.current_account_uk
        self.api_client.remove_account(uk)
        QMessageBox.information(self, "提示", "已删除当前账号")
        # 关闭并让父窗口回到演示或下一个账号
        self.accept()
        if self.parent() and hasattr(self.parent(), 'status_label'):
            if self.api_client.is_logged_in():
                self.parent().status_label.setText("已登录")
            else:
                self.parent().status_label.setText("演示模式 - 点击用户信息进行登录") 