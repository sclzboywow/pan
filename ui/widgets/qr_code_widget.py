#!/usr/bin/env python3
"""
二维码显示组件
"""

import qrcode
from io import BytesIO
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import requests


class QRCodeWidget(QLabel):
    """二维码显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 300)
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                background: white;
            }
        """)
        self.setText("等待二维码...")
        self.setAlignment(Qt.AlignCenter)
    
    def _set_pixmap_from_bytes(self, data: bytes):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        self.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def set_qr_code(self, qr_url: str):
        """设置二维码
        逻辑：
        1) 若传入为 http(s) 链接，优先尝试请求；若返回图片或二进制流，直接显示图片（避免“码中码”）；
           否则将该链接字符串生成二维码。
        2) 非链接文本则直接编码为二维码。
        """
        try:
            print(f"[QR] set_qr_code url= {qr_url}")
            if isinstance(qr_url, str) and qr_url.startswith(("http://", "https://")):
                try:
                    # 显式禁用系统代理，添加UA，允许重定向
                    headers = {"User-Agent": "PanClient/1.0 (+https://example.local)"}
                    resp = requests.get(
                        qr_url,
                        timeout=10,
                        allow_redirects=True,
                        headers=headers,
                        proxies={"http": None, "https": None}
                    )
                    content_type = (resp.headers.get("Content-Type") or "").lower()
                    print(f"[QR] http status= {resp.status_code}, content-type= {content_type}")
                    is_image_type = content_type.startswith("image/")
                    is_octet_stream = content_type in ("application/octet-stream", "binary/octet-stream", "application/octetstream")
                    if resp.status_code == 200 and (is_image_type or is_octet_stream):
                        self._set_pixmap_from_bytes(resp.content)
                        return
                except Exception as e:
                    print(f"[QR] download error: {e}")
                    # 忽略网络异常，回退到本地编码
                    pass
            
            # 回退：将传入字符串编码为二维码
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            self._set_pixmap_from_bytes(buffer.getvalue())
        except Exception as e:
            print(f"生成/显示二维码失败: {e}")
            self.setText("二维码生成失败")
    
    def clear_qr_code(self):
        """清除二维码"""
        self.setText("等待二维码...")
        self.setPixmap(QPixmap())
