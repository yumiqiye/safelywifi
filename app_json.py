from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import json
import os
import datetime
import csv
import io
import subprocess
import re
import platform
import threading
import time

app = Flask(__name__)
app.secret_key = 'wifi_auth_secret_key_change_this_in_prod'

# JSON 数据存储配置
JSON_PATH = 'users.json'

# 系统配置
SYSTEM_OS = platform.system()
HOTSPOT_INTERFACE = None
HOTSPOT_SUBNET = "192.168.137."  # Windows 默认热点网段

def get_hotspot_interface():
    """获取热点网络接口名称"""
    if SYSTEM_OS == "Windows":
        try:
            # 获取所有网络接口
            result = subprocess.run(['netsh', 'interface', 'show', 'interface'], 
                                  capture_output=True, text=True, encoding='gbk')
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Local Area Connection' in line or '以太网' in line or 'WLAN' in line:
                    # 尝试找到热点接口（通常包含"Local Area Connection"或特定编号）
                    parts = line.split()
                    if len(parts) >= 4:
                        return parts[-1]  # 返回接口名称
            # 如果没找到，尝试常见名称
            return "Local Area Connection* 9"  # Windows 热点常见接口名
        except Exception as e:
            print(f"获取热点接口失败：{e}")
            return "Local Area Connection* 9"
    return None

def get_connected_devices():
    """获取连接到热点的设备列表 (MAC 地址和 IP)"""
    devices = []
    
    if SYSTEM_OS == "Windows":
        try:
            # 方法 1: 通过 ARP 表获取
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, encoding='gbk')
            lines = result.stdout.split('\n')
            
            current_ip = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 检查是否是接口行 (如 "Interface: 192.168.137.1")
                if "Interface:" in line:
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if match and match.group(1).startswith(HOTSPOT_SUBNET):
                        current_ip = match.group(1)
                    else:
                        current_ip = None
                    continue
                
                if current_ip:
                    # 解析 ARP 条目：IP 地址   MAC 地址     类型
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        mac = parts[1].replace('-', ':').upper()
                        
                        # 过滤掉自己的 IP 和广播地址
                        if ip != current_ip and not ip.endswith('.255') and not ip.endswith('.0'):
                            # 验证 MAC 地址格式
                            if re.match(r'^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$', mac, re.I):
                                devices.append({'ip': ip, 'mac': mac})
            
            # 方法 2: 也可以通过 netsh wlan show hostednetwork 获取（如果需要更详细信息）
            
        except Exception as e:
            print(f"获取连接设备失败：{e}")
    
    return devices

def add_firewall_block(mac_address):
    """添加防火墙规则阻止指定 MAC 地址访问外网"""
    if SYSTEM_OS == "Windows":
        try:
            # Windows 防火墙不直接支持 MAC 地址过滤，需要使用 netsh advfirewall
            # 替代方案：使用路由表或第三方工具
            # 这里使用一个变通方法：阻止该 IP 的所有出站流量
            
            # 首先获取该 MAC 对应的 IP
            devices = get_connected_devices()
            target_ip = None
            for device in devices:
                if device['mac'] == mac_address:
                    target_ip = device['ip']
                    break
            
            if target_ip:
                # 创建阻止规则
                rule_name = f"Block_MAC_{mac_address.replace(':', '')}"
                
                # 删除可能存在的旧规则
                subprocess.run(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 
                              f'name={rule_name}'], 
                             capture_output=True, text=True)
                
                # 添加新的阻止规则（阻止所有出站流量）
                result = subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                                       f'name={rule_name}',
                                       'dir=out',
                                       'action=block',
                                       f'remoteip={target_ip}',
                                       'enable=yes'],
                                      capture_output=True, text=True, encoding='gbk')
                
                if result.returncode == 0:
                    print(f"已阻止设备 {mac_address} ({target_ip})")
                    return True
                else:
                    print(f"阻止设备失败：{result.stderr}")
                    
        except Exception as e:
            print(f"添加防火墙规则失败：{e}")
    
    return False

