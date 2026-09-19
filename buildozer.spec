# [app configuration]
[app]
title = AOV Checker Pro
package.name = aovchecker
package.domain = org.garena.aov
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js,json,txt
source.exclude_dirs = bin, .buildozer, .git, results, __pycache__, scratch
version = 1.0.0
requirements = python3,requests,urllib3,pillow

# Webview bootstrap - Tự động tải giao diện Web UI local lên Android WebView
p4a.bootstrap = webview
p4a.port = 8080

# Orientation & Display
orientation = portrait
fullscreen = 0

# Android permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE

# Target Android API
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
