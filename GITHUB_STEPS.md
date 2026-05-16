# 怎么放到 GitHub

## 1. 本地测试

```bash
cd /Users/shuke/Documents/Codex/2026-05-16/codex-2-http-xhslink-com-o
python3 -m pip install -r requirements.txt
python3 pixel_person_pet.py
```

也可以双击 `launch.command` 启动。

如果双击提示没有权限，运行：

```bash
chmod +x launch.command
```

## 2. 初始化 Git

```bash
git init
git add .
git commit -m "Add macOS desktop pet"
```

## 3. 创建 GitHub 仓库

在 GitHub 新建一个空仓库，比如 `desktop-pet`，不要勾选自动生成 README。

然后把 GitHub 给你的远程地址替换到下面：

```bash
git branch -M main
git remote add origin https://github.com/你的用户名/desktop-pet.git
git push -u origin main
```

## 4. 送给别人怎么用

对方下载仓库后运行：

```bash
python3 -m pip install -r requirements.txt
python3 pixel_person_pet.py
```

如果想做成真正双击 `.app`，下一步可以用 `py2app` 或 `PyInstaller` 打包。