def remove_firewall_block(mac_address):
    """移除防火墙阻止规则"""
    if SYSTEM_OS == "Windows":
        try:
            rule_name = f"Block_MAC_{mac_address.replace(':', '')}"
            
            # 删除规则
            result = subprocess.run(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 
                                   f'name={rule_name}'], 
                                  capture_output=True, text=True, encoding='gbk')
            
            if result.returncode == 0:
                print(f"已放行设备 {mac_address}")
                return True
            else:
                print(f"放行设备失败：{result.stderr}")
                
        except Exception as e:
            print(f"移除防火墙规则失败：{e}")
    
    return False

def sync_firewall_rules():
    """同步防火墙规则与数据库状态"""
    users = load_users()
    devices = get_connected_devices()
    
    # 获取所有已批准和已拒绝的 MAC 地址
    approved_macs = set()
    rejected_macs = set()
    
    for user in users:
        mac = user.get('mac_address', '').upper()
        if mac and mac != 'Unknown':
            if user.get('status') == 'approved':
                approved_macs.add(mac)
            elif user.get('status') == 'rejected':
                rejected_macs.add(mac)
    
    # 对当前连接的设备应用规则
    for device in devices:
        mac = device['mac'].upper()
        
        # 如果是拒绝状态，确保被阻止
        if mac in rejected_macs:
            add_firewall_block(mac)
        # 如果是批准状态，确保被放行
        elif mac in approved_macs:
            remove_firewall_block(mac)
        # 如果是待审核状态，阻止访问外网（但允许访问本机）
        elif any(u.get('mac_address', '').upper() == mac and u.get('status') == 'pending' for u in users):
            add_firewall_block(mac)

def firewall_monitor_thread():
    """后台线程：定期同步防火墙规则"""
    while True:
        try:
            sync_firewall_rules()
        except Exception as e:
            print(f"防火墙监控错误：{e}")
        time.sleep(5)  # 每 5 秒检查一次

