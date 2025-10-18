#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
删除操作异步工作线程
"""

import time
from PySide6.QtCore import QThread, Signal
from typing import Dict, Any, Optional


class DeleteWorker(QThread):
    """删除文件/目录的异步工作线程"""
    
    # 信号定义
    delete_started = Signal(str)  # 删除开始，参数：文件路径
    delete_completed = Signal(str, bool, str)  # 删除完成，参数：文件路径，是否成功，消息
    delete_progress = Signal(str, str)  # 删除进度，参数：文件路径，状态消息
    
    def __init__(self, api_client, file_path: str, fs_id: str, mode_token: int):
        super().__init__()
        self.api_client = api_client
        self.file_path = file_path
        self.fs_id = fs_id
        self.mode_token = mode_token
        self._should_stop = False
    
    def run(self):
        """执行删除操作"""
        try:
            self.delete_started.emit(self.file_path)
            self.delete_progress.emit(self.file_path, "正在删除...")
            
            # 调用删除API
            ret = self.api_client.delete_file(self.file_path)
            
            if isinstance(ret, dict) and (ret.get('status') in ('ok', 'success')):
                self.delete_progress.emit(self.file_path, "删除成功，正在确认...")
                
                # 异步轮询确认删除（最多约10秒）
                start_ts = time.time()
                disappeared = False
                
                while time.time() - start_ts < 10 and not self._should_stop:
                    try:
                        # 检查模式是否已切换
                        if hasattr(self.api_client, 'mode_token') and self.mode_token != self.api_client.mode_token:
                            self.delete_progress.emit(self.file_path, "模式已切换，停止轮询")
                            break
                        
                        # 获取当前文件列表
                        lst = self.api_client.list_files("/", limit=200)  # 从根目录搜索
                        items = []
                        if isinstance(lst, dict):
                            data = lst.get('data') or lst
                            items = data.get('list') or data.get('files') or data.get('items') or []
                        elif isinstance(lst, list):
                            items = lst
                        
                        # 检查文件是否还存在
                        present = False
                        for it in items:
                            cur = str(it.get('fs_id') or it.get('fsid') or '')
                            if cur and cur == str(self.fs_id):
                                present = True
                                break
                        
                        if not present:
                            disappeared = True
                            break
                        
                        self.delete_progress.emit(self.file_path, f"等待删除完成... ({int(time.time() - start_ts)}s)")
                        time.sleep(0.4)
                        
                    except Exception as e:
                        self.delete_progress.emit(self.file_path, f"轮询出错: {str(e)}")
                        break
                
                if disappeared:
                    self.delete_completed.emit(self.file_path, True, "删除成功")
                else:
                    self.delete_completed.emit(self.file_path, True, "已提交删除（后台处理可能稍有延迟）")
            else:
                # 删除失败
                err = ''
                try:
                    err = (ret or {}).get('error') or ((ret or {}).get('data') or {}).get('errmsg') or ''
                except:
                    pass
                error_msg = f"删除失败: {err}" if err else "删除失败"
                self.delete_completed.emit(self.file_path, False, error_msg)
                
        except Exception as e:
            self.delete_completed.emit(self.file_path, False, f"删除异常: {str(e)}")
    
    def stop(self):
        """停止删除操作"""
        self._should_stop = True
        self.quit()
        self.wait(3000)  # 等待最多3秒
