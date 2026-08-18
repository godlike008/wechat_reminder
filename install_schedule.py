#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台微信定时提醒——注册/卸载定时任务
macOS:   launchd (LaunchAgents plist)
Windows: 任务计划程序 (schtasks)

用法:
    python install_schedule.py            # 注册（读取 config.json 的时间）
    python install_schedule.py --uninstall
"""
import argparse
import json
import os
import platform
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SCRIPT_PATH = os.path.join(BASE_DIR, "send_reminder.py")
LABEL = "com.wechat.reminder"
WIN_TASK_NAME = "WeChatMedicineReminder"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------- macOS: launchd ----------------

def install_macos(schedule_time):
    hour, minute = schedule_time.split(":")
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
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>%d</integer>
        <key>Minute</key>
        <integer>%d</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>%s/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>%s/stderr.log</string>
</dict>
</plist>
""" % (LABEL, python_bin, SCRIPT_PATH, int(hour), int(minute), BASE_DIR, BASE_DIR)

    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(plist)

    subprocess.run(["launchctl", "unload", plist_path],
                   capture_output=True)
    subprocess.run(["launchctl", "load", plist_path], check=True)
    print("macOS: 定时任务已注册 -> 每天 %s" % schedule_time)
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

def install_windows(schedule_time):
    cmd = [
        "schtasks", "/Create", "/TN", WIN_TASK_NAME,
        "/SC", "DAILY", "/ST", schedule_time,
        "/TR", '"%s" "%s"' % (sys.executable, SCRIPT_PATH),
        "/F",
    ]
    subprocess.run(cmd, check=True)
    print("Windows: 定时任务已注册 -> 每天 %s" % schedule_time)
    print("       任务名: %s (可在 任务计划程序 中查看)" % WIN_TASK_NAME)
    return True


def uninstall_windows():
    subprocess.run(["schtasks", "/Delete", "/TN", WIN_TASK_NAME, "/F"],
                   capture_output=True)
    print("Windows: 定时任务已卸载")
    return True


def main():
    parser = argparse.ArgumentParser(description="微信定时提醒 任务注册器")
    parser.add_argument("--uninstall", action="store_true", help="卸载定时任务")
    args = parser.parse_args()

    system = platform.system()
    cfg = load_config()
    schedule_time = cfg.get("schedule_time", "10:00")

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
            install_macos(schedule_time)
        elif system == "Windows":
            install_windows(schedule_time)
        else:
            print("不支持的系统: %s" % system)
            sys.exit(1)


if __name__ == "__main__":
    main()