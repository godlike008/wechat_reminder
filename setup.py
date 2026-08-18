#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信定时提醒——交互式配置向导
引导填写好友备注名、提醒文案、星期、时段，生成 config.json。
支持多好友批量，已有配置会先展示并可逐项修改。

用法:
    python setup.py            # 交互式配置
    python setup.py --preview  # 仅查看当前配置
"""
import argparse
import copy
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

try:
    input = raw_input  # Python 2 兼容（理论上不必要，保险）
except NameError:
    pass

WEEKDAY_MAP = [
    ("1", "周一"),
    ("2", "周二"),
    ("3", "周三"),
    ("4", "周四"),
    ("5", "周五"),
    ("6", "周六"),
    ("7", "周日"),
]

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def load_existing():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"wechat_app_name": "WeChat", "reminders": []}


def save(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("\n✅ 配置已保存到 %s" % CONFIG_PATH)


def ask(prompt, default=None, validator=None):
    while True:
        hint = " [%s]" % default if default is not None else ""
        try:
            raw = input("%s%s: " % (prompt, hint)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n(输入中断)")
            sys.exit(0)
        if not raw and default is not None:
            return default
        if validator is None:
            return raw
        result, msg = validator(raw)
        if result is not None:
            return result
        print("   ⚠️ %s" % msg)


def not_empty(raw):
    if raw:
        return raw, None
    return None, "不能为空"


def valid_time(raw):
    if TIME_RE.match(raw):
        return raw, None
    return None, "时间格式应为 HH:MM（24小时制，如 08:30）"


def ask_time_slot(existing_times):
    """交互添加一个提醒时段，返回新增的 times 列表（含已有）。
    空回车表示结束添加。"""
    times = list(existing_times or [])
    while True:
        print("\n  当前时段: %s" % ("、".join(times) if times else "(无)"))
        raw = ask("  添加时段(HH:MM，直接回车跳过)")
        if not raw:
            break
        if not TIME_RE.match(raw):
            print("   ⚠️ 时间格式应为 HH:MM（24小时制，如 08:30）")
            continue
        if raw in times:
            print("  该时段已存在，跳过")
            continue
        times.append(raw)
    if not times:
        print("  ⚠️ 未设置任何时段，将使用默认 10:00")
        times = ["10:00"]
    return times


def ask_days(existing):
    """选择星期，返回 daily/weekdays/weekends 或星期数组。"""
    print("\n  提醒星期:")
    print("    d) 每天")
    print("    w) 工作日(周一~周五)")
    print("    e) 周末(周六~周日)")
    print("    c) 自定义(逐天勾选)")
    choice = ask("  选择[d/w/e/c]", default="d")
    if choice == "d":
        return "daily"
    if choice == "w":
        return "weekdays"
    if choice == "e":
        return "weekends"
    if choice == "c":
        selected = list(existing) if isinstance(existing, list) else []
        for num, name in WEEKDAY_MAP:
            mark = "✓" if num in selected else " "
            answer = ask("  周%s [%s](y/n)" % (name, mark), default="y" if num in selected else "n")
            if answer.lower() in ("y", "yes", "是"):
                if num not in selected:
                    selected.append(num)
            else:
                if num in selected:
                    selected.remove(num)
        if not selected:
            print("  ⚠️ 未选择任何星期，将按每天处理")
            return "daily"
        return sorted(selected, key=lambda x: int(x))
    print("  无效选择，按每天处理")
    return "daily"


def edit_reminder(r):
    print("\n--- 编辑提醒: %s ---" % r.get("friend", "(未命名)"))
    r["friend"] = ask("好友备注名", default=r.get("friend", ""), validator=not_empty)
    r["message"] = ask("提醒文案", default=r.get("message", "记得吃药啦 💊"))
    r["days"] = ask_days(r.get("days"))
    r["times"] = ask_time_slot(r.get("times", []))
    return r


def add_reminder():
    print("\n--- 添加新提醒 ---")
    r = {}
    r["friend"] = ask("好友备注名", validator=not_empty)
    r["message"] = ask("提醒文案", default="记得吃药啦 💊")
    r["days"] = ask_days(None)
    r["times"] = ask_time_slot([])
    return r


def preview(cfg):
    print("\n========== 当前配置 ==========")
    for i, r in enumerate(cfg.get("reminders", []), 1):
        days = r.get("days", "daily")
        if days == "daily":
            days_txt = "每天"
        elif days == "weekdays":
            days_txt = "工作日(一~五)"
        elif days == "weekends":
            days_txt = "周末(六日)"
        elif isinstance(days, list):
            names = dict(WEEKDAY_MAP)
            days_txt = "周" + "、周".join(names.get(d, d) for d in days)
        else:
            days_txt = str(days)
        print("  %d) %s  %s" % (i, r["friend"], days_txt))
        print("     文案: %s" % r.get("message", ""))
        print("     时段: %s" % "、".join(r.get("times", [])))
    if not cfg.get("reminders"):
        print("  (空)")
    print("================================\n")


def main():
    parser = argparse.ArgumentParser(description="微信定时提醒 配置向导")
    parser.add_argument("--preview", action="store_true", help="仅查看当前配置")
    args = parser.parse_args()

    cfg = load_existing()

    if args.preview:
        preview(cfg)
        return

    print("微信定时提醒 · 配置向导")
    print("========================")
    print("说明：好友备注名必须与微信里的备注完全一致（搜索用）")

    preview(cfg)

    while True:
        print("操作: [a]添加提醒  [e]编辑  [d]删除  [s]保存并退出  [q]放弃")
        choice = ask("请选择", default="s")
        c = choice.lower()
        if c in ("q", "quit", "exit", "放弃"):
            print("已放弃，未做任何更改")
            return
        if c in ("a", "add", "添加"):
            cfg["reminders"].append(add_reminder())
        elif c in ("e", "edit", "编辑"):
            if not cfg["reminders"]:
                print("  ⚠️ 尚无提醒，先添加")
                continue
            idx = ask("要编辑哪个(1~%d)" % len(cfg["reminders"]), default="1")
            try:
                i = int(idx) - 1
                cfg["reminders"][i] = edit_reminder(cfg["reminders"][i])
            except (ValueError, IndexError):
                print("  ⚠️ 序号无效")
        elif c in ("d", "delete", "del", "删除"):
            if not cfg["reminders"]:
                print("  ⚠️ 尚无提醒")
                continue
            idx = ask("要删除哪个(1~%d)" % len(cfg["reminders"]), default="1")
            try:
                i = int(idx) - 1
                removed = cfg["reminders"].pop(i)
                print("  已删除: %s" % removed["friend"])
            except (ValueError, IndexError):
                print("  ⚠️ 序号无效")
        elif c in ("s", "save", "保存"):
            save(cfg)
            print("提示：保存后立即生效（定时任务每分钟自动读取）")
            return
        else:
            print("  ⚠️ 无效选择")
        preview(cfg)


if __name__ == "__main__":
    main()