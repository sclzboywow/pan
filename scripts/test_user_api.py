#!/usr/bin/env python3
"""
用户态后端联调脚本（减少前端试错）

功能：
- 列目录：验证 list_files 返回结构与 isdir/path 等字段
- 取直链：多策略（fsid/path/批量）获取 dlink 并用requests验证可达性（禁用代理、设置UA/Referer）
- 删除并轮询：调用删除接口后轮询当前目录，直到目标消失或超时

使用示例（在项目根目录）：
  python scripts/test_user_api.py list --dir "/"
  python scripts/test_user_api.py dlink --dir "/" --name "文件名.docx"
  python scripts/test_user_api.py delete --dir "/" --name "文件名.docx" --wait 10

注意：APIClient 会读取本地已保存的登录态（jwt/refresh）。请确保先在前端完成一次登录。
"""

import os
import sys
import time
import json
import argparse
from typing import Optional, Dict, Any

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from core.api_client import APIClient


def list_dir(api: APIClient, dir_path: str = "/") -> list:
    result = api.list_files(dir_path, 1000)
    if isinstance(result, dict):
        data = result.get("data") if isinstance(result.get("data"), dict) else result
        files = (data or {}).get("list") or (data or {}).get("files") or (data or {}).get("items") or []
    else:
        files = result or []
    print(json.dumps({
        "dir": dir_path,
        "count": len(files),
        "sample": files[:3]
    }, ensure_ascii=False, indent=2))
    return files


