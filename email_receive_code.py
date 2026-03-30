# -*- coding: utf-8 -*-
"""
邮箱验证码接收脚本
支持: Outlook/Hotmail (IMAP+OAuth2), Gmail (IMAP), QQ邮箱, 163邮箱
功能: 登录邮箱 → 接收验证码 → 提取验证码内容
"""
import time, json, re, imaplib, smtplib, email
from email.header import decode_header
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timedelta

# ==================== 配置 ====================
CONFIG = {
    "check_interval": 10,        # 邮件检查间隔(秒)
    "max_wait": 300,            # 最大等待时间(秒)
    "email_patterns": [          # 验证码正则模式
        r'[Bb]验证[码代码][：:]\s*(\d{4,8})',
        r'[Cc]ode[：:]\s*([A-Z0-9]{4,8})',
        r'[Vv]erification[：:]\s*(\d{4,8})',
        r'一次性[码代码][：:]\s*(\d{4,8})',
        r'注册[码代码][：:]\s*(\d{4,8})',
        r'(\\d{6})',              # 6位纯数字
        r'(\\d{4})',              # 4位纯数字
    ],
    "senders_filter": [           # 只检查这些发件人的邮件
        "noreply", "no-reply", "support", "service",
        "admin", "notify", "verification", "verify"
    ]
}

@dataclass
class EmailMessage:
    sender: str
    subject: str
    body: str
    timestamp: str
    code: Optional[str] = None

# ==================== 工具函数 ====================
def decode_str(s):
    """解码email header字符串"""
    if not s:
        return ""
    decoded_parts = decode_header(s)
    result = []
    for part, enc in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or 'utf-8', errors='ignore'))
        else:
            result.append(part)
    return ''.join(result)

def get_email_body(msg) -> str:
    """提取邮件正文"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain':
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
                break
            elif ct == 'text/html':
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or 'utf-8'
        body = payload.decode(charset, errors='ignore')
    return body

def extract_code(body: str) -> Optional[str]:
    """从邮件内容提取验证码"""
    for pattern in CONFIG["email_patterns"]:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def is_valid_code(code: str) -> bool:
    """验证码有效性检查"""
    if not code:
        return False
    # 过滤明显不是验证码的
    if len(code) < 4 or len(code) > 8:
        return False
    if not code.isalnum():
        return False
    return True

# ==================== 邮箱连接 ====================
def connect_outlook_imap(email_addr: str, access_token: str) -> Optional[imaplib.IMAP4_SSL]:
    """OAuth2 + IMAP 连接 Outlook"""
    try:
        mail = imaplib.IMAP4_SSL("outlook.office365.com", 993)
        auth_string = f"user={email_addr}\x01auth=Bearer {access_token}\x01\x01"
        mail.authenticate('XOAUTH2', lambda x: auth_string.encode())
        return mail
    except Exception as e:
        print(f"[Outlook] 连接失败: {e}")
        return None

def connect_gmail_imap(email_addr: str, access_token: str) -> Optional[imaplib.IMAP4_SSL]:
    """OAuth2 + IMAP 连接 Gmail"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        auth_string = f"user={email_addr}\x01auth=Bearer {access_token}\x01\x01"
        mail.authenticate('XOAUTH2', lambda x: auth_string.encode())
        return mail
    except Exception as e:
        print(f"[Gmail] 连接失败: {e}")
        return None

def connect_qq_imap(email_addr: str, password: str) -> Optional[imaplib.IMAP4_SSL]:
    """QQ邮箱 IMAP (需要开启IMAP服务并获取授权码)"""
    try:
        mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
        # QQ邮箱用授权码代替密码
        mail.login(email_addr, password)
        return mail
    except Exception as e:
        print(f"[QQ] 连接失败: {e}")
        return None

def connect_163_imap(email_addr: str, password: str) -> Optional[imaplib.IMAP4_SSL]:
    """163邮箱 IMAP (需要开启IMAP服务)"""
    try:
        mail = imaplib.IMAP4_SSL("imap.163.com", 993)
        mail.login(email_addr, password)
        return mail
    except Exception as e:
        print(f"[163] 连接失败: {e}")
        return None

