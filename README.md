# Pixel Person Desktop Pet

这是一个原生 macOS 透明窗口版「桌面像素人」雏形：会读取你桌面上的 4 组动作素材，并在终端打印大量 `Step ...` 调试信息。

Windows 朋友请使用 `pixel_person_pet_windows.py`，打包说明见 `WINDOWS_BUILD.md`。

素材路径：

- `assets/idle`
- `assets/walk`
- `assets/drink`
- `assets/typing`
- `assets/focus`：可选，专注进行中的图片。当前使用 `assets/focus/bang.png`
- `assets/done`：可选，专注完成后的图片。把你的 GOOD 图片保存成 `assets/done/good.png` 或任意 `.png` 即可。

运行：

```bash
python3 pixel_person_pet.py
```

如果提示缺少依赖，先运行：

```bash
python3 -m pip install -r requirements.txt
```

也可以双击 `launch.command` 启动。第一次使用如果提示没有权限，运行 `chmod +x launch.command`。

玩法：

- 左键点一下：按顺序触发 `走路 -> 喝水 -> 打字`
- 左键拖动：移动位置
- 右键：打开菜单，可选择 `开始专注 1 小时`、`取消专注`、`打字`、`退出`
- 键盘 `1`：待机
- 键盘 `2`：立刻走路
- 键盘 `3`：喝水
- 键盘 `4`：打字
- 键盘 `f`：开始专注 1 小时
- 键盘 `c`：取消专注
- `Esc`：退出

备注：

- 当前素材是 RGB 图片，棋盘格背景不是真透明。程序会自动把边缘连通的棋盘格背景抠掉。
- 项目已内置一份透明素材在 `assets/`，发给别人时不用再依赖你的桌面文件夹。
- 角色显示高度在 `pixel_person_pet.py` 的 `TARGET_HEIGHT` 里调，默认 `210`。
- 动画速度在 `FRAME_DELAY_MS` 里调，默认 `360` 毫秒一帧。
- 程序不会自己“运行完”，桌宠会一直待在桌面上，直到你按 `Esc` 退出。
- 她平时会静止待机，不会自动循环动作；只有点击或按键才会动。
- 专注模式中会显示 `assets/focus/bang.png`，倒计时结束后切换到 GOOD 完成图。
- 之前 Pygame/SDL 在 macOS 上会把窗口合成为黑色不透明底，这版已经改成原生 AppKit 透明浮窗。
- 想快速测试专注完成，可以临时运行：

```bash
PET_FOCUS_SECONDS=10 python3 pixel_person_pet.py
```
