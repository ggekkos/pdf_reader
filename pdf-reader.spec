# -*- mode: python ; coding: utf-8 -*-
# Builds the executable: pyinstaller pdf-reader.spec  ->  dist/PDFReader.exe
from PyInstaller.utils.hooks import collect_all

# Reading aloud: the Piper and Kokoro engines, each with its espeak-ng
# (pronunciation data and C libraries). Piper's training module needs
# PyTorch and isn't used by the app.
voice_datas, voice_binaries, voice_imports = [], [], []
for package in ("piper", "kokoro_onnx", "espeakng_loader", "phonemizer"):
    keep = (lambda name: not name.startswith("piper.train")) if package == "piper" else None
    d, b, h = collect_all(package, filter_submodules=keep) if keep else collect_all(package)
    voice_datas += d
    voice_binaries += b
    voice_imports += h

a = Analysis(
    ["tools/launcher.py"],
    pathex=["."],
    datas=[("pdf_reader/assets", "pdf_reader/assets")] + voice_datas,
    binaries=voice_binaries,
    hiddenimports=voice_imports,
    excludes=[
        "PyQt5", "tkinter", "pytest", "scipy", "PIL", "pandas", "matplotlib", "torch",
        "piper.train",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtPdf",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
    ],
    noarchive=False,
)
# DLLs the app doesn't use: QML/Quick, Qt's PDF module, software OpenGL and Qt
# Multimedia's FFmpeg (we only play raw audio, which goes straight to Windows).
UNNEEDED = ("opengl32sw", "Qt6Quick", "Qt6Qml", "Qt6Pdf", "Qt6VirtualKeyboard",
            "avcodec", "avformat", "avutil", "swresample", "swscale", "ffmpegmediaplugin")
a.binaries = [b for b in a.binaries if not any(n in b[0] for n in UNNEEDED)]
a.datas = [d for d in a.datas if "piper/train" not in d[0].replace("\\", "/")]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PDFReader",
    icon="pdf_reader/assets/icon.ico",
    console=False,
    upx=False,
)
