# -*- coding: utf-8 -*-
"""
Zopia.ai 自动注册脚本
- 用已注册的邮箱账号注册 Zopia
- 每个账号生成邀请链接，可邀请10个邮箱
- 11个账号为一组（1个邀请人 + 10个被邀请人）
- 保存到 txt/CSV
"""
import random, time, json, re, os
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path
from datetime import datetime

# ==================== 配置 ====================
AFFILIATE_CODE = "WxE5lNPc"   # 固定邀请码
BASE_URL = "https://zopia.ai"
MAX_INVITEES = 10              # 每个账号最多邀请10个
GROUP_SIZE = 11                # 每组：1个主账号 + 10个被邀请账号

@dataclass
class ZopiaAccount:
    email: str
    password: str
    affiliate_link: str = ""
    invite_count: int = 0
    invited_emails: List[str] = None
    group_id: int = 0
    role: str = "inviter"  # "inviter" or "invitee"
    registered_at: str = ""

    def __post_init__(self):
        if self.invited_emails is None:
            self.invited_emails = []

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_data(filepath: str = "zopia_accounts.json") -> List[ZopiaAccount]:
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
            return [ZopiaAccount(**a) for a in data]
    return []

def save_data(accounts: List[ZopiaAccount], filepath: str = "zopia_accounts.json"):
    with open(filepath, 'w') as f:
        json.dump([asdict(a) for a in accounts], f, ensure_ascii=False, indent=2)

def save_csv(accounts: List[ZopiaAccount], filepath: str = "zopia_accounts.csv"):
    """导出CSV格式，便于查看"""
    with open(filepath, 'w') as f:
        f.write("组号,角色,邮箱,密码,邀请链接,已邀请数,注册时间\n")
        for a in accounts:
            f.write(f"{a.group_id},{a.role},{a.email},{a.password},{a.affiliate_link},{a.invite_count},{a.registered_at}\n")
    print(f"CSV已保存: {filepath}")

def save_txt(accounts: List[ZopiaAccount], filepath: str = "zopia_accounts.txt"):
    """导出TXT格式，便于程序读取"""
    with open(filepath, 'w') as f:
        for a in accounts:
            f.write(f"[Group {a.group_id}] {a.role.upper()}: {a.email}:{a.password}\n")
            if a.invited_emails:
                f.write(f"  Invited: {', '.join(a.invited_emails)}\n")
            f.write("\n")
    print(f"TXT已保存: {filepath}")

