#!/bin/bash
# 用法: ./send_reminder.sh "好友备注名" "提醒文案"
FRIEND="$1"
MESSAGE="${2:-记得吃药啦 💊}"

/usr/bin/osascript /Users/harry/wechat-medicine-reminder/send_reminder.applescript "$FRIEND" "$MESSAGE"

if [ $? -eq 0 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') 已发送给 $FRIEND" >> /Users/harry/wechat-medicine-reminder/reminder.log
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') 发送失败: $FRIEND" >> /Users/harry/wechat-medicine-reminder/reminder.log
fi