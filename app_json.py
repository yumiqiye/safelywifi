from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import json
import os
import datetime
import csv
import io

app = Flask(__name__)
app.secret_key = 'wifi_auth_secret_key_change_this_in_prod'

# JSON 数据存储配置
JSON_PATH = 'users.json'

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
            break
    save_users(users)
    
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
            break
    save_users(users)
    
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
