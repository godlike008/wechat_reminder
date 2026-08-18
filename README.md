# 微信定时提醒（跨平台）

每天定时自动发微信消息提醒好友吃药。**无需网页协议，无封号风险**，走系统 UI 自动化操控微信桌面版。

## 目录

```
wechat_reminder/
├── config.json            # 参数配置：好友备注名 / 文案 / 时间
├── send_reminder.py       # 发送核心（macOS + Windows 通用）
├── install_schedule.py    # 注册/卸载定时任务
└── reminder.log           # 发送日志（自动生成）
```

## 快速开始（两台平台都只需 3 步）

### 1. 配置参数

编辑 `config.json`：

```json
{
  "friend": "我宝",
  "message": "记得吃药啦 💊",
  "schedule_time": "10:00",
  "wechat_app_name": "WeChat"
}
```

| 字段 | 说明 |
|------|------|
| `friend` | 好友在微信里的**备注名**（搜索用） |
| `message` | 提醒文案（支持中文/emoji） |
| `schedule_time` | 每天提醒时间，24 小时制 `HH:MM` |

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

# 注册每天定时任务（读取 config.json 的时间）
python install_schedule.py

# 卸载定时任务
python install_schedule.py --uninstall
```

---

## 原理

| 系统 | 方案 | 步骤 |
|------|------|------|
| macOS | AppleScript + System Events | `Cmd+F` 搜索好友 → 剪贴板粘贴昵称 → 回车进会话 → 粘贴文案 → 回车发送 |
| Windows | uiautomation 库 | 定位微信主窗口 → 搜索框输入昵称 → 回车进会话 → 粘贴文案 → 回车发送 |

中文/emoji 一律通过**系统剪贴板**粘贴，避免按键编码问题，这是最稳的方式。

## 定时机制

| 系统 | 机制 | 管理方式 |
|------|------|----------|
| macOS | launchd (`~/Library/LaunchAgents/com.wechat.reminder.plist`) | `launchctl list \| grep wechat` |
| Windows | 任务计划程序（任务名 `WeChatMedicineReminder`） | 控制面板 → 管理工具 → 任务计划程序 |

## 可靠性设计（已内置）

| 能力 | 实现 |
|------|------|
| 发送前自检 | 微信未运行则自动启动（macOS: `launch`；Windows: `Run`） |
| 失败重试 | 最多重试 3 次，间隔 2 秒 |
| 结果验证 | 发送后读取 UI 树，确认会话已打开、剪贴板已被消费 |
| 锁屏处理 | 检测锁屏则等待解锁（最多 4 小时，每 15 秒轮询）再发送 |
| 剪贴板还原 | 尽力还原用户原有剪贴板内容 |

## 注意事项（重要）

1. **微信必须保持登录**，且电脑**不要锁屏**（锁屏时 UI 自动化无法点击）。
2. 任务在**当前用户会话**下运行，需保持登录态。
3. Windows 的 uiautomation 适配微信 3.x 桌面版；若微信更新导致定位失败，可能需要调整 `send_reminder.py` 中的控件查找参数。
4. 发送记录写入 `reminder.log`，排查问题先看它。
5. macOS 下若脚本由 launchd 调用，辅助功能权限需授予 `/usr/bin/osascript` 或对应的 Python 解释器所在应用。
6. **已知限制**：实测 macOS 微信激活后会**持续清空系统剪贴板**，故发送期间用户剪贴板内容通常无法还原（脚本会记录警告，不影响发送主流程）。
7. **验证兜底**：若 UI 树读取失败（读不到消息气泡文本），脚本不会误判失败，会以会话标题 + 剪贴板信号为准。