#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台微信定时提醒——注册/卸载定时任务 v2
调度策略: 每分钟触发一次 send_reminder.py --scheduled，
脚本自身判断"当前时刻是否匹配各好友的时段"并防重复，
因此改 config.json 无需重装定时任务。

macOS:   launchd (StartInterval=60)
Windows: 任务计划程序 (schtasks /SC MINUTE /MO 1)

用法:
    python install_schedule.py            # 注册
    python install_schedule.py --uninstall
"""
import argparse
import os
import platform
import subprocess
import sys


def _program_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _program_dir()
# 打包后调度同目录的 wechat-send 可执行文件(带 --scheduled);
# 源码模式调度 send_reminder.py
if getattr(sys, "frozen", False):
    exe_name = "wechat-send.exe" if platform.system() == "Windows" else "wechat-send"
    SCRIPT_PATH = os.path.join(BASE_DIR, exe_name)
else:
    SCRIPT_PATH = os.path.join(BASE_DIR, "send_reminder.py")
LABEL = "com.wechat.reminder"
WIN_TASK_NAME = "WeChatMedicineReminder"


# ---------------- macOS: launchd ----------------

def install_macos():
    plist_path = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % LABEL)
    python_bin = sys.executable or "/usr/bin/python3"

    plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>%s</string>
    <key>ProgramArguments</key>
    <array>
        <string>%s</string>
        <string>%s</string>
        <string>--scheduled</string>
    </array>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>%s/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>%s/stderr.log</string>
</dict>
</plist>
""" % (LABEL, python_bin, SCRIPT_PATH, BASE_DIR, BASE_DIR)

    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(plist)

    subprocess.run(["launchctl", "unload", plist_path], capture_output=True)
    subprocess.run(["launchctl", "load", plist_path], check=True)
    print("macOS: 定时任务已注册(每分钟检查一次)")
    print("       plist: %s" % plist_path)
    return True


def uninstall_macos():
    plist_path = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % LABEL)
    subprocess.run(["launchctl", "unload", plist_path], capture_output=True)
    if os.path.exists(plist_path):
        os.remove(plist_path)
    print("macOS: 定时任务已卸载")
    return True


# ---------------- Windows: schtasks ----------------

def install_windows():
    cmd = [
        "schtasks", "/Create", "/TN", WIN_TASK_NAME,
        "/SC", "MINUTE", "/MO", "1",
        "/TR", '"%s" "%s" --scheduled' % (sys.executable, SCRIPT_PATH),
        "/F",
    ]
    subprocess.run(cmd, check=True)
    print("Windows: 定时任务已注册(每分钟检查一次)")
    print("       任务名: %s (可在 任务计划程序 中查看)" % WIN_TASK_NAME)
    return True


def uninstall_windows():
    subprocess.run(["schtasks", "/Delete", "/TN", WIN_TASK_NAME, "/F"],
                   capture_output=True)
    print("Windows: 定时任务已卸载")
    return True


def main():
    parser = argparse.ArgumentParser(description="微信定时提醒 任务注册器 v2")
    parser.add_argument("--uninstall", action="store_true", help="卸载定时任务")
    args = parser.parse_args()

    system = platform.system()

    if args.uninstall:
        if system == "Darwin":
            uninstall_macos()
        elif system == "Windows":
            uninstall_windows()
        else:
            print("不支持的系统: %s" % system)
            sys.exit(1)
    else:
        if system == "Darwin":
            install_macos()
        elif system == "Windows":
            install_windows()
        else:
            print("不支持的系统: %s" % system)
            sys.exit(1)


if __name__ == "__main__":
    main()