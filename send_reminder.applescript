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

			-- 用剪贴板粘贴好友备注名（支持中文）
			set the clipboard to friendName
			keystroke "v" using command down
			delay 1

			-- 回车打开会话
			key code 36
			delay 1

			-- 粘贴提醒文案
			set the clipboard to messageText
			keystroke "v" using command down
			delay 0.5

			-- 回车发送
			key code 36
			delay 0.5

			-- 清除剪贴板避免误用
			set the clipboard to ""
		end tell
	end tell
end run