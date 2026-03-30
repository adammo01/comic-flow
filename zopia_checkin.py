# -*- coding: utf-8 -*-
"""
Zopia.ai 登录签到脚本
- 读取已注册的账号列表
- 批量登录并签到
- 记录签到状态和结果
"""
import random, time, json, re, os, sys
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional

BASE_URL = "https://zopia.ai"

@dataclass
class CheckInResult:
    email: str
    checked_in: bool
    points_earned: int = 0
    total_points: int = 0
    streak_days: int = 0
    error: str = ""
    timestamp: str = ""

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_accounts(filepath: str = "zopia_accounts.json") -> List[dict]:
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return []

def save_results(results: List[CheckInResult], filepath: str = "checkin_results.json"):
    with open(filepath, 'w') as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)

def init_browser(proxy: str = "", headless: bool = True):
    """初始化浏览器"""
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
        options = ChromiumOptions()
        if proxy:
            options.set_proxy(proxy)
        if headless:
            options.set_argument('--headless=new')
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-dev-shm-usage')
        options.set_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = ChromiumPage(options)
        return page
    except ImportError:
        print("DrissionPage未安装，运行: pip install DrissionPage")
        return None
    except Exception as e:
        print(f"浏览器初始化失败: {e}")
        return None

def login_zopia(page, email: str, password: str) -> bool:
    """登录Zopia"""
    try:
        page.get(f"{BASE_URL}/login")
        time.sleep(random.uniform(2, 3))

        # 填写邮箱
        email_input = page.ele('#email') or page.ele('[name="email"]') or page.ele('input[type="email"]')
        if email_input:
            email_input.input(email)
        time.sleep(0.5)

        # 填写密码
        pw_input = page.ele('#password') or page.ele('[name="password"]') or page.ele('input[type="password"]')
        if pw_input:
            pw_input.input(password)
        time.sleep(0.5)

        # 点击登录
        submit = page.ele('button[type="submit"]') or page.ele('button:has-text("Log")') or page.ele('button:has-text("Sign in")')
        if submit:
            submit.click()
        time.sleep(3)

        # 检查是否登录成功
        if "dashboard" in page.url or "account" in page.url or page.ele('.user') or page.ele('[class*="avatar"]'):
            print(f"  ✅ 登录成功: {email}")
            return True
        else:
            print(f"  ❌ 登录失败: {email} (URL: {page.url})")
            return False

    except Exception as e:
        print(f"  ❌ 登录出错: {email} - {e}")
        return False

def check_in(page) -> Optional[dict]:
    """执行签到"""
    try:
        # 跳转到签到页面或dashboard
        page.get(f"{BASE_URL}/dashboard")
        time.sleep(2)

        # 查找签到按钮
        checkin_btn = (
            page.ele('button:has-text("Check in")') or
            page.ele('button:has-text("签到")') or
            page.ele('button:has-text("Daily")') or
            page.ele('[class*="checkin"]') or
            page.ele('[id*="checkin"]')
        )

        if checkin_btn:
            checkin_btn.click()
            time.sleep(2)
            print("  ✅ 签到完成")

        # 提取积分信息
        points = 0
        streak = 0

        page_content = page.html
        # 匹配积分
        pts_match = re.search(r'(\d+)\s*(?:points?|积分)', page_content, re.IGNORECASE)
        if pts_match:
            points = int(pts_match.group(1))

        # 匹配连续签到天数
        streak_match = re.search(r'(\d+)\s*(?:days?|天)', page_content, re.IGNORECASE)
        if streak_match:
            streak = int(streak_match.group(1))

        return {"points": points, "streak": streak}

    except Exception as e:
        print(f"  ⚠️ 签到获取信息失败: {e}")
        return {"points": 0, "streak": 0}

def process_account(page, email: str, password: str) -> CheckInResult:
    """处理单个账号的签到"""
    result = CheckInResult(
        email=email,
        checked_in=False,
        timestamp=get_timestamp()
    )

    # 登录
    if not login_zopia(page, email, password):
        result.error = "登录失败"
        return result

    time.sleep(random.uniform(1, 2))

    # 签到
    checkin_info = check_in(page)
    if checkin_info:
        result.checked_in = True
        result.points_earned = checkin_info.get("points", 0)
        result.total_points = checkin_info.get("points", 0)
        result.streak_days = checkin_info.get("streak", 0)

    # 获取邀请奖励页面
    try:
        page.get(f"{BASE_URL}/affiliate")
        time.sleep(2)

        # 查找今日邀请奖励
        content = page.html
        reward_match = re.search(r'(\d+)\s*(?:invites?|邀请)', content, re.IGNORECASE)
        if reward_match:
            print(f"  📊 邀请数: {reward_match.group(1)}")
    except:
        pass

    return result

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zopia.ai 登录签到")
    parser.add_argument("--accounts", "-a", default="zopia_accounts.json", help="账号文件")
    parser.add_argument("--results", "-r", default="checkin_results.json", help="结果文件")
    parser.add_argument("--proxy", default="", help="代理 IP:端口")
    parser.add_argument("--delay", "-d", type=int, default=10, help="账号间隔(秒)")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="显示浏览器")
    args = parser.parse_args()

    accounts = load_accounts(args.accounts)
    if not accounts:
        print(f"❌ 未找到账号文件: {args.accounts}")
        return

    page = init_browser(args.proxy, args.headless)
    if not page:
        return

    print(f"=" * 60)
    print(f"Zopia.ai 登录签到 - {len(accounts)} 个账号")
    print(f"=" * 60)

    results = []
    success = 0

    for i, acc in enumerate(accounts):
        email = acc.get('email', '')
        password = acc.get('password', '')

        if not email or not password:
            print(f"[{i+1}] 跳过无效账号")
            continue

        print(f"\n[{i+1}/{len(accounts)}] {email}")

        result = process_account(page, email, password)
        results.append(result)

        if result.checked_in:
            success += 1

        # 保存进度
        save_results(results, args.results)

        if i < len(accounts) - 1:
            time.sleep(args.delay)

    page.quit()

    print(f"\n{'='*60}")
    print(f"签到完成: {success}/{len(accounts)} 成功")
    print(f"结果保存: {args.results}")

    # 输出统计
    total_points = sum(r.points_earned for r in results)
    print(f"今日总积分: +{total_points}")

if __name__ == "__main__":
    main()
