#!/usr/bin/env python3
"""
Windows 打包脚本 - 使用 PyInstaller 打包为 exe
用法: python scripts/build_windows.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_cmd(cmd, check=True):
    """运行命令并检查结果"""
    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        print(f"命令失败，退出码: {result.returncode}")
        sys.exit(1)
    return result

def main():
    print("[1/5] 检查 Python...")
    run_cmd([sys.executable, "--version"])
    
    print("[2/5] 检查 PyInstaller...")
    try:
        import PyInstaller
        print("PyInstaller 已安装")
    except ImportError:
        print("PyInstaller 未安装，尝试安装...")
        # 尝试多种安装方式
        install_commands = [
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "pyinstaller", "--no-proxy"],
            [sys.executable, "-m", "pip", "install", "pyinstaller", "--trusted-host", "pypi.org", "--trusted-host", "pypi.python.org", "--trusted-host", "files.pythonhosted.org"],
            [sys.executable, "-m", "pip", "install", "pyinstaller", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple/"]
        ]
        
        success = False
        for cmd in install_commands:
            try:
                print(f"尝试: {' '.join(cmd)}")
                run_cmd(cmd, check=False)
                # 验证安装
                try:
                    import PyInstaller
                    print("PyInstaller 安装成功")
                    success = True
                    break
                except ImportError:
                    continue
            except:
                continue
        
        if not success:
            print("自动安装失败，请手动安装 PyInstaller:")
            print("pip install pyinstaller")
            print("或使用国内镜像: pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple/")
            sys.exit(1)
    
    if Path("requirements.txt").exists():
        print("[2b] 安装项目依赖...")
        try:
            run_cmd([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--no-proxy"])
        except:
            print("项目依赖安装失败，继续打包...")
    
    print("[3/5] 准备 PyInstaller 参数...")
    
    # 基础参数
    args = [
        "--clean",
        "--noconfirm", 
        "--name", "云栈客户端",
        "--onefile",
        "--strip",
        "--optimize", "2",
        "--noconsole"
    ]
    
    # 图标
    icon_path = "resources/icons/logo.ico"
    if Path(icon_path).exists():
        args.extend(["--icon", icon_path])
    else:
        print(f"警告: 图标文件 {icon_path} 不存在，继续打包...")
    
    # 资源文件夹
    if Path("resources").exists():
        args.extend(["--add-data", "resources;resources"])
    
    # 隐藏导入
    hidden_imports = [
        "PySide6.QtCore",
        "PySide6.QtGui", 
        "PySide6.QtWidgets",
        "PySide6.QtNetwork"
    ]
    for mod in hidden_imports:
        args.extend(["--hidden-import", mod])
    
    # 排除模块
    excludes = [
        "pytest", "pip", "pkg_resources", "setuptools", "tkinter",
        "matplotlib", "pandas", "numpy", "scipy", "IPython", 
        "notebook", "jupyter", "test", "tests"
    ]
    for mod in excludes:
        args.extend(["--exclude-module", mod])
    
    # 手动清理敏感文件（PyInstaller 不支持文件排除）
    print("[3b] 清理敏感文件...")
    sensitive_files = [
        "tokens.json", "*.log", "*.db", "*.sqlite*", 
        "user_data", "cache", "logs", ".git", ".vscode", ".idea"
    ]
    
    for pattern in sensitive_files:
        for file in Path(".").rglob(pattern):
            try:
                if file.is_file():
                    file.unlink()
                    print(f"已删除: {file}")
                elif file.is_dir():
                    import shutil
                    shutil.rmtree(file)
                    print(f"已删除目录: {file}")
            except Exception as e:
                print(f"无法删除 {file}: {e}")
    
    # UPX 压缩（如果可用）
    upx_path = shutil.which("upx")
    if upx_path:
        upx_dir = str(Path(upx_path).parent)
        args.extend(["--upx-dir", upx_dir])
        print(f"使用 UPX 压缩: {upx_dir}")
    else:
        print("UPX 未找到，跳过压缩")
        print("提示: 如需压缩，可手动下载UPX并添加到系统PATH")
        print("下载地址: https://github.com/upx/upx/releases")
        print("或使用其他压缩工具如7-Zip压缩最终exe文件")
    
    # 入口文件
    args.append("main.py")
    
    print("[4/5] 运行 PyInstaller...")
    run_cmd([sys.executable, "-m", "PyInstaller"] + args)
    
    print("[5/5] 清理临时文件...")
    # 清理构建目录中的敏感文件
    build_dir = Path("build")
    if build_dir.exists():
        sensitive_files = ["tokens.json", "*.log", "*.db", "*.sqlite*"]
        for pattern in sensitive_files:
            for file in build_dir.rglob(pattern):
                try:
                    file.unlink()
                    print(f"已删除敏感文件: {file}")
                except:
                    pass
    
    print("打包完成!")
    exe_path = Path("dist") / "云栈客户端.exe"
    if exe_path.exists():
        print(f"可执行文件: {exe_path.absolute()}")
        print(f"文件大小: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
        print("注意: 已排除敏感文件，首次运行需要重新登录")
    else:
        print("错误: 未找到生成的可执行文件")

if __name__ == "__main__":
    main()
