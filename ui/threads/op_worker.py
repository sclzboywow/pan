from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication
import time
import posixpath


class OperationWorker(QThread):
    op_started = Signal(str)                 # op_name
    op_progress = Signal(str, str)           # op_name, message
    op_completed = Signal(str, bool, str)    # op_name, success, message

    def __init__(self, api_client, op_name: str, args: dict, verify: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.op_name = op_name
        self.args = args or {}
        self.verify = verify or {}
        self._should_stop = False

    def stop(self):
        self._should_stop = True
        self.quit()
        self.wait(3000)

    def run(self):
        try:
            print(f"[DEBUG][OP] thread start op={self.op_name} args={self.args} verify={self.verify}")
        except Exception:
            pass
        self.op_started.emit(self.op_name)
        try:
            self.op_progress.emit(self.op_name, "正在提交请求...")
            ret = self._dispatch()

            # 判错与统一处理
            ok = False
            if isinstance(ret, dict):
                status_ok = ret.get('status') in ('ok', 'success')
                errno_ok = (ret.get('data') or {}).get('errno') in (0,)
                ok = status_ok or errno_ok

            if not ok:
                try:
                    err = self.api_client._handle_api_error(ret)
                except Exception:
                    err = str(ret)
                self.op_completed.emit(self.op_name, False, f"提交失败: {err}")
                return

            # 轮询验证是否落地
            self.op_progress.emit(self.op_name, "已提交，正在确认结果...")
            try:
                print(f"[DEBUG][OP] dispatch result: {ret}")
            except Exception:
                pass
            success, msg = self._poll_verify()
            self.op_completed.emit(self.op_name, success, msg)
        except Exception as e:
            self.op_completed.emit(self.op_name, False, f"异常: {str(e)}")

    def _dispatch(self):
        try:
            print(f"[DEBUG][OP] dispatch {self.op_name} with args={self.args}")
        except Exception:
            pass
        if self.op_name == 'mkdir':
            return self.api_client.create_folder(self.args['dir_path'], self.args['folder_name'])
        if self.op_name == 'rename':
            return self.api_client.rename_file(self.args['file_path'], self.args['new_name'])
        if self.op_name == 'move':
            return self.api_client.move_file(self.args['source_path'], self.args['target_dir'], self.args.get('new_name'))
        if self.op_name == 'copy':
            return self.api_client.copy_file(self.args['source_path'], self.args['target_dir'])
        return {'status': 'error', 'error': f'unsupported_op:{self.op_name}'}

    def _poll_verify(self, timeout_sec: float = 15.0, interval_sec: float = 0.5):
        """
        基于列表结果做简易验证：在 verify['current_dir'] 拉列表，判断 verify['expect_path'] 是否出现。
        """
        current_dir = self.verify.get('current_dir') or '/'
        expect_path = self.verify.get('expect_path') or ''

        if not expect_path:
            return False, "已提交（后台处理可能稍有延迟）"

        t0 = time.time()
        while time.time() - t0 < timeout_sec and not self._should_stop:
            try:
                lst = self.api_client.list_files(current_dir, limit=500)
                try:
                    print(f"[DEBUG][OP] verify list dir={current_dir} resp_head={(str(lst)[:200] if lst is not None else 'None')}")
                except Exception:
                    pass
                items = []
                if isinstance(lst, dict):
                    data = lst.get('data') or lst
                    items = data.get('list') or data.get('files') or data.get('items') or []
                elif isinstance(lst, list):
                    items = lst

                found = False
                expect_name = posixpath.basename(expect_path.rstrip('/'))
                for it in items:
                    cur_path = str(it.get('path') or '')
                    cur_name = str(it.get('server_filename') or it.get('filename') or it.get('name') or '')
                    if cur_path == expect_path or cur_name == expect_name:
                        found = True
                        break

                if found:
                    try:
                        print(f"[DEBUG][OP] verify success expect={expect_path}")
                    except Exception:
                        pass
                    return True, "操作成功"
                QApplication.processEvents()
                time.sleep(interval_sec)
            except Exception as e:
                try:
                    print(f"[DEBUG][OP] verify exception: {e}")
                except Exception:
                    pass
                # 标记为未落地，提示已提交（异常），避免误判为成功
                return False, "已提交(确认异常, 请稍后刷新查看)"
                return True, f"已提交（确认异常：{e}）"

        return False, "已提交（后台处理可能稍有延迟）"


