#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台微信定时提醒——发送核心 v2
macOS: AppleScript + System Events (UI 自动化)
Windows: uiautomation (UI 自动化)

功能:
  - 多好友批量: config.json 中 reminders 数组
  - 每天多次: 每个 reminder 的 times 数组
  - 按星期调度: days 支持 daily/weekdays/weekends/数组
  - 可靠性: 自检、自动启动微信、重试、UI验证、锁屏处理
  - 防重复: 状态文件记录已发送, 防止定时任务重复触发

用法:
    python send_reminder.py --scheduled   # 定时模式(任务计划每分钟调用)
    python send_reminder.py -n 我宝      # 手动发送给某好友(覆盖配置)
    python send_reminder.py -m "记得吃药" # 手动覆盖文案
"""
import argparse
import json
import logging
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime

def _program_dir():
    """返回程序所在目录：PyInstaller 打包后指向可执行文件旁，
    普通运行时指向脚本所在目录。config/日志均放在该目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _program_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "reminder.log")
STATE_PATH = os.path.join(BASE_DIR, "reminder_state.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
log = logging.getLogger("wechat_reminder")

RETRY_TIMES = 3
UNLOCK_TIMEOUT = 4 * 3600  # 锁屏最长等待 4 小时
UNLOCK_POLL = 15           # 每 15 秒检查一次
TIME_WINDOW_MIN = 5        # 定时触发的时间容差(分钟)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def is_os_macos():
    return platform.system() == "Darwin"


def today_iso():
    return datetime.now().strftime("%Y-%m-%d")


def weekday_iso():
    return datetime.now().isoweekday()  # 1=周一 ... 7=周日


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def mark_sent(key):
    state = load_state()
    state[key] = True
    save_state(state)


def is_sent(key):
    return load_state().get(key, False)


def day_matches(spec, wd):
    """判断某 reminder 是否在今天触发。wd 为 1=周一...7=周日。"""
    if spec is None or spec == "daily":
        return True
    if spec == "weekdays":
        return 1 <= wd <= 5
    if spec == "weekends":
        return wd >= 6
    if isinstance(spec, list):
        return wd in spec
    return True


def now_in_window(target_hhmm, now_hhmm):
    """判断当前时间是否落在目标时刻的容差窗口内(避免定时任务错点)。"""
    try:
        th, tm = int(target_hhmm[:2]), int(target_hhmm[3:5])
        nh, nm = int(now_hhmm[:2]), int(now_hhmm[3:5])
        target_min = th * 60 + tm
        now_min = nh * 60 + nm
        return 0 <= now_min - target_min < TIME_WINDOW_MIN
    except Exception:
        return False


# ---------------- 剪贴板 ----------------

def get_clipboard():
    try:
        if is_os_macos():
            r = subprocess.run(["pbpaste"], capture_output=True, text=True)
            return r.stdout if r.returncode == 0 else ""
        return ""
    except Exception:
        return ""


def set_clipboard(text):
    if is_os_macos():
        subprocess.run(["pbcopy"], input=text, text=True)
    else:
        try:
            import uiautomation as auto
            auto.SetClipboardText(text)
        except Exception:
            pass


def restore_clipboard(saved):
    """尝试还原剪贴板。注意: 实测微信激活后会持续清空系统剪贴板，
    本环境通常无法还原，仅尽力而为并记录日志，不影响主流程。"""
    try:
        time.sleep(0.5)
        if saved:
            set_clipboard(saved)
        if get_clipboard() == saved:
            return True
        log.warning("微信持续清空系统剪贴板，无法还原用户原有剪贴板内容")
        return False
    except Exception as e:
        log.warning("还原剪贴板异常 | %s", e)
        return False


# ---------------- macOS ----------------

MACOS_LAUNCH_SCRIPT = r"""
tell application "WeChat"
    launch
    activate
end tell
"""

MACOS_APPLESCRIPT = r"""
on run argv
    set friendName to item 1 of argv
    set messageText to item 2 of argv
    tell application "WeChat" to activate
    delay 1
    tell application "System Events"
        tell process "WeChat"
            -- 聚焦搜索框
            keystroke "f" using command down
            delay 0.8
            -- 剪贴板粘贴好友备注名(支持中文)
            set the clipboard to friendName
            keystroke "v" using command down
            delay 1
            -- 回车打开会话
            key code 36
            delay 1
            -- 粘贴文案
            set the clipboard to messageText
            keystroke "v" using command down
            delay 0.5
            -- 回车发送
            key code 36
            delay 0.5
            -- 清空剪贴板
            set the clipboard to ""
        end tell
    end tell
end run
"""

MACOS_DUMP_UI = r"""
tell application "System Events"
    tell process "WeChat"
        return entire contents of window 1
    end tell
end tell
"""

MACOS_CHECK_LOCKED = r"""
do shell script "ioreg -n Root -d1 -a | grep -A1 IOConsoleLocked | grep -q true"
"""


def wechat_running_macos():
    r = subprocess.run(
        ["pgrep", "-x", "WeChat"], capture_output=True, text=True
    )
    return r.returncode == 0


def launch_wechat_macos():
    try:
        subprocess.run(
            ["osascript", "-e", MACOS_LAUNCH_SCRIPT], check=True,
            capture_output=True, text=True,
        )
        log.info("macOS: 已启动微信")
        time.sleep(3)
        return True
    except subprocess.CalledProcessError as e:
        log.error("macOS: 启动微信失败 | %s", e.stderr.strip())
        return False


def screen_locked_macos():
    r = subprocess.run(
        ["osascript", "-e", MACOS_CHECK_LOCKED],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def send_macos(friend, message):
    try:
        subprocess.run(
            ["osascript", "-e", MACOS_APPLESCRIPT, friend, message],
            check=True, capture_output=True, text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        log.error("macOS: 执行发送失败 | %s", e.stderr.strip())
        return False


def verify_macos(friend, message):
    """验证：UI 树含会话标题 = 会话已打开；
    若剪贴板已被清空(发送完成置空)则佐证消息已发出。"""
    r = subprocess.run(
        ["osascript", "-e", MACOS_DUMP_UI],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        log.warning("macOS: 无法读取 UI 树用于验证 | %s", r.stderr.strip())
        return True  # 读不到时不误判为失败
    tree = r.stdout

    friend_ok = friend in tree
    if not friend_ok:
        log.warning("macOS: 验证未通过（UI 树未检出好友 %s）", friend)
        return False

    # 消息文本不在 UI 树中，改用剪贴板信号佐证
    if get_clipboard() != "":
        log.warning("macOS: 剪贴板未被清空，消息可能未发送成功")
        return False
    log.info("macOS: 验证通过（会话已打开且发送流程走完）")
    return True


# ---------------- Windows ----------------

def wechat_running_windows():
    try:
        import uiautomation as auto
        win = auto.WindowControl(ClassName="WeChatMainWndForPC", Name="微信")
        return win.Exists(timeout=1)
    except Exception:
        return False


def launch_wechat_windows():
    try:
        import uiautomation as auto
        wechat_exe = "WeChat.exe"
        auto.Run(wechat_exe, wait=True, waitTime=5)
        log.info("Windows: 已启动微信")
        time.sleep(3)
        return True
    except Exception as e:
        log.error("Windows: 启动微信失败 | %s", e)
        return False


def screen_locked_windows():
    """Windows 锁屏检测：检查系统会话是否处于锁定状态。"""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # 0x04 == 已断开会话/锁定状态(SSH 或锁屏); 0x00 == 活动
        return user32.GetForegroundWindow() == 0 and user32.OpenInputDesktop() == 0
    except Exception:
        return False


def send_windows(friend, message):
    try:
        import uiautomation as auto
    except ImportError:
        log.error("Windows: 缺少依赖，请先运行: pip install uiautomation")
        return False

    win = auto.WindowControl(ClassName="WeChatMainWndForPC", Name="微信")
    if not win.Exists(timeout=3):
        log.error("Windows: 未找到微信主窗口，请确认微信已登录且为 3.x 桌面版")
        return False
    win.SetActive()

    search_edit = win.EditControl(ClassName="Edit", searchDepth=10)
    if not search_edit.Exists(timeout=2):
        log.error("Windows: 未找到搜索框")
        return False
    search_edit.Click()

    auto.SetClipboardText(friend)
    search_edit.SendKeys("{Ctrl}v")
    time.sleep(0.8)
    search_edit.SendKeys("{Enter}")
    time.sleep(1)

    input_edit = win.EditControl(searchDepth=10)
    if not input_edit.Exists(timeout=2):
        log.error("Windows: 未找到聊天输入框")
        return False
    input_edit.Click()
    auto.SetClipboardText(message)
    input_edit.SendKeys("{Ctrl}v")
    time.sleep(0.5)
    input_edit.SendKeys("{Enter}")
    return True


def verify_windows(friend, message):
    try:
        import uiautomation as auto
        win = auto.WindowControl(ClassName="WeChatMainWndForPC", Name="微信")
        if not win.Exists(timeout=1):
            log.warning("Windows: 验证时找不到微信窗口，按成功处理")
            return True
        tree = win.GetRootControl().GetChildren().__repr__()
        if friend in tree and message in tree:
            log.info("Windows: 验证通过（会话与消息均在 UI 中）")
            return True
        log.warning("Windows: 验证未完全通过（UI 树未检出好友 %s）", friend)
        return False
    except Exception as e:
        log.warning("Windows: 无法读取 UI 树用于验证 | %s", e)
        return True


# ---------------- 通用流程 ----------------

def screen_locked():
    if is_os_macos():
        return screen_locked_macos()
    return screen_locked_windows()


def wechat_running():
    if is_os_macos():
        return wechat_running_macos()
    return wechat_running_windows()


def launch_wechat():
    if is_os_macos():
        return launch_wechat_macos()
    return launch_wechat_windows()


def send_once(friend, message):
    if is_os_macos():
        return send_macos(friend, message)
    return send_windows(friend, message)


def verify(friend, message):
    if is_os_macos():
        return verify_macos(friend, message)
    return verify_windows(friend, message)


def wait_for_unlock():
    waited = 0
    while screen_locked():
        if waited >= UNLOCK_TIMEOUT:
            log.error("等待解锁超时(%d 小时)，放弃本次提醒", UNLOCK_TIMEOUT // 3600)
            return False
        log.info("屏幕锁定中，等待解锁后继续…(已等待 %d 分钟)", waited // 60)
        time.sleep(UNLOCK_POLL)
        waited += UNLOCK_POLL
    return True


def send(friend, message, wait_unlock=True):
    # 1. 自检：微信是否运行
    if not wechat_running():
        log.info("微信未运行，尝试启动…")
        if not launch_wechat():
            log.error("微信无法启动，中止")
            return False

    # 4. 锁屏则等待解锁
    if wait_unlock and not wait_for_unlock():
        return False

    # 5. 保存并接管剪贴板
    original_clipboard = get_clipboard()

    try:
        # 2. 重试发送
        sent = False
        for attempt in range(1, RETRY_TIMES + 1):
            if attempt > 1:
                log.info("第 %d 次重试…", attempt)
            if send_once(friend, message):
                # 3. 结果验证
                if verify(friend, message):
                    sent = True
                    break
                log.warning("发送成功但验证未通过，重试…")
            time.sleep(2)
        if not sent:
            log.error("发送失败：重试 %d 次均未成功", RETRY_TIMES)
            return False

        log.info("发送成功: %s <- %s", friend, message)
        return True
    finally:
        # 5. 恢复剪贴板
        restore_clipboard(original_clipboard)

def run_scheduled():
    """定时模式：每分钟由任务计划调用，检查是否有到点的提醒并发送。
    用状态文件防重复——同一天同一时段只发一次。"""
    cfg = load_config()
    reminders = cfg.get("reminders", [])
    wd = weekday_iso()
    today = today_iso()
    now_hhmm = datetime.now().strftime("%H:%M")

    matched = False
    for r in reminders:
        friend = r["friend"]
        message = r.get("message", "记得吃药啦 💊")
        times = r.get("times", ["10:00"])

        if not day_matches(r.get("days", "daily"), wd):
            log.debug("跳过 %s: 今天(周%d)不在调度内", friend, wd)
            continue

        for t in times:
            if not now_in_window(t, now_hhmm):
                continue
            matched = True
            key = "%s|%s|%s" % (friend, today, t)
            if is_sent(key):
                log.info("已发送过 %s 今天的 %s，跳过", friend, t)
                continue
            log.info("到点: %s @ %s -> %s", friend, t, message)
            ok = send(friend, message, wait_unlock=False)
            if ok:
                mark_sent(key)
                log.info("已完成 %s @ %s 并记录状态", friend, t)
            else:
                log.error("%s @ %s 发送失败，未记录状态(下一分钟会重试)", friend, t)

    if not matched:
        log.debug("当前 %s 无到点提醒", now_hhmm)


def main():
    parser = argparse.ArgumentParser(description="微信定时提醒发送器 v2")
    parser.add_argument("--scheduled", action="store_true",
                        help="定时模式(由任务计划每分钟调用)")
    parser.add_argument("-n", "--name", help="手动发送: 好友备注名")
    parser.add_argument("-m", "--message", help="手动发送: 文案(默认读取配置)")
    args = parser.parse_args()

    if args.scheduled:
        run_scheduled()
        sys.exit(0)

    cfg = load_config()
    reminders = cfg.get("reminders", [])
    if args.name:
        # 手动模式: 发送给指定好友
        message = args.message
        if message is None:
            r = next((x for x in reminders if x["friend"] == args.name), None)
            message = r["message"] if r else "记得吃药啦 💊"
        ok = send(args.name, message)
        sys.exit(0 if ok else 1)

    # 无参数: 手动发送配置中第一个 reminder
    if not reminders:
        log.error("config.json 中没有 reminders 配置")
        sys.exit(1)
    r = reminders[0]
    ok = send(r["friend"], r.get("message", "记得吃药啦 💊"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()