from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt
from ui.widgets.loading_spinner import LoadingSpinner

class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量上传")
        self.setFixedSize(300, 150)
        self.setWindowFlags(Qt.WindowType.Dialog | 
                          Qt.WindowType.CustomizeWindowHint | 
                          Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout()
        
        # 创建并添加加载动画
        self.spinner = LoadingSpinner(self)
        spinner_container = QWidget()
        spinner_layout = QVBoxLayout()
        spinner_layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        spinner_container.setLayout(spinner_layout)
        
        # 状态文本
        self.status_label = QLabel("准备上传...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 进度文本
        self.progress_label = QLabel("0%")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(spinner_container)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_label)
        self.setLayout(layout)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background: white;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
            QLabel {
                color: #333;
                font-size: 14px;
                margin-top: 10px;
            }
        """)
    
    def update_status(self, text, percent):
        self.status_label.setText(text)
        self.progress_label.setText(f"{percent}%")
        
    def closeEvent(self, event):
        # 确保关闭对话框时停止动画
        if hasattr(self, 'spinner'):
            self.spinner.timer.stop()
        super().closeEvent(event) 