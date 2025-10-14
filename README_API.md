# 云栈客户端 - 后端API集成版

## 功能特性

### 🔐 用户认证
- **用户注册/登录**: 支持用户名密码注册和登录
- **百度网盘授权**: 通过二维码扫码完成百度网盘授权
- **JWT认证**: 使用JWT token进行API认证

### 📁 文件管理
- **文件列表**: 获取百度网盘文件列表
- **文件搜索**: 支持文件名搜索和语义搜索
- **文件上传**: 支持本地文件上传到百度网盘
- **文件操作**: 创建文件夹、删除、移动、重命名、复制文件

### 🔍 高级功能
- **分类浏览**: 按图片、文档、视频等分类浏览
- **分享功能**: 创建文件分享链接
- **离线下载**: 支持URL离线下载到百度网盘

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

### 后端API地址
默认后端API地址为 `http://118.24.67.10`，可以在 `core/api_client.py` 中修改：

```python
def __init__(self, base_url: str = "http://118.24.67.10"):
```

### 支持的API端点

#### 认证相关
- `POST /auth/login` - 用户登录
- `POST /auth/register` - 用户注册
- `GET /auth/me` - 获取用户信息

#### OAuth授权
- `POST /oauth/device/start` - 启动扫码授权
- `POST /oauth/device/poll` - 轮询授权状态

#### 百度网盘API代理
- `POST /mcp/user/exec` - 用户API调用（需要认证）
- `POST /mcp/public/exec` - 公共API调用（无需认证）

## 使用方法

### 1. 启动应用
```bash
python main.py
```

### 2. 用户登录
1. 点击"我的信息"按钮
2. 在登录对话框中输入用户名和密码
3. 点击"登录"按钮

### 3. 百度网盘授权
1. 登录成功后，切换到"百度网盘授权"标签页
2. 点击"开始扫码授权"按钮
3. 使用百度网盘APP扫描二维码
4. 等待授权完成

### 4. 文件管理
- **浏览文件**: 登录授权后自动加载文件列表
- **搜索文件**: 在搜索框输入关键词进行搜索
- **上传文件**: 点击"上传文档"按钮选择文件上传
- **文件操作**: 右键点击文件进行各种操作

## API客户端使用示例

```python
from pan_client.core.api_client import APIClient

# 创建API客户端
api_client = APIClient("http://118.24.67.10")

# 用户登录
success = api_client.login("username", "password")
if success:
    print("登录成功")
    
    # 获取文件列表
    result = api_client.list_files("/", 100)
    if result and result.get("status") == "ok":
        files = result.get("data", {}).get("list", [])
        print(f"找到 {len(files)} 个文件")
    
    # 搜索文件
    result = api_client.search_filename("关键词", "/")
    if result and result.get("status") == "ok":
        files = result.get("data", {}).get("list", [])
        print(f"搜索到 {len(files)} 个匹配文件")
    
    # 上传文件
    result = api_client.upload_local_file("/path/to/local/file.txt", "/remote/path/")
    if result and result.get("status") == "ok":
        print("上传成功")
```

## 支持的操作

### 基础操作
- `quota` - 获取配额信息
- `list_files` - 获取文件列表
- `list_images` - 获取图片列表
- `list_docs` - 获取文档列表
- `list_videos` - 获取视频列表

### 文件管理
- `mkdir` - 创建文件夹
- `delete` - 删除文件
- `move` - 移动文件
- `rename` - 重命名文件
- `copy` - 复制文件

### 上传功能
- `upload_local` - 上传本地文件
- `upload_url` - 上传URL文件
- `upload_text` - 上传文本内容
- `upload_batch_local` - 批量上传本地文件
- `upload_batch_url` - 批量上传URL文件
- `upload_batch_text` - 批量上传文本内容

### 搜索功能
- `search_filename` - 按文件名搜索
- `search_semantic` - 语义搜索

### 分享功能
- `share_create` - 创建分享链接

### 离线下载
- `offline_add` - 添加离线下载任务
- `offline_status` - 查询任务状态
- `offline_cancel` - 取消任务

## 错误处理

所有API调用都包含完整的错误处理：
- 网络连接错误
- 认证失败
- API调用失败
- 数据解析错误

错误信息会通过信号机制传递给UI层，用户可以看到具体的错误提示。

## 开发说明

### 项目结构
```
pan_client/
├── core/
│   ├── api_client.py      # API客户端
│   └── utils.py           # 工具函数
├── ui/
│   ├── dialogs/
│   │   ├── login_dialog.py    # 登录对话框
│   │   └── user_info_dialog.py # 用户信息对话框
│   ├── threads/
│   │   └── auth_thread.py     # 授权轮询线程
│   ├── widgets/
│   │   └── qr_code_widget.py  # 二维码组件
│   └── modern_pan.py          # 主界面
├── main.py                 # 程序入口
└── requirements.txt        # 依赖列表
```

### 信号机制
API客户端使用Qt信号机制进行异步通信：
- `login_success` - 登录成功
- `login_failed` - 登录失败
- `auth_success` - 授权成功
- `auth_failed` - 授权失败
- `api_error` - API错误

### 线程安全
所有网络请求都在主线程中执行，避免阻塞UI。授权轮询使用单独的线程进行。

## 注意事项

1. **网络连接**: 确保能够访问后端API服务器
2. **百度网盘授权**: 需要有效的百度网盘账号
3. **文件大小限制**: 上传文件大小受百度网盘限制
4. **并发限制**: 避免同时进行多个上传/下载操作

## 故障排除

### 登录失败
- 检查用户名和密码是否正确
- 确认网络连接正常
- 检查后端API服务是否运行

### 授权失败
- 确保百度网盘APP已安装
- 检查二维码是否过期
- 确认百度网盘账号状态正常

### 文件操作失败
- 确认已成功完成授权
- 检查文件权限
- 确认文件路径正确

## 更新日志

### v1.0.0
- 集成后端API
- 实现用户认证和授权
- 支持文件管理和搜索
- 添加上传和分享功能
