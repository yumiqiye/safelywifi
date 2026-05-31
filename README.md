# Wi-Fi 认证系统 (适配华为路由器)

这是一个基于 Python Flask 的 Portal 认证系统，支持用户输入账号密码登录，管理员后台手动审核通过后，调用华为路由器 API 放行用户上网。

## 功能特点
- **用户登录页**：美观的响应式登录界面，自动获取用户 MAC/IP。
- **自动/手动策略**：
  - 管理员账号 (`admin`/`admin123`) 登录自动放行。
  - 普通用户登录后进入“待审核”状态。
- **管理后台**：
  - 地址：`/admin` (账号: `superadmin` / 密码: `root`)
  - 可查看申请列表，手动点击“通过”或“拒绝”。
  - “通过”后自动调用华为设备接口放行。
- **跨平台**：适用于 Windows 和 Linux。

## 目录结构
```
/workspace
├── app.py              # 主程序
├── templates/
│   ├── login.html      # 用户登录页
│   └── admin.html      # 管理后台页
├── requirements.txt    # 依赖包
└── README.md           # 说明文档
```

## 安装步骤

### 1. 安装依赖
确保已安装 Python 3。
```bash
pip install flask
# 如果需要调用真实的华为 API，还需安装 requests
# pip install requests
```

### 2. 运行程序
```bash
python app.py
```
默认监听端口 **8080**。
- 用户访问：`http://<服务器IP>:8080`
- 管理后台：`http://<服务器IP>:8080/admin`

### 3. 华为路由器配置 (关键步骤)
为了让用户连接 Wi-Fi 后自动跳转到此页面，需要在华为路由器/AC 上配置 **Portal 认证** 或 **重定向规则**。

#### 方案 A：使用华为 AC/网关的内置 Portal 服务器 (推荐)
如果华为设备支持自定义 Portal 页面，将 `login.html` 的内容上传至设备，并配置认证模板指向本系统的 API 接口（需二次开发对接设备内部逻辑）。

#### 方案 B：旁挂式认证 (本代码适用场景)
1. **防火墙/流控策略**：默认阻断所有 Wi-Fi 客户端的互联网访问，但放行对本认证服务器 (8080 端口) 的访问。
2. **DNS 劫持/重定向**：配置路由器将所有 HTTP 请求 (80 端口) 重定向到 `http://<服务器IP>:8080`。
   - *注：部分华为设备支持 `redirect` 命令或 ACL 重定向。*
3. **联动放行**：
   - 当管理员在后台点击“通过”时，代码中的 `authorize_user_huawei` 函数会被触发。
   - **你需要在此处填入真实的华为 API 调用代码**。
   - 常见方式：
     - **SNMP**: 修改交换机 ACL。
     - **REST API**: 华为 NCE-Campus 或 AR 路由器网管接口。
     - **SSH/Telnet**: 脚本登录设备执行命令行 (如 `acl permit mac xxxx`)。

## 代码定制指南
打开 `app.py`，找到 `authorize_user_huawei` 函数：

```python
def authorize_user_huawei(mac_address, ip_address):
    # TODO: 替换为真实的华为设备 API 调用
    # 示例 (伪代码):
    # import requests
    # url = "https://192.168.1.1:8443/api/v1/users/allow"
    # data = {"mac": mac_address}
    # requests.post(url, json=data, auth=('admin', 'password'))
    print(f"放行用户: {mac_address}")
    return True
```

## 安全提示
1. 生产环境请务必修改默认的管理员密码 (`superadmin`/`root`) 和测试账号 (`admin`/`admin123`)。
2. 建议将内存数据库 (`users_db`) 替换为 SQLite 或 MySQL 以持久化数据。
3. 部署在 Linux 上如需使用 80 端口，请使用 `sudo` 或通过 Nginx 反向代理。
