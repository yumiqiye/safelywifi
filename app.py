from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
import datetime
import csv
import io

app = Flask(__name__)
app.secret_key = 'wifi_auth_secret_key_change_this_in_prod'

# 数据库配置
DB_PATH = 'users.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 用户表：账号，密码，MAC地址，IP地址，状态(pending/approved/rejected)，申请时间
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  mac_address TEXT,
                  ip_address TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # 创建默认管理员 (superadmin / root)
    try:
        c.execute("INSERT INTO users (username, password, status) VALUES (?, ?, ?)", 
                  ('superadmin', 'root', 'approved'))
        # 创建普通测试账号 (admin / admin123) - 模拟自动通过
        c.execute("INSERT INTO users (username, password, status) VALUES (?, ?, ?)", 
                  ('admin', 'admin123', 'approved'))
    except sqlite3.IntegrityError:
        pass # 已存在
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()

    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        # 更新 IP 和 MAC (如果之前没有)
        if user['mac_address'] == 'Unknown' or not user['mac_address']:
             conn.execute('UPDATE users SET mac_address = ?, ip_address = ? WHERE id = ?', 
                         (user_mac, user_ip, user['id']))
             conn.commit()

        conn.close()
        
        if user['status'] == 'approved':
            return redirect(url_for('success'))
        else:
            return redirect(url_for('status'))
    else:
        # 尝试注册/申请逻辑：如果用户不存在，自动创建为 pending 状态
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO users (username, password, mac_address, ip_address, status) VALUES (?, ?, ?, ?, ?)',
                         (username, password, user_mac, user_ip, 'pending'))
            conn.commit()
            conn.close()
            session['username'] = username
            # 这里简化处理，新注册用户直接跳转到等待页
            return redirect(url_for('status'))
        except sqlite3.IntegrityError:
            flash('账号或密码错误，且无法自动注册（可能账号已存在但密码不同）')
            return redirect(url_for('login'))

@app.route('/status')
def status():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
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
    
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
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
    
    conn = get_db_connection()
    conn.execute('UPDATE users SET status = ? WHERE id = ?', ('approved', user_id))
    conn.commit()
    conn.close()
    flash('用户已批准！请在路由器上将对应 MAC 地址加入白名单。')
    return redirect(url_for('admin'))

@app.route('/admin/reject/<int:user_id>')
def reject_user(user_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    conn = get_db_connection()
    conn.execute('UPDATE users SET status = ? WHERE id = ?', ('rejected', user_id))
    conn.commit()
    conn.close()
    flash('用户已拒绝')
    return redirect(url_for('admin'))

@app.route('/admin/export')
def export_csv():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    conn = get_db_connection()
    users = conn.execute("SELECT username, mac_address, ip_address, status, created_at FROM users WHERE status = 'approved'").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Username', 'MAC Address', 'IP Address', 'Status', 'Approved Time'])
    
    for user in users:
        writer.writerow([user['username'], user['mac_address'], user['ip_address'], user['status'], user['created_at']])
    
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
    init_db()
    # host='0.0.0.0' 允许局域网访问
    app.run(host='0.0.0.0', port=8080, debug=True)
