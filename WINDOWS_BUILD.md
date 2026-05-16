# Windows 打包说明

这个项目的 `pixel_person_pet.py` 是 macOS 原生透明窗口版，不能直接给 Windows 用户运行。

Windows 用户请使用：

```bash
python pixel_person_pet_windows.py
```

## 本地打包成 exe

在 Windows 电脑上进入项目目录，然后运行：

```bash
python -m pip install -r requirements-windows.txt
pyinstaller --noconsole --onefile --add-data "assets;assets" --name PixelPersonPet pixel_person_pet_windows.py
```

打包完成后，文件在：

```text
dist/PixelPersonPet.exe
```

把这个 `.exe` 发给朋友即可。

## 用 GitHub 自动打包

把项目推到 GitHub 后，仓库会自动运行 `.github/workflows/build-windows.yml`。

运行结束后，在 GitHub 的 `Actions` 页面打开最新构建，下载 `PixelPersonPet-Windows` artifact，里面就是 `PixelPersonPet.exe`。
