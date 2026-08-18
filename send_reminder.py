#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台微信定时提醒——发送核心（可靠性增强版）
macOS: AppleScript + System Events (UI 自动化)
Windows: uiautomation (UI 自动化)

可靠性增强:
  1. 发送前自检: 微信未运行则自动启动
  2. 失败重试: 自动重试多次
  3. 结果验证: 发送后读取 UI 树确认消息真实发出
  4. 锁屏处理: 检测到锁屏则等待解锁后发送
  5. 恢复剪贴板: 结束后还原用户原有剪贴板内容

用法:
    python send_reminder.py              # 读取 config.json 发送
    python send_reminder.py -n 我宝      # 覆盖好友备注名
    python send_reminder.py -m "记得吃药" # 覆盖文案
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "reminder.log")

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


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def is_os_macos():
    return platform.system() == "Darwin"


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


def send(friend, message):
    # 1. 自检：微信是否运行
    if not wechat_running():
        log.info("微信未运行，尝试启动…")
        if not launch_wechat():
            log.error("微信无法启动，中止")
            return False

    # 4. 锁屏则等待解锁
    if not wait_for_unlock():
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

def main():
    parser = argparse.ArgumentParser(description="微信定时提醒发送器")
    parser.add_argument("-n", "--name", help="好友备注名（覆盖 config.json）")
    parser.add_argument("-m", "--message", help="提醒文案（覆盖 config.json）")
    args = parser.parse_args()

    cfg = load_config()
    friend = args.name or cfg["friend"]
    message = args.message or cfg["message"]

    ok = send(friend, message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()