def load_users():
    """从 JSON 文件加载用户数据"""
    if not os.path.exists(JSON_PATH):
        return []
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def save_users(users):
    """保存用户数据到 JSON 文件"""
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def init_data():
    """初始化数据"""
    users = load_users()
    
    # 检查是否存在默认管理员，不存在则创建
    admin_exists = any(u.get('username') == 'superadmin' for u in users)
    test_user_exists = any(u.get('username') == 'admin' for u in users)
    
    next_id = 1
    if users:
        next_id = max(u.get('id', 0) for u in users) + 1
    
    if not admin_exists:
        # 创建默认管理员 (superadmin / root)
        users.append({
            'id': next_id,
            'username': 'superadmin',
            'password': 'root',
            'mac_address': '',
            'ip_address': '',
            'status': 'approved',
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        next_id += 1
    
    if not test_user_exists:
        # 创建普通测试账号 (admin / admin123) - 模拟自动通过
        users.append({
            'id': next_id,
            'username': 'admin',
            'password': 'admin123',
            'mac_address': '',
            'ip_address': '',
            'status': 'approved',
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    save_users(users)
    
    # 启动防火墙监控线程
    monitor_thread = threading.Thread(target=firewall_monitor_thread, daemon=True)
    monitor_thread.start()
    print("防火墙监控线程已启动")
    
    return users

@app.route('/')
def login():
    if 'user_id' in session:
        return redirect(url_for('status'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form.get('username')
    password = request.form.get('password')
    # 获取客户端简易信息 (实际生产环境可能需要更复杂的获取方式)
    user_ip = request.remote_addr
    user_mac = request.form.get('mac', 'Unknown') 

    if not username or not password:
        flash('请输入账号和密码')
        return redirect(url_for('login'))

    users = load_users()
    user = None
    for u in users:
        if u.get('username') == username and u.get('password') == password:
            user = u
            break

    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        # 更新 IP 和 MAC (如果之前没有)
        if not user.get('mac_address') or user.get('mac_address') == 'Unknown':
            for u in users:
                if u['id'] == user['id']:
                    u['mac_address'] = user_mac
                    u['ip_address'] = user_ip
                    break
            save_users(users)

        if user.get('status') == 'approved':
            return redirect(url_for('success'))
        else:
            return redirect(url_for('status'))
    else:
        # 尝试注册/申请逻辑：如果用户不存在，自动创建为 pending 状态
        users = load_users()
        # 检查用户名是否已存在
        username_exists = any(u.get('username') == username for u in users)
        if username_exists:
            flash('账号或密码错误，且无法自动注册（可能账号已存在但密码不同）')
            return redirect(url_for('login'))
        
        next_id = 1
        if users:
            next_id = max(u.get('id', 0) for u in users) + 1
        
        new_user = {
            'id': next_id,
            'username': username,
            'password': password,
            'mac_address': user_mac,
            'ip_address': user_ip,
            'status': 'pending',
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        users.append(new_user)
        save_users(users)
        
        session['username'] = username
        session['user_id'] = next_id
        # 这里简化处理，新注册用户直接跳转到等待页
        return redirect(url_for('status'))

@app.route('/status')
def status():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    users = load_users()
    user = None
    for u in users:
        if u.get('id') == session['user_id']:
            user = u
            break
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    return render_template('status.html', user=user)

@app.route('/success')
def success():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('success.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 管理后台 ---

@app.route('/admin')
def admin():
    # 简单鉴权
    if 'admin_logged_in' not in session or not session['admin_logged_in']:
        return render_template('admin_login.html')
    
    users = load_users()
    return render_template('admin_dashboard.html', users=users)

@app.route('/admin/login', methods=['POST'])
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # 硬编码超级管理员，实际可放入数据库
    if username == 'superadmin' and password == 'root':
        session['admin_logged_in'] = True
        return redirect(url_for('admin'))
    else:
        flash('管理员账号或密码错误')
        return redirect(url_for('admin'))

@app.route('/admin/approve/<int:user_id>')
def approve_user(user_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    users = load_users()
    for u in users:
        if u.get('id') == user_id:
            u['status'] = 'approved'
            mac_address = u.get('mac_address', '')
            break
    save_users(users)
    
    # 自动放行：移除防火墙阻止规则
    if mac_address and mac_address != 'Unknown':
        remove_firewall_block(mac_address)
        flash(f'用户已批准！防火墙规则已更新，设备 {mac_address} 现在可以访问外网。')
    else:
        flash('用户已批准！请在路由器上将对应 MAC 地址加入白名单。')
    
    return redirect(url_for('admin'))

@app.route('/admin/reject/<int:user_id>')
def reject_user(user_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    users = load_users()
    for u in users:
        if u.get('id') == user_id:
            u['status'] = 'rejected'
            mac_address = u.get('mac_address', '')
            break
    save_users(users)
    
    # 自动拦截：添加防火墙阻止规则
    if mac_address and mac_address != 'Unknown':
        add_firewall_block(mac_address)
        flash(f'用户已拒绝！防火墙规则已更新，设备 {mac_address} 已被阻止访问外网。')
    else:
        flash('用户已拒绝')
    
    return redirect(url_for('admin'))

@app.route('/admin/export')
def export_csv():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    users = load_users()
    approved_users = [u for u in users if u.get('status') == 'approved']
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Username', 'MAC Address', 'IP Address', 'Status', 'Approved Time'])
    
    for user in approved_users:
        writer.writerow([
            user.get('username', ''), 
            user.get('mac_address', ''), 
            user.get('ip_address', ''), 
            user.get('status', ''), 
            user.get('created_at', '')
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'whitelist_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_data()
    # host='0.0.0.0' 允许局域网访问，debug=False 避免 reloader 导致端口占用
    app.run(host='0.0.0.0', port=8080, debug=False)
