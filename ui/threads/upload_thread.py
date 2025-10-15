#!/usr/bin/env python3
"""
批量上传线程（避免阻塞UI）
"""

from PySide6.QtCore import QThread, Signal
from typing import List, Dict, Any, Optional
import os
import hashlib


class UploadWorker(QThread):
    progress = Signal(str, int, int)  # status_text, done, total
    finished = Signal(int, int, int)  # success_cnt, failed_cnt, skipped_cnt

    def __init__(self, api_client, file_paths: List[str], is_public: bool, user_dir: Optional[str] = None):
        super().__init__()
        self.api_client = api_client
        self.file_paths = file_paths or []
        self.is_public = bool(is_public)
        self.user_dir = user_dir or "/"
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _compute_md5(self, path: str) -> Optional[str]:
        try:
            md5 = hashlib.md5()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    if self._stopped:
                        return None
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception:
            return None

    def run(self):
        total = len(self.file_paths)
        done = 0
        success_cnt = 0
        failed_cnt = 0
        skipped_cnt = 0

        for p in self.file_paths:
            if self._stopped:
                break
            done += 1
            base_name = os.path.basename(p)
            self.progress.emit(f"准备上传 {base_name}", done - 1, total)
            if not os.path.exists(p):
                failed_cnt += 1
                self.progress.emit(f"跳过（不存在）{base_name}", done, total)
                continue

            # 前置查重
            md5_hex = self._compute_md5(p)
            if md5_hex:
                du = self.api_client.files_dedup_md5(md5_hex, 5)
                if isinstance(du, dict) and du.get('exists') is True:
                    skipped_cnt += 1
                    self.progress.emit(f"已存在，跳过 {base_name}", done, total)
                    continue

            # 上传
            if self.is_public:
                resp = self.api_client.public_upload_multipart(dir_path="/用户上传", local_path=p, filename=base_name, md5=md5_hex)
            else:
                remote_path = (self.user_dir.rstrip('/') + '/' + base_name) if self.user_dir != '/' else '/' + base_name
                resp = self.api_client.upload_local_file(p, remote_path)

            ok = isinstance(resp, dict) and resp.get('status') == 'ok'
            try:
                inner = (resp or {}).get('data') if isinstance(resp, dict) else None
                if inner and isinstance(inner, dict) and str(inner.get('status') or 'ok').lower() == 'error':
                    ok = False
            except Exception:
                pass

            if ok:
                success_cnt += 1
                self.progress.emit(f"上传成功 {base_name}", done, total)
            else:
                failed_cnt += 1
                self.progress.emit(f"上传失败 {base_name}", done, total)

        self.finished.emit(success_cnt, failed_cnt, skipped_cnt)


