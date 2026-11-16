@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "App\FM_GPTPRO.exe" if exist "App\_internal\" goto run
echo.
echo [缺少运行包] App\FM_GPTPRO.exe 或 App\_internal\ 不存在。
echo.
echo 原因：本 GitHub 仓库是源码仓库，.gitignore 排除了 App\ 运行包，
echo       所以直接下载/克隆得到的目录不含可直接双击的运行程序。
echo.
echo 任选一种方式打开上位机：
echo   方式1（推荐、最省事）：改用完整发布包 PLC_I-architecture-*.zip，
echo          解压后双击其中的 启动上位机.bat。
echo   方式2：本机已装 Python 3.14 及依赖时，双击 start-desktop.bat 从源码运行。
echo   方式3：本机打包：powershell -NoProfile -ExecutionPolicy Bypass -File tools\BuildDesktop.ps1
echo          成功后 App\ 生成，本脚本即可正常启动。
echo.
echo 详见 README.md 的“启动”章节。
echo.
pause
exit /b 1
:run
start "" "App\FM_GPTPRO.exe"
exit /b 0