def find_file(files: list, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not name:
        return files[0] if files else None
    for f in files:
        n = f.get('server_filename') or f.get('file_name') or f.get('name')
        if n == name:
            return f
    return None


def resolve_dlink(api: APIClient, file_info: Dict[str, Any], expires: int = 300) -> Optional[str]:
    fsid = file_info.get('fs_id') or file_info.get('fsid') or file_info.get('id')
    name = file_info.get('server_filename') or file_info.get('file_name') or file_info.get('name') or ''
    path_val = file_info.get('path') or file_info.get('server_path') or ''
    if not path_val and name:
        base = "/" if not file_info.get('path') else os.path.dirname(file_info['path'])
        if not base.endswith('/'):
            base += '/'
        path_val = base + name

    # 1) fsid
    if fsid:
        r = api.user_download_link(fsid=str(fsid), expires_hint=expires)
        d = (r or {}).get('data') or {}
        dlink = d.get('dlink') or (r or {}).get('dlink')
        if dlink:
            return dlink
        print(f"[DEBUG] fsid直链失败: {(d.get('errmsg') or d.get('error') or (r or {}).get('error'))}")

    # 2) path
    if path_val:
        r2 = api.user_download_link(path=path_val, expires_hint=expires)
        d2 = (r2 or {}).get('data') or {}
        dlink2 = d2.get('dlink') or (r2 or {}).get('dlink')
        if dlink2:
            return dlink2
        print(f"[DEBUG] path直链失败: {(d2.get('errmsg') or d2.get('error') or (r2 or {}).get('error'))}")

    # 3) 批量
    if fsid:
        r3 = api.user_download_links([fsid])
        d3 = (r3 or {}).get('data') or {}
        items = d3.get('list') or d3.get('items') or []
        if items:
            dlink3 = items[0].get('dlink') or items[0].get('url')
            if dlink3:
                return dlink3
        print(f"[DEBUG] 批量直链失败: {(d3.get('errmsg') or (r3 or {}).get('error'))}")

    return None


def check_dlink_reachable(dlink: str) -> bool:
    import requests
    headers = {
        "User-Agent": "netdisk;7.2.14;PC;PC-Windows;10.0.19045;WindowsBaiduYunGuanJia",
        "Referer": "https://pan.baidu.com/",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    proxies = {"http": None, "https": None}
    try:
        if 'HTTP_PROXY' in os.environ: del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ: del os.environ['HTTPS_PROXY']
    except Exception:
        pass
    r = requests.head(dlink, headers=headers, proxies=proxies, allow_redirects=True, timeout=10)
    print(f"[DEBUG] HEAD status: {r.status_code}")
    return r.status_code == 200


def delete_and_poll(api: APIClient, file_info: Dict[str, Any], dir_path: str, wait_seconds: int = 10) -> bool:
    fsid = file_info.get('fs_id') or file_info.get('fsid')
    name = file_info.get('server_filename') or file_info.get('file_name') or file_info.get('name')
    ret = api.delete_file(str(fsid))
    print("delete resp:", ret)
    deadline = time.time() + max(0, wait_seconds)
    while time.time() < deadline:
        time.sleep(1)
        files = list_dir(api, dir_path)
        still = find_file(files, name)
        if not still:
            print("[OK] 已从列表消失")
            return True
    print("[WARN] 超时，仍在列表中（后端可能异步/回收站）")
    return False


def main():
    parser = argparse.ArgumentParser(description="用户态API测试")
    sub = parser.add_subparsers(dest='cmd')

    p_list = sub.add_parser('list')
    p_list.add_argument('--dir', default='/', help='目录路径')

    p_dlink = sub.add_parser('dlink')
    p_dlink.add_argument('--dir', default='/', help='目录路径')
    p_dlink.add_argument('--name', required=False, help='文件名（不填取第一项）')

    p_dlink_fsid = sub.add_parser('dlink_fsid')
    p_dlink_fsid.add_argument('--fsid', required=True, help='目标文件fsid')
    p_dlink_fsid.add_argument('--expires', type=int, default=600, help='有效期提示秒数')

    # 新增：用户态签票
    p_ticket = sub.add_parser('ticket')
    p_ticket.add_argument('--fsid', required=True, help='目标文件fsid')
    p_ticket.add_argument('--ttl', type=int, default=300, help='票据有效期秒数')

    # 新增：代理下载触发（可直接给ticket，或给fsid自动签票）
    p_proxy = sub.add_parser('proxy')
    g = p_proxy.add_mutually_exclusive_group(required=True)
    g.add_argument('--fsid', help='目标文件fsid（自动签票）')
    g.add_argument('--ticket', help='已获取的ticket')
    p_proxy.add_argument('--ttl', type=int, default=300, help='当使用fsid时的签票有效期秒数')
    p_proxy.add_argument('--range', dest='range_header', default='bytes=0-', help='Range 头，默认 bytes=0-')

    p_del = sub.add_parser('delete')
    p_del.add_argument('--dir', default='/', help='目录路径')
    p_del.add_argument('--name', required=True, help='要删除的文件名')
    p_del.add_argument('--wait', type=int, default=10, help='删除后轮询秒数')

    args = parser.parse_args()

    api = APIClient()
    if not api.is_logged_in():
        print("[ERR] 未登录，请先在前端完成登录后再运行此脚本。")
        return 1

    if args.cmd == 'list':
        list_dir(api, args.dir)
        return 0

    if args.cmd == 'dlink':
        files = list_dir(api, args.dir)
        f = find_file(files, args.name)
        if not f:
            print("[ERR] 未找到目标文件")
            return 2
        dlink = resolve_dlink(api, f, expires=600)
        print("dlink:", dlink)
        if not dlink:
            print("[ERR] 获取直链失败")
            return 3
        ok = check_dlink_reachable(dlink)
        print("reachable:", ok)
        return 0 if ok else 4

    if args.cmd == 'dlink_fsid':
        r = api.user_download_link(fsid=str(args.fsid), expires_hint=int(args.expires))
        print("raw:", json.dumps(r, ensure_ascii=False))
        d = (r or {}).get('data') or {}
        dlink = d.get('dlink') or (r or {}).get('dlink')
        print("dlink:", dlink)
        if not dlink:
            return 3
        ok = check_dlink_reachable(dlink)
        print("reachable:", ok)
        return 0 if ok else 4

    if args.cmd == 'ticket':
        import datetime
        r = api.user_download_ticket(fsid=args.fsid, ttl=int(args.ttl))
        print("raw:", json.dumps(r, ensure_ascii=False))
        data = (r or {}).get('data') or {}
        ticket = data.get('ticket')
        print("ticket:", ticket)
        print("utc:", datetime.datetime.utcnow().isoformat())
        return 0 if ticket else 6

    if args.cmd == 'proxy':
        import datetime, requests
        # 准备ticket
        if args.fsid:
            rr = api.user_download_ticket(fsid=args.fsid, ttl=int(args.ttl))
            print("sign:", json.dumps(rr, ensure_ascii=False))
            data = (rr or {}).get('data') or {}
            ticket = data.get('ticket')
        else:
            ticket = args.ticket
        if not ticket:
            print("[ERR] 无法获得ticket")
            return 6
        base = api.base_url.rstrip('/')
        url = f"{base}/files/proxy_download?ticket={ticket}&range={args.range_header}"
        headers = {"Authorization": f"Bearer {api.user_jwt}", "User-Agent": "PanClient/1.0.0"}
        # 禁用系统代理
        proxies = {"http": None, "https": None}
        print("utc:", datetime.datetime.utcnow().isoformat())
        print("GET:", url)
        r = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=30, proxies=proxies)
        print("status:", r.status_code)
        try:
            print("json:", r.json())
        except Exception:
            pass
        print("resp_headers:", dict(r.headers))
        if r.ok:
            try:
                chunk = next(r.iter_content(chunk_size=1024))
                print("peek_len:", len(chunk))
            except Exception as e:
                print("peek_err:", str(e))
        return 0 if r.status_code < 500 else 7

    if args.cmd == 'delete':
        files = list_dir(api, args.dir)
        f = find_file(files, args.name)
        if not f:
            print("[ERR] 未找到目标文件")
            return 2
        ok = delete_and_poll(api, f, args.dir, args.wait)
        return 0 if ok else 5

    parser.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