# ==================== 浏览器自动化 ====================
def init_browser(proxy: str = ""):
    """初始化浏览器"""
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
        options = ChromiumOptions()
        if proxy:
            options.set_proxy(proxy)
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-dev-shm-usage')
        # 随机User-Agent
        options.set_argument(f'--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = ChromiumPage(options)
        return page
    except ImportError:
        print("DrissionPage未安装，运行: pip install DrissionPage")
        return None
    except Exception as e:
        print(f"浏览器初始化失败: {e}")
        return None

def register_zopia(page, email: str, password: str) -> Optional[dict]:
    """
    注册 Zopia 账号
    """
    try:
        page.get(f"{BASE_URL}/signup?aff={AFFILIATE_CODE}")
        time.sleep(random.uniform(2, 4))

        # 填写注册表单
        page.ele('#email').input(email) if page.ele('#email') else None
        time.sleep(0.5)

        pw = page.ele('#password') or page.ele('[name="password"]') or page.ele('input[type="password"]')
        if pw:
            pw.input(password)
        time.sleep(0.5)

        # 点击注册
        submit = page.ele('#submit') or page.ele('button[type="submit"]') or page.ele('button:has-text("Sign up")')
        if submit:
            submit.click()

        time.sleep(3)

        # 检查是否注册成功
        if "dashboard" in page.url or "login" not in page.url:
            print(f"  ✅ 注册成功: {email}")
            return {"email": email, "success": True}
        else:
            print(f"  ❌ 注册可能失败，当前URL: {page.url}")
            return {"email": email, "success": False, "url": page.url}

    except Exception as e:
        print(f"  ❌ 注册出错: {e}")
        return {"email": email, "success": False, "error": str(e)}

def get_affiliate_link(page) -> Optional[str]:
    """获取邀请链接"""
    try:
        # 通常在 dashboard 或 account 设置里
        page.get(f"{BASE_URL}/dashboard")
        time.sleep(2)

        # 查找邀请链接
        link_elem = page.ele('a:has-text("affiliate")') or \
                   page.ele('[href*="aff="]') or \
                   page.ele('input[value*="WxE5"]')
        if link_elem:
            href = link_elem.attr('href') or link_elem.attr('value')
            if href:
                return href

        # 从页面源码中搜索
        content = page.html
        match = re.search(r'(https?://[^\s"\'<>]+aff=[A-Za-z0-9]+)', content)
        if match:
            return match.group(1)

        return f"{BASE_URL}/signup?aff={AFFILIATE_CODE}"
    except Exception as e:
        print(f"  ⚠️ 获取邀请链接失败: {e}")
        return f"{BASE_URL}/signup?aff={AFFILIATE_CODE}"

# ==================== 批量注册 ====================
def register_group_inviter(accounts: List[ZopiaAccount], page, group_id: int, email: str, password: str, proxy: str = "") -> ZopiaAccount:
    """注册一组的主账号（邀请人）"""
    print(f"\n[{group_id}] 注册主账号(邀请人): {email}")

    result = register_zopia(page, email, password)
    if result and result.get("success"):
        link = get_affiliate_link(page)
        acc = ZopiaAccount(
            email=email,
            password=password,
            affiliate_link=link,
            invite_count=0,
            invited_emails=[],
            group_id=group_id,
            role="inviter",
            registered_at=get_timestamp()
        )
    else:
        acc = ZopiaAccount(
            email=email,
            password=password,
            affiliate_link=f"{BASE_URL}/signup?aff={AFFILIATE_CODE}",
            group_id=group_id,
            role="inviter",
            registered_at=get_timestamp()
        )

    return acc

def register_invitee(accounts: List[ZopiaAccount], page, inviter_acc: ZopiaAccount, email: str, password: str) -> ZopiaAccount:
    """注册被邀请账号"""
    print(f"  [{inviter_acc.group_id}] 注册被邀请人: {email}")

    # 使用邀请人的链接注册
    try:
        page.get(inviter_acc.affiliate_link)
        time.sleep(random.uniform(2, 3))

        # 填写注册表单
        page.ele('#email').input(email) if page.ele('#email') else None
        time.sleep(0.5)
        pw = page.ele('#password') or page.ele('[name="password"]') or page.ele('input[type="password"]')
        if pw:
            pw.input(password)
        time.sleep(0.5)

        submit = page.ele('button[type="submit"]') or page.ele('button:has-text("Sign up")')
        if submit:
            submit.click()

        time.sleep(3)

        # 更新邀请人的邀请数
        inviter_acc.invite_count += 1
        inviter_acc.invited_emails.append(email)

        return ZopiaAccount(
            email=email,
            password=password,
            group_id=inviter_acc.group_id,
            role="invitee",
            registered_at=get_timestamp()
        )
    except Exception as e:
        print(f"  ⚠️ 注册被邀请人出错: {e}")
        return ZopiaAccount(
            email=email,
            password=password,
            group_id=inviter_acc.group_id,
            role="invitee",
            registered_at=get_timestamp()
        )

def generate_email_name() -> str:
    """生成随机邮箱名"""
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return ''.join(random.choices(chars, k=random.randint(8, 12)))

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zopia.ai 自动注册")
    parser.add_argument("--groups", "-g", type=int, default=1, help="注册多少组(每组11个)")
    parser.add_argument("--email-domain", default="outlook.com", help="邮箱后缀")
    parser.add_argument("--delay", "-d", type=int, default=5, help="注册间隔(秒)")
    parser.add_argument("--proxy", default="", help="代理 IP:端口")
    parser.add_argument("--data-file", default="zopia_accounts.json", help="数据文件")
    parser.add_argument("--export-csv", action="store_true", help="同时导出CSV")
    parser.add_argument("--export-txt", action="store_true", help="同时导出TXT")
    args = parser.parse_args()

    accounts = load_data(args.data_file)
    page = init_browser(args.proxy)

    if not page:
        print("无法启动浏览器，请安装 DrissionPage")
        return

    print(f"=" * 60)
    print(f"Zopia.ai 自动注册 - {args.groups} 组 x {GROUP_SIZE} = {args.groups * GROUP_SIZE} 个账号")
    print(f"邀请码: {AFFILIATE_CODE}")
    print(f"=" * 60)

    for g in range(args.groups):
        group_id = g + 1
        group_accounts = []

        # 1. 注册主账号（邀请人）
        inviter_email = f"{generate_email_name()}@{args.email_domain}"
        inviter_pw = f"Zopia{random.randint(100000, 999999)}!"
        inviter_acc = register_group_inviter(
            accounts, page, group_id, inviter_email, inviter_pw, args.proxy
        )
        accounts.append(inviter_acc)
        group_accounts.append(inviter_acc)
        save_data(accounts, args.data_file)
        time.sleep(args.delay)

        # 2. 注册10个被邀请账号
        for i in range(MAX_INVITEES):
            invitee_email = f"{generate_email_name()}{random.randint(10,99)}@{args.email_domain}"
            invitee_pw = f"Zopia{random.randint(100000, 999999)}!"
            invitee_acc = register_invitee(accounts, page, inviter_acc, invitee_email, invitee_pw)
            accounts.append(invitee_acc)
            group_accounts.append(invitee_acc)
            save_data(accounts, args.data_file)
            print(f"  [{group_id}] 已邀请 {inviter_acc.invite_count}/{MAX_INVITEES}")
            time.sleep(args.delay)

        print(f"\n✅ Group {group_id} 完成: 邀请人1 + 被邀请人{inviter_acc.invite_count}")

    page.quit()

    print(f"\n{'='*60}")
    print(f"注册完成! 共 {len(accounts)} 个账号, {args.groups} 组")
    print(f"数据保存: {args.data_file}")

    if args.export_csv:
        save_csv(accounts)
    if args.export_txt:
        save_txt(accounts)

if __name__ == "__main__":
    main()
