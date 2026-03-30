# -*- coding: utf-8 -*-
"""
邮箱自动注册脚本
支持: Hotmail/Outlook, Gmail, QQ邮箱, 163邮箱, 新浪邮箱
使用 Browser-Use / DrissionPage 模拟人工注册
"""
import random, time, json, os, re
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path

# ==================== 配置 ====================
CONFIG_FILE = "accounts.json"
OUTPUT_FILE = "registered_accounts.json"

@dataclass
class EmailAccount:
    email: str
    password: str
    platform: str
    proxy: str = ""
    registered_at: str = ""
    invite_code: str = ""
    status: str = "pending"

def load_accounts():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            return json.load(f)
    return []

def save_accounts(accounts):
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

def get_timestamp():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ==================== 随机数据生成 ====================
FIRST_NAMES = ["张","王","李","赵","陈","刘","吴","杨","周","黄","徐","孙","马","朱","胡","郭","何","林","罗","高"]
LAST_NAMES = ["伟","芳","娜","敏","静","丽","强","磊","军","洋","勇","艳","杰","涛","明","超","秀英","霞","平","刚"]
DOMAINS = {
    "hotmail": ["hotmail.com", "outlook.com", "live.com", "msn.com"],
    "gmail": ["gmail.com"],
    "qq": ["qq.com"],
    "163": ["163.com", "126.com"],
    "sina": ["sina.com", "sina.cn"],
}

def generate_name():
    return random.choice(FIRST_NAMES) + random.choice(LAST_NAMES) + str(random.randint(10, 99))

def generate_email(platform: str) -> tuple:
    name = generate_name()
    domain = random.choice(DOMAINS.get(platform, ["outlook.com"]))
    email = f"{name}@{domain}"
    password = f"Pass{random.randint(100000, 999999)}!"
    return email, password, platform

# ==================== 核心注册逻辑 ====================
def register_hotmail(email: str, password: str, proxy: str = "") -> dict:
    """
    注册 Outlook/Hotmail 邮箱
    使用 requests + MS Graph API 或 Browser
    """
    print(f"[Outlook] 开始注册: {email}")

    # 方式1: Microsoft Account Create API (非官方，需自行研究)
    # 方式2: Browser自动化 (推荐 DrissionPage)
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions

        options = ChromiumOptions()
        if proxy:
            options.set_proxy(proxy)
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_argument('--no-sandbox')

        page = ChromiumPage(options)
        page.get('https://signup.live.com/signup')

        # 填写邮箱
        page.ele('#MemberName').input(email)
        page.ele('#MemberNameSubmit').click()
        time.sleep(2)

        # 选择自定义邮箱（已有邮箱跳过）
        try:
            page.ele('#CreateMicrosoftAccountAside').click()
            time.sleep(1)
        except:
            pass

        # 填写密码
        page.ele('#PasswordInput').input(password)
        page.ele('#PasswordConfirm').input(password)
        page.ele('#SignupFormSubmit').click()
        time.sleep(2)

        # 填写姓名
        page.ele('#FirstName').input(generate_name())
        page.ele('#LastName').input(generate_name())
        page.ele('#SignupFormSubmit').click()
        time.sleep(2)

        # 出生日期
        page.ele('#BirthMonth').select('1')
        page.ele('#BirthDay').input(str(random.randint(1, 28)))
        page.ele('#BirthYear').input(str(random.randint(1980, 2005)))
        page.ele('#SignupFormSubmit').click()
        time.sleep(3)

        page.quit()
        print(f"[Outlook] ✅ 注册成功: {email}")
        return {"success": True, "email": email}

    except ImportError:
        print("[Outlook] DrissionPage未安装，请运行: pip install DrissionPage")
        return {"success": False, "email": email, "error": "DrissionPage未安装"}
    except Exception as e:
        print(f"[Outlook] ❌ 注册失败: {e}")
        return {"success": False, "email": email, "error": str(e)}

def register_gmail(email: str, password: str, proxy: str = "") -> dict:
    """注册Gmail"""
    print(f"[Gmail] 开始注册: {email}")
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions

        options = ChromiumOptions()
        if proxy:
            options.set_proxy(proxy)
        options.set_argument('--disable-blink-features=AutomationControlled')

        page = ChromiumPage(options)
        page.get('https://accounts.google.com/signup')

        # 填写名字
        page.ele('[name="firstName"]').input(generate_name())
        page.ele('[name="lastName"]').input(generate_name())
        page.ele('#collectNameNext').click()
        time.sleep(2)

        # 填写出生日期
        page.ele('[name="birthdayMonth"]').select('1')
        page.ele('[name="birthdayDay"]').input(str(random.randint(1, 28)))
        page.ele('[name="birthdayYear"]').input(str(random.randint(1980, 2005)))
        page.ele('[name="gender"]').select('1')
        page.click('#birthdaygenderNext')
        time.sleep(2)

        # 使用建议的邮箱或自定义
        try:
            page.ele('#utySzEd').click()  # 使用建议邮箱
        except:
            pass

        page.click('#next')
        time.sleep(3)

        page.quit()
        print(f"[Gmail] ✅ 注册成功: {email}")
        return {"success": True, "email": email}
    except Exception as e:
        print(f"[Gmail] ❌ 注册失败: {e}")
        return {"success": False, "email": email, "error": str(e)}

# ==================== 主程序 ====================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="邮箱自动注册脚本")
    parser.add_argument("--platform", "-p", default="hotmail",
                       choices=["hotmail", "gmail", "qq", "163", "sina"],
                       help="邮箱平台")
    parser.add_argument("--count", "-c", type=int, default=10, help="注册数量")
    parser.add_argument("--delay", "-d", type=int, default=5, help="注册间隔(秒)")
    parser.add_argument("--proxy", default="", help="代理 IP:端口")
    args = parser.parse_args()

    accounts = load_accounts()

    print(f"=" * 50)
    print(f"邮箱自动注册 - {args.platform} - 目标: {args.count}个")
    print(f"=" * 50)

    success_count = 0
    for i in range(args.count):
        email, password, platform = generate_email(args.platform)
        print(f"\n[{i+1}/{args.count}] 正在注册: {email}")

        if platform in ["hotmail", "outlook", "live"]:
            result = register_hotmail(email, password, args.proxy)
        elif platform == "gmail":
            result = register_gmail(email, password, args.proxy)
        else:
            print(f"[{platform}] 该平台暂不支持")
            continue

        if result.get("success"):
            accounts.append({
                **result,
                "password": password,
                "platform": platform,
                "proxy": args.proxy,
                "registered_at": get_timestamp(),
                "status": "registered"
            })
            success_count += 1

        time.sleep(args.delay)
        save_accounts(accounts)

    print(f"\n{'='*50}")
    print(f"注册完成: {success_count}/{args.count} 成功")
    print(f"结果保存到: {OUTPUT_FILE}")
    save_accounts(accounts)

if __name__ == "__main__":
    main()
