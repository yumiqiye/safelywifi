import subprocess
import json
import os
import sys

# 配置区域
HOTSPOT_IP = "192.168.137.1"  # 你的电脑热点IP
HOTSPOT_SUBNET = "192.168.137.0/24" # 热点网段
SERVER_PORT = "8080"
RULE_NAME_BLOCK = "Hotspot_Block_All"
RULE_NAME_ALLOW = "Hotspot_Allow_Server"

def run_cmd(command):
    """以管理员权限运行命令并返回结果"""
    print(f"执行: {command}")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            encoding='gbk' # Windows 中文编码
        )
        if result.returncode == 0:
            print(f"✅ 成功: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ 失败: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
        return False

def check_admin():
    """检查是否以管理员运行"""
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

def main():
    print("="*30)
    print("🔍 热点防火墙拦截诊断工具")
    print("="*30)

    if not check_admin():
        print("\n⚠️  警告：当前未以管理员身份运行！")
        print("请务必右键点击终端，选择【以管理员身份运行】，否则无法修改防火墙。")
        print("按任意键继续尝试（可能会失败）...")
        input()

    # 1. 清理旧规则
    print("\n[1] 清理旧防火墙规则...")
    run_cmd(f'netsh advfirewall firewall delete rule name="{RULE_NAME_BLOCK}"')
    run_cmd(f'netsh advfirewall firewall delete rule name="{RULE_NAME_ALLOW}"')

    # 2. 创建拦截规则 (阻止访问外网，但允许DNS以便显示页面)
    # 注意：Windows 热点拦截通常需要指定方向为 out (出站)
    print(f"\n[2] 创建拦截规则：阻止 {HOTSPOT_SUBNET} 访问外网...")
    # 阻止所有出站流量
    cmd_block = (
        f'netsh advfirewall firewall add rule '
        f'name="{RULE_NAME_BLOCK}" '
        f'dir=out '
        f'action=block '
        f'remoteip={HOTSPOT_SUBNET} '
        f'enable=yes'
    )
    # 修正逻辑：上面的 remoteip 是指目标IP。
    # 我们要阻断的是：源IP是热点网段 的设备 访问 外部IP。
    # 但 netsh 简单规则很难指定源IP。
    # 替代方案：在接口级别或通过 Python 监控 ARP 后针对特定 IP 阻断。
    
    # 更有效的策略：针对特定客户端 IP 进行阻断 (模拟真实场景)
    # 这里我们假设有一个测试客户端 IP
    test_client_ip = "192.168.137.100" # 假设的手机IP
    
    print(f"\n[3] 模拟测试：阻断测试客户端 {test_client_ip} 访问外网...")
    
    # 规则 A: 阻止该 IP 访问任何远程 IP (除了本地)
    run_cmd(
        f'netsh advfirewall firewall add rule '
        f'name="Test_Block_{test_client_ip}" '
        f'dir=out '
        f'action=block '
        f'remoteip=any '
        f'localip={test_client_ip} '
        f'enable=yes'
    )

    # 规则 B: 允许该 IP 访问本机服务器 (用于认证)
    print(f"\n[4] 模拟测试：允许 {test_client_ip} 访问本机 {SERVER_PORT} 端口...")
    run_cmd(
        f'netsh advfirewall firewall add rule '
        f'name="Test_Allow_{test_client_ip}" '
        f'dir=out '
        f'action=allow '
        f'remoteip={HOTSPOT_IP} '
        f'localip={test_client_ip} '
        f'remoteport={SERVER_PORT} '
        f'protocol=tcp '
        f'enable=yes'
    )
    
    # 规则 C: 允许 DNS (否则网页都打不开，体验不好，可选)
    # 实际生产中可能需要更复杂的逻辑，这里先简化
    
    print("\n[5] 查看当前防火墙规则...")
    run_cmd(f'netsh advfirewall firewall show rule name=all | findstr "Test_"')

    print("\n" + "="*30)
    print("💡 结论:")
    print("1. 如果看到 '✅ 成功'，说明防火墙规则已写入。")
    print("2. 请找一台手机连接热点，手动设置静态 IP 为 192.168.137.100 测试。")
    print("3. 如果手机能上网，说明规则没生效（可能是 Windows 版本特性或流量桥接）。")
    print("4. 如果手机不能上网但能打开 http://192.168.137.1:8080，说明成功！")
    print("="*30)

if __name__ == "__main__":
    main()
