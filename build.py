#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本——生成免 Python 的可执行程序。

macOS: 生成 ./dist/wechat-reminder 可执行文件
Windows: 生成 ./dist/wechat-reminder.exe

用法:
    pip install pyinstaller
    python build.py
"""
import os
import platform
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")


def run(args):
    print(">>>", " ".join(args))
    subprocess.run(args, check=True)


def pyinstaller_cmd():
    """返回可用的 pyinstaller 调用方式（优先 -m PyInstaller 保证 venv 可用）。"""
    try:
        import PyInstaller  # noqa
        return [sys.executable, "-m", "PyInstaller"]
    except ImportError:
        return ["pyinstaller"]


def main():
    pi = pyinstaller_cmd()

    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

    is_win = platform.system() == "Windows"
    console_flag = "--console"

    # 打包 GUI 配置界面
    run(pi + [
        "--onefile",
        console_flag,
        "--name", "wechat-gui",
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        "--specpath", BASE_DIR,
        "--clean",
        os.path.join(BASE_DIR, "gui.py"),
    ])

    # 打包发送核心（同时承担 --scheduled 调度入口）
    run(pi + [
        "--onefile",
        console_flag,
        "--name", "wechat-send",
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        "--specpath", BASE_DIR,
        "--clean",
        os.path.join(BASE_DIR, "send_reminder.py"),
    ])

    # 打包任务注册器
    run(pi + [
        "--onefile",
        console_flag,
        "--name", "wechat-install",
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        "--specpath", BASE_DIR,
        "--clean",
        os.path.join(BASE_DIR, "install_schedule.py"),
    ])

    # 附带示例配置（用户复制为 config.json）
    shutil.copy(
        os.path.join(BASE_DIR, "config.example.json"),
        os.path.join(DIST_DIR, "config.example.json"),
    )

    # 附带说明
    with open(os.path.join(DIST_DIR, "使用说明.txt"), "w", encoding="utf-8") as f:
        f.write(
            "微信定时提醒 · 打包版使用说明\n"
            "============================\n\n"
            "1. 首次使用: 运行 wechat-gui 配置好友/文案/时间\n"
            "2. 手动测试: 运行 wechat-send\n"
            "3. 注册定时: 运行 wechat-install (卸载加 --uninstall)\n\n"
            "注意:\n"
            "- 所有程序都从所在目录读取 config.json, 请保持这几个文件在同一文件夹\n"
            "- 微信需保持登录, 电脑不要锁屏\n"
            "- macOS 需在 系统设置-隐私与安全性-辅助功能 授权运行程序\n"
            "- 免装 Python, 直接双击运行\n"
        )

    print("\n打包完成 → %s" % DIST_DIR)
    for name in os.listdir(DIST_DIR):
        print("  -", name)


if __name__ == "__main__":
    main()