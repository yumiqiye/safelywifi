# Wi-Fi 认证程序 (无需 API 版本)

一个适用于 Windows/Linux 的轻量级 Wi-Fi 认证系统，专为华为路由器环境设计。**不需要路由器 API**，采用"手动放行"模式。

## 📖 项目说明

本程序提供一个 Web 认证页面，用户输入账号密码登录后进入"待审核"状态。管理员在后台审核通过后，**手动将用户的 MAC 地址添加到华为路由器的白名单中**，用户即可访问互联网。

### 工作流程
1. 用户连接 Wi-Fi，打开浏览器自动跳转到认证页
2. 用户输入账号密码提交
3. 系统记录用户信息（账号、密码、MAC、IP），状态设为"待审核"
4. 管理员登录后台 `/admin`，查看待审核用户
5. 管理员点击"通过"，系统提示需要手动操作
6. **管理员登录华为路由器，将用户的 MAC 地址加入白名单/允许列表**
7. 用户刷新页面，显示认证成功，可以上网

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行程序
```bash
python app.py
```

服务启动后：
- **用户登录页**: `http://<服务器IP>:8080`
- **管理后台**: `http://<服务器IP>:8080/admin`

### 默认账号

#### 超级管理员（审核后台）
- 账号：`superadmin`
- 密码：`root`

#### 测试用户（已自动通过）
- 账号：`admin`
- 密码：`admin123`

## 📁 文件结构
```
/workspace
├── app.py                 # 主程序 (Flask 后端)
├── templates/             # HTML 模板
│   ├── login.html         # 用户登录页
│   ├── status.html        # 等待审核页
│   ├── success.html       # 认证成功页
│   ├── admin_login.html   # 管理员登录页
│   └── admin_dashboard.html # 管理后台
├── users.db               # SQLite 数据库 (自动生成)
├── requirements.txt       # Python 依赖
└── README.md              # 本文件
```

## ⚙️ 华为路由器配置指南

由于没有 API，需要在华为路由器上**手动配置 MAC 地址白名单**。以下是常见型号的配置方法：

### 方法一：Web 界面配置 (推荐)
1. 登录华为路由器 Web 管理界面 (通常 `192.168.3.1` 或 `192.168.1.1`)
2. 找到 "Wi-Fi 设置" / "无线设置" / "访客网络" / "MAC 过滤"
3. 添加允许的设备 MAC 地址
4. 保存配置

### 方法二：命令行配置 (SSH)
```bash
# 登录路由器 SSH
ssh admin@192.168.3.1

# 进入系统视图
system-view

# 添加 MAC 地址到白名单 (示例，具体命令因型号而异)
wlan mac-filter permit xx:xx:xx:xx:xx:xx

# 或使用 ACL
acl number 4000
 rule 5 permit source-mac xxxx-xxxx-xxxx
```

### 方法三：导出 CSV 批量导入
1. 在管理后台点击 "导出白名单 CSV"
2. 登录华为 AC/NCE 控制器
3. 批量导入 MAC 地址白名单

## 🔧 高级配置

### 修改端口
编辑 `app.py`，修改最后一行：
```python
app.run(host='0.0.0.0', port=8080, debug=True)
```

### 生产环境部署
建议使用 Gunicorn 或 uWSGI：
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

### 配合 Captive Portal
如果使用华为路由器的强制门户 (Captive Portal) 功能：
1. 在路由器上配置认证 URL 为 `http://<服务器IP>:8080`
2. 配置重定向规则，未认证用户强制跳转到认证页
3. 认证成功后，路由器根据 MAC 白名单放行

## 📝 注意事项

1. **MAC 地址获取**: 由于浏览器安全限制，网页无法直接获取客户端真实 MAC 地址。实际部署时，需要通过以下方式之一获取：
   - 华为路由器在重定向时注入 MAC 地址参数
   - 从路由器日志/ARP 表中查询
   - 使用 DHCP Snooping 功能

2. **安全性**: 
   - 生产环境请修改 `app.secret_key`
   - 建议启用 HTTPS
   - 密码目前为明文存储，生产环境请使用哈希加密

3. **数据库**: 当前使用 SQLite，高并发场景建议改用 MySQL/PostgreSQL

## 🆘 常见问题

**Q: 用户登录后为什么还不能上网？**
A: 本程序仅负责认证和记录，需要管理员手动在华为路由器上将用户 MAC 加入白名单后才能上网。

**Q: 如何获取用户的真实 MAC 地址？**
A: 查看华为路由器的 ARP 表或 DHCP 租约列表，根据 IP 地址对应查找 MAC 地址。

**Q: 支持哪些华为设备？**
A: 所有支持 MAC 地址白名单功能的华为路由器/AC 控制器均可，包括 AR 系列、AC6005、NCE-Campus 等。

## 📄 License

MIT License