def refresh_token_if_needed(refresh_token: str, client_id: str, client_secret: str) -> Optional[str]:
    """刷新OAuth2 access token"""
    import urllib.request, urllib.parse

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    try:
        req = urllib.request.Request(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("access_token")
    except Exception as e:
        print(f"[Token] 刷新失败: {e}")
        return None

# ==================== 验证码等待 ====================
def wait_for_code(
    mail_conn,
    platform: str,
    email_addr: str,
    from_sender: str = "",
    max_wait: int = 300
) -> Optional[str]:
    """
    等待并提取验证码
    mail_conn: IMAP连接
    platform: outlook/gmail/qq/163
    email_addr: 邮箱地址
    from_sender: 指定发件人(可选)
    """
    print(f"[{platform}] 开始等待验证码... (最长 {max_wait}秒)")
    start_time = time.time()
    last_check = datetime.now() - timedelta(minutes=5)  # 最近5分钟内的邮件

    while time.time() - start_time < max_wait:
        try:
            if platform in ["outlook", "hotmail"]:
                mail_conn.select('INBOX')
            else:
                mail_conn.select('INBOX')

            # 搜索邮件 (最近几分钟内的未读邮件)
            search_after = (datetime.now() - timedelta(minutes=10)).strftime("%d-%b-%Y")
            if from_sender:
                status, messages = mail_conn.search(None, f'UNSEEN SINCE {search_after} FROM "{from_sender}"')
            else:
                status, messages = mail_conn.search(None, f'UNSEEN SINCE {search_after}')

            mail_ids = messages[0].split()
            print(f"[{platform}] 检查 {len(mail_ids)} 封新邮件...")

            for mail_id in reversed(mail_ids[-5:]):  # 检查最近5封
                try:
                    status, msg_data = mail_conn.fetch(mail_id, '(RFC822)')
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    sender = decode_str(msg.get('From', ''))
                    subject = decode_str(msg.get('Subject', ''))
                    body = get_email_body(msg)

                    print(f"  📧 来自: {sender[:40]}")
                    print(f"     主题: {subject[:60]}")

                    # 提取验证码
                    code = extract_code(body)
                    if code and is_valid_code(code):
                        print(f"  ✅ 找到验证码: {code}")
                        return code

                except Exception as e:
                    print(f"  ⚠️ 读取邮件失败: {e}")
                    continue

        except Exception as e:
            print(f"  ⚠️ 搜索邮件失败: {e}")

        print(f"  ⏳ 等待 {CONFIG['check_interval']} 秒...")
        time.sleep(CONFIG['check_interval'])

    print(f"[{platform}] ⏰ 超时，未找到验证码")
    return None

# ==================== 主程序 ====================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="邮箱验证码接收")
    parser.add_argument("--email", required=True, help="邮箱地址")
    parser.add_argument("--password", help="密码或授权码(QQ/163用)")
    parser.add_argument("--platform", choices=["outlook", "gmail", "qq", "163"], required=True)
    parser.add_argument("--access-token", dest="access_token", help="OAuth2 Access Token")
    parser.add_argument("--refresh-token", dest="refresh_token", help="OAuth2 Refresh Token")
    parser.add_argument("--client-id", dest="client_id", help="OAuth2 Client ID")
    parser.add_argument("--client-secret", dest="client_secret", help="OAuth2 Client Secret")
    parser.add_argument("--sender", default="", help="指定发件人过滤")
    parser.add_argument("--max-wait", type=int, default=300, dest="max_wait", help="最大等待秒数")
    args = parser.parse_args()

    print(f"连接邮箱: {args.email} ({args.platform})")

    # 建立连接
    conn = None
    access_tok = args.access_token

    # 如果有refresh_token，尝试刷新
    if args.refresh_token and args.client_id:
        access_tok = refresh_token_if_needed(
            args.refresh_token, args.client_id, args.client_secret
        ) or args.access_token

    if args.platform in ["outlook", "hotmail"]:
        if not access_tok:
            print("❌ 需要 --access-token (OAuth2)")
            return
        conn = connect_outlook_imap(args.email, access_tok)
    elif args.platform == "gmail":
        if not access_tok:
            print("❌ 需要 --access-token (OAuth2)")
            return
        conn = connect_gmail_imap(args.email, access_tok)
    elif args.platform == "qq":
        if not args.password:
            print("❌ QQ邮箱需要 --password (授权码)")
            return
        conn = connect_qq_imap(args.email, args.password)
    elif args.platform == "163":
        if not args.password:
            print("❌ 163邮箱需要 --password")
            return
        conn = connect_163_imap(args.email, args.password)

    if not conn:
        print("❌ 连接失败")
        return

    print("✅ 邮箱连接成功")

    # 等待验证码
    code = wait_for_code(conn, args.platform, args.email, args.sender, args.max_wait)

    if code:
        print(f"\n🎉 验证码: {code}")
        # 可选：保存到文件
        with open("captured_code.txt", "w") as f:
            f.write(code)
        print("已保存到 captured_code.txt")
    else:
        print("\n❌ 未找到验证码")

    conn.logout()

if __name__ == "__main__":
    main()
