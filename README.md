# 微信定时提醒（跨平台）

自动发微信消息提醒好友（吃药/复诊/任何事）。**无需网页协议，无封号风险**，走系统 UI 自动化操控微信桌面版。

## 特性 v2

- **多好友批量**：一次配置多个人，各自独立文案
- **每天多次**：每人可设多个时段（如早 8 / 午 14 / 晚 20）
- **按星期调度**：`daily` / `weekdays` / `weekends` / 指定星期数组
- **防重复**：状态文件保证同一天同一时段只发一次
- **可靠性**：自检、自动启动微信、失败重试、UI 验证、锁屏处理

## 目录

```
wechat_reminder/
├── config.json            # 参数配置（含隐私，不入库）
├── config.example.json    # 配置示例（可克隆）
├── gui.py                 # 图形配置界面 (Tkinter)
├── setup.py               # 交互式命令行配置向导
├── send_reminder.py       # 发送核心（macOS + Windows 通用）
├── install_schedule.py    # 注册/卸载定时任务
├── reminder.log           # 发送日志（自动生成）
└── reminder_state.json    # 发送状态（自动生成，防重复）
```

## 快速开始（两台平台都只需 3 步）

### 1. 配置参数

**图形界面配置**（推荐，零依赖，macOS/Windows 通用）：

```bash
python gui.py
```

窗口内可添加/编辑/删除提醒、勾选星期、管理多个时段，点保存即写入 `config.json`。

也可以复制示例手动编辑：

```bash
cp config.example.json config.json
```

```json
{
  "wechat_app_name": "WeChat",
  "reminders": [
    {
      "friend": "我宝",
      "message": "记得吃药啦 💊",
      "days": "daily",
      "times": ["08:00", "14:00", "20:00"]
    },
    {
      "friend": "妈妈",
      "message": "该量血压了 🩺",
      "days": ["1", "3", "5"],
      "times": ["09:00"]
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `reminders[].friend` | 好友在微信里的**备注名**（搜索用） |
| `reminders[].message` | 提醒文案（支持中文/emoji） |
| `reminders[].days` | `daily`=每天；`weekdays`=周一~五；`weekends`=六日；或数组 `[1..7]`（1=周一） |
| `reminders[].times` | 每天触发时段数组，24 小时制 `HH:MM`，可多个 |

> 改配置后**无需重装定时任务**——任务每分钟检查一次配置。

### 2. 首次授权（一次性）

> 操控微信需要系统的"辅助功能/UI 自动化"权限。

- **macOS**：系统设置 → 隐私与安全性 → 辅助功能 → 勾选运行本脚本的终端或 Python 宿主（如 OpenCode.app）。**必须重启该应用后生效。**
- **Windows**：安装 uiautomation 库即可，无需额外系统授权：
  ```bat
  pip install uiautomation
  ```

### 3. 测试发送 + 注册定时任务

```bash
# 先手动测试发一条（确认参数和权限 OK）
python send_reminder.py

# 手动发送给指定好友（覆盖配置）
python send_reminder.py -n 我宝 -m "记得吃药啦 💊"

# 注册定时任务（每分钟检查一次配置，改配置无需重装）
python install_schedule.py

# 卸载定时任务
python install_schedule.py --uninstall
```

## 原理

| 系统 | 方案 | 步骤 |
|------|------|------|
| macOS | AppleScript + System Events | `Cmd+F` 搜索好友 → 剪贴板粘贴昵称 → 回车进会话 → 粘贴文案 → 回车发送 |
| Windows | uiautomation 库 | 定位微信主窗口 → 搜索框输入昵称 → 回车进会话 → 粘贴文案 → 回车发送 |

中文/emoji 一律通过**系统剪贴板**粘贴，避免按键编码问题，这是最稳的方式。

## 定时机制

定时任务**每分钟**触发一次 `send_reminder.py --scheduled`，脚本判断当前时刻是否落在某提醒的时段内（±5 分钟容差），并用 `reminder_state.json` 防止同一天同一时段重复发送。

| 系统 | 机制 | 管理方式 |
|------|------|----------|
| macOS | launchd (`~/Library/LaunchAgents/com.wechat.reminder.plist`, `StartInterval=60`) | `launchctl list \| grep wechat` |
| Windows | 任务计划程序（任务名 `WeChatMedicineReminder`, 每分钟） | 控制面板 → 管理工具 → 任务计划程序 |

> 因为任务每分钟检查，**修改 `config.json`（加好友/改时间/换文案）即时生效，无需重装任务**。

## 可靠性设计（已内置）

| 能力 | 实现 |
|------|------|
| 发送前自检 | 微信未运行则自动启动（macOS: `launch`；Windows: `Run`） |
| 失败重试 | 最多重试 3 次，间隔 2 秒 |
| 结果验证 | 发送后读取 UI 树，确认会话已打开、剪贴板已被消费 |
| 锁屏处理 | 检测锁屏则等待解锁（最多 4 小时，每 15 秒轮询）再发送 |
| 防重复 | 状态文件记录 `好友|日期|时段`，同一天同一时段只发一次 |
| 剪贴板还原 | 尽力还原用户原有剪贴板内容 |

## 注意事项（重要）

1. **微信必须保持登录**，且电脑**不要锁屏**（锁屏时 UI 自动化无法点击）。定时模式遇锁屏会跳过本次，解锁后下一分钟补发。
2. 任务在**当前用户会话**下运行，需保持登录态。
3. Windows 的 uiautomation 适配微信 3.x 桌面版；若微信更新导致定位失败，可能需要调整 `send_reminder.py` 中的控件查找参数。
4. 发送记录写入 `reminder.log`，排查问题先看它。
5. macOS 下若脚本由 launchd 调用，辅助功能权限需授予 `/usr/bin/osascript` 或对应的 Python 解释器所在应用。
6. **已知限制**：实测 macOS 微信激活后会**持续清空系统剪贴板**，故发送期间用户剪贴板内容通常无法还原（脚本会记录警告，不影响发送主流程）。
7. **验证兜底**：若 UI 树读取失败（读不到消息气泡文本），脚本不会误判失败，会以会话标题 + 剪贴板信号为准。