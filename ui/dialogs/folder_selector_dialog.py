#!/usr/bin/env python3
"""
目录选择对话框
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
                              QMessageBox, QHeaderView, QAbstractItemView)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon
from core.api_client import APIClient
from core.utils import get_icon_path


class FolderSelectorDialog(QDialog):
    """目录选择对话框"""
    
    folder_selected = Signal(str)  # 选择目录信号
    
    def __init__(self, parent=None, api_client=None, current_folder="/", title="选择目录"):
        super().__init__(parent)
        self.api_client = api_client or APIClient()
        self.current_folder = current_folder
        self.folders = {}  # 缓存目录结构
        
        self.setWindowTitle(title)
        self.setFixedSize(500, 400)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        self.init_ui()
        self.load_folders()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel("选择目标目录")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title_label.setStyleSheet("color: #1976D2; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 当前路径显示
        self.path_label = QLabel(f"当前路径: {self.current_folder}")
        self.path_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background: #f5f5f5; border-radius: 3px;")
        layout.addWidget(self.path_label)
        
        # 目录树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("目录结构")
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: white;
            }
            QTreeWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background: #e3f2fd;
                color: #1976D2;
            }
            QTreeWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        layout.addWidget(self.tree)
        
        # 手动输入路径
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("或手动输入路径:"))
        self.path_input = QLineEdit()
        self.path_input.setText(self.current_folder)
        self.path_input.setPlaceholderText("例如: /我的文档/工作")
        input_layout.addWidget(self.path_input)
        layout.addLayout(input_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_folders)
        button_layout.addWidget(self.refresh_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept_selection)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background: #1976D2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1565C0;
            }
        """)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.tree.itemDoubleClicked.connect(self.accept_selection)
    
    def load_folders(self):
        """加载目录结构"""
        try:
            self.tree.clear()
            
            # 添加根目录
            root_item = QTreeWidgetItem(self.tree, ["/ (根目录)"])
            root_item.setData(0, Qt.UserRole, "/")
            root_item.setIcon(0, QIcon(get_icon_path('folder.png')))
            root_item.setExpanded(True)
            
            # 加载用户态目录
            if self.api_client.is_logged_in():
                # 更新路径标签显示加载状态
                self.path_label.setText("正在加载目录...")
                result = self.api_client.list_files("/", limit=1000)
                
                if isinstance(result, dict):
                    data = result.get('data') or {}
                    files = result.get('list') or result.get('files') or data.get('list') or data.get('files') or []
                elif isinstance(result, list):
                    files = result
                else:
                    files = []
                
                # 只显示目录
                folders = [f for f in files if int(f.get('isdir') or 0) == 1]
                self._build_tree(root_item, folders, "/")
                
                # 恢复路径标签显示
                self.path_label.setText(f"当前路径: {self.current_folder}")
            
            # 展开到当前目录
            self._expand_to_path(self.current_folder)
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载目录失败: {e}")
    
    def _build_tree(self, parent_item, folders, parent_path):
        """递归构建目录树"""
        try:
            for folder in folders:
                folder_name = folder.get('server_filename') or folder.get('file_name') or folder.get('name') or ''
                folder_path = folder.get('path') or folder.get('server_path') or ''
                
                if not folder_path.startswith(parent_path):
                    continue
                
                # 创建目录项
                item = QTreeWidgetItem(parent_item, [folder_name])
                item.setData(0, Qt.UserRole, folder_path)
                item.setIcon(0, QIcon(get_icon_path('folder.png')))
                
                # 递归添加子目录
                child_folders = [f for f in folders if f.get('path', '').startswith(folder_path + '/') and f.get('path', '') != folder_path]
                if child_folders:
                    self._build_tree(item, child_folders, folder_path)
                    
        except Exception as e:
            print(f"[ERROR] 构建目录树失败: {e}")
    
    def _expand_to_path(self, target_path):
        """展开到指定路径"""
        try:
            if not target_path or target_path == "/":
                return
            
            # 查找并展开路径
            items = self.tree.findItems(target_path, Qt.MatchExactly | Qt.MatchRecursive, 1)
            if items:
                item = items[0]
                # 展开父级
                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                # 选中当前项
                self.tree.setCurrentItem(item)
                self.path_input.setText(target_path)
                
        except Exception as e:
            print(f"[ERROR] 展开路径失败: {e}")
    
    def on_selection_changed(self):
        """选择改变时的处理"""
        try:
            current_item = self.tree.currentItem()
            if current_item:
                path = current_item.data(0, Qt.UserRole)
                if path:
                    self.path_input.setText(path)
                    self.path_label.setText(f"当前路径: {path}")
        except Exception as e:
            print(f"[ERROR] 选择改变处理失败: {e}")
    
    def accept_selection(self):
        """确认选择"""
        try:
            # 优先使用手动输入的路径
            selected_path = self.path_input.text().strip()
            
            if not selected_path:
                QMessageBox.warning(self, "提示", "请选择或输入目标目录")
                return
            
            # 验证路径格式
            if not selected_path.startswith('/'):
                selected_path = '/' + selected_path
            
            # 不能选择当前目录
            if selected_path == self.current_folder:
                QMessageBox.warning(self, "提示", "不能选择当前目录作为目标")
                return
            
            # 更新当前文件夹状态
            self.current_folder = selected_path
            
            self.folder_selected.emit(selected_path)
            self.accept()
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"选择目录失败: {e}")
