# -*- coding: utf-8 -*-
"""
自动注册机 - 类比脚本
基于 BV1WXouYmEKn 视频技术分析重构
支持: Outlook/Hotmail OAuth2 邮箱自动注册
"""

import random
import time
import json
import re
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.header import decode_header
from threading import Thread
from dataclasses import dataclass
from typing import Optional, List

# ==================== 配置 ====================
CONFIG = {
    "thread_count": 10,        # 并发线程数
    "retry_count": 3,          # 重试次数
    "delay_range": (1, 3),     # 请求间隔(秒)
    "oauth2": {
        "client_id": "YOUR_AZURE_APP_CLIENT_ID",
        "client_secret": "YOUR_AZURE_APP_CLIENT_SECRET",
        "redirect_uri": "http://localhost",
        "scope": "https://outlook.office.com/IMAP.AccessAsUser.All"
    }
}


# ==================== 数据模型 ====================
@dataclass
class Account:
    email: str
    password: str
    client_id: str
    refresh_token: str
    access_token: str


@dataclass
class RegisterResult:
    email: str
    success: bool
    message: str
    timestamp: str


# ==================== 工具函数 ====================
def read_all_accounts(filepath: str = "accounts.json") -> List[Account]:
    """步骤1: 读取所有账号数据"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [Account(**acc) for acc in data]
    except FileNotFoundError:
        # 如果文件不存在，生成示例数据
        print("[INFO] accounts.json 不存在，生成示例数据...")
        sample = [
            {"email": "test001@outlook.com", "password": "pwd001",
             "client_id": "cid001", "refresh_token": "rt001", "access_token": "at001"},
            {"email": "test002@outlook.com", "password": "pwd002",
             "client_id": "cid002", "refresh_token": "rt002", "access_token": "at002"},
        ]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)
        return [Account(**acc) for acc in sample]


def send_regist_msg(email: str, password: str) -> bool:
    """步骤2: 发送注册消息/验证码到目标邮箱"""
    # 这里模拟向某个平台API发送注册请求
    # 真实场景: 调用目标平台的注册API
    delay = random.uniform(*CONFIG["delay_range"])
    time.sleep(delay)

    # 模拟API调用
    success = random.random() > 0.1  # 90%成功率
    print(f"[INFO] {email} → 发送验证码 {'成功' if success else '失败'}")
    return success


def refresh_oauth2_token(refresh_token: str, client_id: str, client_secret: str) -> Optional[str]:
    """刷新 OAuth2 Access Token"""
    import requests

    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": CONFIG["oauth2"]["scope"]
    }

    try:
        resp = requests.post(token_url, data=data, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception as e:
        print(f"[ERROR] Token刷新失败: {e}")
    return None


def get_mail_content_oauth2(email: str, access_token: str) -> Optional[str]:
    """步骤3: 用 OAuth2 + IMAP 收取邮件内容"""
    import requests

    # Microsoft Graph API 获取邮件
    # 或者直接用 IMAP + OAuth2
    try:
        # 方法1: IMAP with OAuth2
        mail = imaplib.IMAP4_SSL("outlook.office365.com", 993)
        mail.authenticate('XOAUTH2', lambda x:
            f"user={email}\x01auth=Bearer {access_token}\x01\x01".encode()
        )
        mail.select('INBOX')

        # 搜索最新邮件
        status, messages = mail.search(None, 'UNSEEN', 'FROM', 'noreply@microsoft.com')
        mail_ids = messages[0].split()
        if not mail_ids:
            return None

        # 获取最新邮件
        latest_id = mail_ids[-1]
        status, msg_data = mail.fetch(latest_id, '(RFC822)')
        mail_content = msg_data[0][1]

        mail.logout()
        return mail_content.decode('utf-8', errors='ignore')

    except Exception as e:
        print(f"[ERROR] 收取邮件失败: {e}")
        return None


def parse_code(mail_content: str) -> Optional[str]:
    """步骤4: 从邮件内容中解析验证码"""
    if not mail_content:
        return None

    # 常见验证码正则模式
    patterns = [
        r'(\d{4,8})',           # 纯数字验证码
        r'verification code[：:\s]*([A-Z0-9]{4,8})',
        r'验证码[：:\s]*([0-9A-Z]{4,8})',
        r'code[：:\s]*([A-Z0-9]{4,8})',
    ]

    for pattern in patterns:
        match = re.search(pattern, mail_content, re.IGNORECASE)
        if match:
            code = match.group(1)
            print(f"[INFO] 解析到验证码: {code}")
            return code
    return None


def confirm_register(email: str, code: str) -> bool:
    """步骤5: 用验证码确认完成注册"""
    delay = random.uniform(0.5, 1.5)
    time.sleep(delay)

    success = random.random() > 0.15  # 85%成功率
    print(f"[INFO] {email} → 注册确认 {'成功' if success else '失败'}")
    return success


# ==================== 主逻辑 ====================
def func(acc: Account) -> RegisterResult:
    """处理单个账号的完整注册流程"""
    email = acc.email

    # 步骤2: 发送注册消息
    if not send_regist_msg(email, acc.password):
        return RegisterResult(email, False, "发送验证码失败", time.strftime("%Y-%m-%d %H:%M:%S"))

    # 步骤3: OAuth2 IMAP 收取邮件
    access_token = acc.access_token

    # 尝试刷新token（如果access_token过期）
    if not access_token:
        access_token = refresh_oauth2_token(
            acc.refresh_token,
            acc.client_id,
            CONFIG["oauth2"]["client_secret"]
        )

    if not access_token:
        return RegisterResult(email, False, "OAuth2鉴权失败", time.strftime("%Y-%m-%d %H:%M:%S"))

    print(f"[INFO] {email} → OAuth2鉴权成功")

    mail_content = get_mail_content_oauth2(email, access_token)
    if not mail_content:
        return RegisterResult(email, False, "未收到邮件", time.strftime("%Y-%m-%d %H:%M:%S"))

    # 步骤4: 解析验证码
    code = parse_code(mail_content)
    if not code:
        return RegisterResult(email, False, "解析验证码失败", time.strftime("%Y-%m-%d %H:%M:%S"))

    # 步骤5: 确认注册
    if confirm_register(email, code):
        return RegisterResult(email, True, f"注册成功，验证码: {code}", time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        return RegisterResult(email, False, "注册确认失败", time.strftime("%Y-%m-%d %H:%M:%S"))


def run_threads(accounts: List[Account]) -> List[RegisterResult]:
    """多线程并发执行"""
    results = []
    threads = []

    def thread_wrapper(acc):
        result = func(acc)
        results.append(result)

    # 创建线程
    for acc in accounts:
        t = Thread(target=thread_wrapper, args=(acc,))
        threads.append(t)
        t.start()

        # 控制并发数
        active = sum(1 for t in threads if t.is_alive())
        if active >= CONFIG["thread_count"]:
            for t in threads:
                t.join()

    # 等待所有线程完成
    for t in threads:
        t.join()

    return results


# ==================== 入口 ====================
if __name__ == "__main__":
    print("=" * 50)
    print("自动注册机 - OAuth2 邮箱批量注册")
    print("=" * 50)

    # 步骤1: 读取所有账号
    accounts = read_all_accounts()
    print(f"[INFO] 共读取 {len(accounts)} 个账号")

    if not accounts:
        print("[ERROR] 没有找到账号数据，请创建 accounts.json")
        print("格式: [{\"email\":\"xxx@outlook.com\",\"password\":\"pwd\",\"client_id\":\"cid\",\"refresh_token\":\"rt\",\"access_token\":\"at\"}]")
        exit(1)

    # 多线程执行
    print(f"[INFO] 启动 {CONFIG['thread_count']} 个并发线程...")
    results = run_threads(accounts)

    # 输出结果
    print("\n" + "=" * 50)
    print("执行结果汇总")
    print("=" * 50)
    success_count = sum(1 for r in results if r.success)
    print(f"成功: {success_count}/{len(results)}")
    print(f"失败: {len(results) - success_count}/{len(results)}")

    for r in results:
        status = "✅" if r.success else "❌"
        print(f"{status} {r.email} → {r.message}")

    # 保存结果
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump([{"email": r.email, "success": r.success, "message": r.message,
                    "timestamp": r.timestamp} for r in results], f, ensure_ascii=False, indent=2)
    print("\n[INFO] 结果已保存到 results.json")
