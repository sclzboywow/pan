#!/usr/bin/env python3
"""
手动压缩exe文件的脚本
在PyInstaller打包完成后，使用7-Zip或其他工具压缩exe文件
"""

import os
import sys
import subprocess
from pathlib import Path

def compress_exe():
    """压缩生成的exe文件"""
    exe_path = Path("dist") / "云栈客户端.exe"
    
    if not exe_path.exists():
        print("错误: 未找到exe文件，请先运行打包脚本")
        return
    
    print(f"找到exe文件: {exe_path}")
    print(f"原始大小: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    # 尝试使用7-Zip压缩
    seven_zip_paths = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        "7z.exe"  # 如果在PATH中
    ]
    
    seven_zip = None
    for path in seven_zip_paths:
        if shutil.which(path) or Path(path).exists():
            seven_zip = path
            break
    
    if seven_zip:
        print("使用7-Zip压缩...")
        try:
            # 创建压缩包
            archive_path = exe_path.with_suffix('.7z')
            cmd = [seven_zip, 'a', '-mx9', str(archive_path), str(exe_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✓ 压缩完成: {archive_path}")
                print(f"压缩后大小: {archive_path.stat().st_size / 1024 / 1024:.1f} MB")
                compression_ratio = (1 - archive_path.stat().st_size / exe_path.stat().st_size) * 100
                print(f"压缩率: {compression_ratio:.1f}%")
            else:
                print(f"✗ 7-Zip压缩失败: {result.stderr}")
        except Exception as e:
            print(f"✗ 7-Zip压缩异常: {e}")
    else:
        print("未找到7-Zip，请手动压缩exe文件")
        print("建议:")
        print("1. 安装7-Zip: https://www.7-zip.org/")
        print("2. 或使用WinRAR、Bandizip等压缩工具")
        print("3. 或使用在线压缩服务")

if __name__ == "__main__":
    import shutil
    compress_exe()
