#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信定时提醒——GUI 配置界面 (Tkinter, 零依赖跨平台)
macOS/Windows 均可运行, 仅需系统自带 tkinter。

用法:
    python gui.py            # 打开图形配置界面
"""
import json
import os
import re
import sys
import tkinter as tk
from tkinter import messagebox, ttk


def _program_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _program_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
DAYS_PRESETS = [
    ("每天", "daily"),
    ("工作日", "weekdays"),
    ("周末", "weekends"),
]


def load_existing():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"wechat_app_name": "WeChat", "reminders": []}


def save(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def parse_days(days):
    """把 days 配置转成勾选状态。返回 (preset_index, [bool x7])。"""
    checks = [False] * 7
    preset = 0
    if days == "weekdays":
        preset = 1
        checks = [True] * 5 + [False] * 2
    elif days == "weekends":
        preset = 2
        checks = [False] * 5 + [True] * 2
    elif isinstance(days, list):
        preset = -1  # 自定义
        for d in days:
            try:
                checks[int(d) - 1] = True
            except Exception:
                pass
    return preset, checks


def days_to_cfg(preset, checks):
    """把界面状态转成 days 配置。"""
    if preset == 0:
        return "daily"
    if preset == 1:
        return "weekdays"
    if preset == 2:
        return "weekends"
    return [str(i + 1) for i, on in enumerate(checks) if on]


class ReminderDialog(tk.Toplevel):
    """单个提醒的编辑弹窗。"""

    def __init__(self, master, reminder=None, title="添加提醒"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        r = reminder or {"friend": "", "message": "", "days": "daily", "times": []}

        preset, checks = parse_days(r.get("days", "daily"))

        pad = {"padx": 8, "pady": 4}
        tk.Label(self, text="好友备注名(与微信备注一致)").grid(row=0, column=0, sticky="w", **pad)
        self.friend = tk.Entry(self, width=30)
        self.friend.insert(0, r.get("friend", ""))
        self.friend.grid(row=0, column=1, **pad)

        tk.Label(self, text="提醒文案").grid(row=1, column=0, sticky="w", **pad)
        self.message = tk.Entry(self, width=30)
        self.message.insert(0, r.get("message", "记得吃药啦 💊"))
        self.message.grid(row=1, column=1, **pad)

        tk.Label(self, text="提醒星期").grid(row=2, column=0, sticky="nw", **pad)
        frame_days = tk.Frame(self)
        frame_days.grid(row=2, column=1, sticky="w", **pad)
        self.day_vars = [tk.BooleanVar(value=on) for on in checks]
        day_row = tk.Frame(frame_days)
        day_row.pack(anchor="w")
        for i, name in enumerate(WEEKDAY_NAMES):
            tk.Checkbutton(day_row, text=name, variable=self.day_vars[i]).pack(side="left")
        preset_row = tk.Frame(frame_days)
        preset_row.pack(anchor="w", pady=(4, 0))
        self.preset_var = tk.IntVar(value=preset if preset >= 0 else 0)
        for i, (label, _) in enumerate(DAYS_PRESETS):
            rb = tk.Radiobutton(preset_row, text=label, value=i, variable=self.preset_var)
            rb.pack(side="left")

        tk.Label(self, text="提醒时段(24小时制)").grid(row=3, column=0, sticky="nw", **pad)
        frame_time = tk.Frame(self)
        frame_time.grid(row=3, column=1, sticky="w", **pad)
        self.time_list = tk.Listbox(frame_time, width=18, height=3)
        self.time_list.pack(side="left")
        for t in r.get("times", []):
            self.time_list.insert("end", t)
        btn_frame = tk.Frame(frame_time)
        btn_frame.pack(side="left", padx=(6, 0))
        tk.Button(btn_frame, text="添加", width=6, command=self.add_time).pack(pady=2)
        tk.Button(btn_frame, text="删除", width=6, command=self.del_time).pack(pady=2)
        self.time_entry = tk.Entry(frame_time, width=10)
        self.time_entry.pack(pady=(4, 0))

        btns = tk.Frame(self)
        btns.grid(row=4, column=0, columnspan=2, pady=10)
        tk.Button(btns, text="保存", width=8, command=self.on_ok).pack(side="left", padx=6)
        tk.Button(btns, text="取消", width=8, command=self.destroy).pack(side="left", padx=6)

        self.transient(master)
        self.grab_set()
        self.bind("<Return>", lambda e: self.on_ok())
        self.friend.focus_set()
        self.wait_window()

    def add_time(self):
        raw = self.time_entry.get().strip()
        if not TIME_RE.match(raw):
            messagebox.showerror("格式错误", "时间应为 HH:MM（24小时制，如 08:30）", parent=self)
            return
        if raw in list(self.time_list.get(0, "end")):
            messagebox.showinfo("提示", "该时段已存在", parent=self)
            return
        self.time_list.insert("end", raw)
        self.time_entry.delete(0, "end")

    def del_time(self):
        sel = self.time_list.curselection()
        if sel:
            self.time_list.delete(sel[0])

    def on_ok(self):
        friend = self.friend.get().strip()
        if not friend:
            messagebox.showerror("错误", "好友备注名不能为空", parent=self)
            return
        checks = [v.get() for v in self.day_vars]
        days = days_to_cfg(self.preset_var.get(), checks)
        times = list(self.time_list.get(0, "end"))
        if not times:
            messagebox.showerror("错误", "请至少添加一个提醒时段", parent=self)
            return
        self.result = {
            "friend": friend,
            "message": self.message.get().strip() or "记得吃药啦 💊",
            "days": days,
            "times": times,
        }
        self.destroy()


class ConfigApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("微信定时提醒 · 配置")
        self.geometry("520x460")
        self.minsize(480, 400)
        self.cfg = load_existing()
        self._build()

    def _build(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))
        tk.Button(toolbar, text="添加提醒", command=self.add).pack(side="left", padx=2)
        tk.Button(toolbar, text="编辑", command=self.edit).pack(side="left", padx=2)
        tk.Button(toolbar, text="删除", command=self.delete).pack(side="left", padx=2)
        tk.Button(toolbar, text="保存", command=self.on_save).pack(side="left", padx=2)
        tk.Button(toolbar, text="预览", command=self.preview).pack(side="left", padx=2)

        self.tree = ttk.Treeview(self, columns=("friend", "days", "times", "msg"),
                                 show="headings", selectmode="browse")
        for col, text, width in (
            ("friend", "好友", 90),
            ("days", "星期", 100),
            ("times", "时段", 120),
            ("msg", "文案", 180),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.refresh()

    def _days_text(self, days):
        if days == "weekdays":
            return "工作日"
        if days == "weekends":
            return "周末"
        if isinstance(days, list):
            names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            return "、".join(names[int(d)] for d in days if str(d).isdigit())
        return "每天"

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.cfg.get("reminders", []):
            self.tree.insert("", "end", values=(
                r.get("friend", ""),
                self._days_text(r.get("days", "daily")),
                "、".join(r.get("times", [])),
                r.get("message", ""),
            ))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = self.tree.index(sel[0])
        reminders = self.cfg.get("reminders", [])
        if 0 <= idx < len(reminders):
            return idx
        return None

    def add(self):
        dlg = ReminderDialog(self, title="添加提醒")
        if dlg.result:
            self.cfg.setdefault("reminders", []).append(dlg.result)
            self.refresh()

    def edit(self):
        idx = self._selected()
        if idx is None:
            messagebox.showinfo("提示", "请先在列表中选择一项")
            return
        dlg = ReminderDialog(self, self.cfg["reminders"][idx], title="编辑提醒")
        if dlg.result:
            self.cfg["reminders"][idx] = dlg.result
            self.refresh()

    def delete(self):
        idx = self._selected()
        if idx is None:
            messagebox.showinfo("提示", "请先在列表中选择一项")
            return
        name = self.cfg["reminders"][idx].get("friend", "")
        if messagebox.askyesno("确认", "删除对 %s 的提醒？" % name):
            del self.cfg["reminders"][idx]
            self.refresh()

    def preview(self):
        lines = []
        for i, r in enumerate(self.cfg.get("reminders", []), 1):
            lines.append("%d) %s | %s | %s | %s" % (
                i,
                r.get("friend", ""),
                self._days_text(r.get("days", "daily")),
                "、".join(r.get("times", [])),
                r.get("message", ""),
            ))
        messagebox.showinfo("当前配置", "\n".join(lines) if lines else "(空)")

    def on_save(self):
        try:
            save(self.cfg)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        messagebox.showinfo("已保存", "配置已写入 config.json\n定时任务每分钟自动读取，立即生效")


def main():
    app = ConfigApp()
    app.mainloop()


if __name__ == "__main__":
    main()