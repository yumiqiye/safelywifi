import os
import socket
import threading
from flask import Flask, request, render_template, redirect, url_for, jsonify
from datetime import datetime

app = Flask(__name__)

# --- 配置区域 ---
# 华为路由器/控制器 API 配置 (需要根据实际型号修改，如 NCE-Campus 或 AC6005)
HUAWEI_CONTROLLER_URL = "https://192.168.1.1:8443" 
HUAWEI_API_TOKEN = "your_api_token_here"

# 内存数据库 (生产环境请替换为 SQLite/MySQL)
# 状态: 'pending' (待审核), 'approved' (已通过), 'rejected' (拒绝)
users_db = {} 

# --- 辅助函数：获取用户 MAC 地址 ---
def get_user_mac():
    """
    尝试从 HTTP 头或 ARP 表中获取用户 MAC。
    注意：在真实环境中，通常需要路由器在重定向时通过 URL 参数传递 MAC (如 ?mac=xx:xx:xx)。
    这里做模拟处理。
    """
    # 模拟：如果路由器配置了 URL 重定向带参数，从这里取
    mac = request.args.get('mac', 'unknown-mac')
    if mac == 'unknown-mac':
        # 仅作为演示，真实环境很难直接从HTTP获取MAC，需依靠路由器透传
        mac = f"MAC-{socket.gethostbyname(socket.gethostname())}" 
    return mac

# --- 辅助函数：调用华为路由器 API ---
def authorize_user_huawei(mac_address, ip_address):
    """
    调用华为路由器 API 将用户加入白名单。
    此处为伪代码，需根据具体华为设备型号 (AC/AP/网关) 的 API 文档实现。
    """
    print(f"[System] 正在向华为设备发送授权指令: MAC={mac_address}, IP={ip_address}")
    
    # 示例：如果是华为 NCE-Campus，通常发送 REST API 请求
    # payload = {"mac": mac_address, "action": "allow"}
    # requests.post(f"{HUAWEI_CONTROLLER_URL}/api/v1/users/authorize", json=payload, headers=...)
    
    # 模拟成功
    return True

# --- 路由：用户登录页 ---
@app.route('/')
def login_page():
    user_mac = get_user_mac()
    user_ip = request.remote_addr
    return render_template('login.html', mac=user_mac, ip=user_ip)

# --- 路由：处理登录提交 ---
@app.route('/login', methods=['POST'])
def login_submit():
    username = request.form.get('username')
    password = request.form.get('password')
    user_mac = get_user_mac()
    user_ip = request.remote_addr
    
    # 简单验证逻辑
    if not username or not password:
        return redirect(url_for('login_page', error="请输入账号密码"))

    # 策略判断：
    # 1. 如果是特定管理员账号，直接通过
    # 2. 否则，进入待审核状态 (pending)，等待后台手动通过
    
    if username == "admin" and password == "admin123":
        # 自动通过
        authorize_user_huawei(user_mac, user_ip)
        return render_template('login.html', success="管理员登录成功，已放行！", mac=user_mac)
    
    # 普通用户：存入数据库，状态为 pending
    users_db[username] = {
        "password": password,
        "mac": user_mac,
        "ip": user_ip,
        "status": "pending",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return render_template('login.html', message="您的申请已提交，请等待管理员审核。", mac=user_mac)

# --- 路由：管理后台 ---
@app.route('/admin')
def admin_panel():
    # 简单的硬编码密码保护
    auth = request.authorization
    if not auth or not (auth.username == "superadmin" and auth.password == "root"):
        return redirect(url_for('login_page')) # 或者返回 401
        
    return render_template('admin.html', users=users_db)

# --- 路由：管理员手动通过 ---
@app.route('/approve/<username>', methods=['POST'])
def approve_user(username):
    if username in users_db:
        users_db[username]['status'] = 'approved'
        # 调用华为设备接口放行
        authorize_user_huawei(users_db[username]['mac'], users_db[username]['ip'])
        return jsonify({"success": True, "message": f"用户 {username} 已放行"})
    return jsonify({"success": False, "message": "用户不存在"})

# --- 路由：管理员拒绝 ---
@app.route('/reject/<username>', methods=['POST'])
def reject_user(username):
    if username in users_db:
        users_db[username]['status'] = 'rejected'
        return jsonify({"success": True, "message": f"用户 {username} 已拒绝"})
    return jsonify({"success": False, "message": "用户不存在"})

if __name__ == '__main__':
    # 监听所有网卡，端口 80 (Linux可能需要sudo) 或 8080
    port = int(os.environ.get("PORT", 8080))
    print(f"启动认证服务器，监听端口 {port}...")
    print(f"管理后台地址: http://localhost:{port}/admin (账号: superadmin / root)")
    app.run(host='0.0.0.0', port=port, debug=True)
