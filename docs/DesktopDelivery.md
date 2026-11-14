# PySide6 + Web + PLC 原始交付记录（2026-11-09）

本文件保留原1.2交付历史。当前版本已升级到1.3，使用新PLC工程FM_XJV1_Cylinder_v13.project与更新后的App。当前能力、编译和验证结果见根目录README及[气缸配置与业务接口](气缸配置与业务接口.md)、[升级验证](../Validation/cylinder-upgrade-results.json)，不要将下文历史签名/未开放气缸说明当成当前实现。

本版把上位机重构为 PySide6 桌面程序。Vue 页面在 QWebEngineView 中运行，操作请求、结果回包和状态推送通过 QWebChannel 连接 Python 共享服务，再由唯一 CommWorker 访问 PLC。桌面入口不启动 FastAPI/Uvicorn、不打开系统浏览器、不监听 HTTP 端口。现有 Vue 页面、协议编解码和 PLC 控制实现继续复用。

## 启动

双击交付根目录的“启动上位机.bat”，或运行 App/FM_GPTPRO.exe。必须保留 EXE 旁的 _internal 目录。无需另装 Python、Node 或浏览器；随包携带 Qt WebEngine。默认离线，连接设置中选择模拟或 Modbus TCP；真实 PLC 默认 192.168.6.6:1502，Unit ID 1。每个 Windows 用户只允许一个桌面实例。全屏模式使用 FM_GPTPRO.exe --fullscreen。

默认数据位置为 %LOCALAPPDATA%/FM_GPTPRO，沿用现有 names.json、simulation.json；桌面日志为 desktop.log，自动轮转。调试可用 --data-dir 指定隔离目录。名称仅保存在上位机，不写 PLC。模拟数据不代表现场配置或 PLC 掉电保持。

## 目录

- App：本次构建的唯一 Windows 上位机运行包。
- backend、desktop、web、tools：可重建的 Python、PySide6、Vue 源码、测试与构建脚本。
- plc/project/FM_XJV1.project：唯一 PLC 交付工程，内容选自最新 AxisFix v11；只统一交付文件名。
- plc/src：当前 34 个 ST 文件、35 个 IEC 对象。
- plc/tests：当前 IEC 自测源码，不含可误下载的自测工程。
- plc/tools/rebuild_current.py：在 XS Studio 内对当前工程另存副本并更新源码，不依赖旧工程模板，不登录或下载。
- plc/evidence：最近一次对应源码的编译、隔离自测及任务核对记录。
- docs：当前协议、生成寄存器表、本说明与验证结果。
- Validation：本轮自动验证结果和 Qt 窗口截图。
- MANIFEST.json：交付文件 SHA-256、来源和验收边界。

源码直接放在交付根目录，无目录联接或对原仓库的路径依赖。旧模板导入/归档参考专用测试不进入成品，当前协议与 PLC 源码身份检查、运行时和桥接测试保留；完整仓库测试与成品自带测试分别报告。

## 实现分工

- desktop/window.py：Qt 窗口、资源范围、导航、失焦/最小化/重载/渲染异常/退出管理。
- desktop/bridge.py：QWebChannel 请求白名单入口、异步处理、独立停止/续租通道、状态推送、页面纪元和退出清理。
- backend/service.py：共享请求模型和业务操作；HTTP 适配器与桌面桥接复用同一实现，避免两套命令逻辑。
- web/src/native.js：请求编号与回包关联、13 秒超时、状态订阅。动作超时显示“结果未知”，不自动重发。
- web/src/store.js：桌面运行时选择 QWebChannel；开发浏览器方式使用既有 HTTP/WebSocket，便于前端验证。
- backend/comm_worker.py：独占 Modbus 连接，串行 PLC 事务、ACK、停止抢占、心跳和点动租约。
- PLC 的函数_动作许可：唯一运动许可决策层。

Qt 界面线程不等待 PLC ACK。普通操作与停止/续租使用不同执行池，状态采样使用独立执行池。失焦立即使旧点动请求身份失效，异步撤销现有点动；恢复窗口不会恢复旧租约。页面重载清理旧页回包，渲染异常也撤销点动。关闭窗口等待执行器和通信线程退出后结束程序。Windows 强制终止和物理断电仍由既有 PLC 心跳/租约与现场安全回路处理。

## 源码开发和重建

使用与本版匹配的 Windows 64 位 Python 3.14、Node/npm。依赖安装和重建需要网络，运行包不需要。

在交付根目录执行：

    python -m pip install -r requirements-dev.txt
    powershell -NoProfile -ExecutionPolicy Bypass -File tools/BuildDesktop.ps1

生成 artifacts/desktop-release/FM_GPTPRO/FM_GPTPRO.exe。前端资源已放入 web/dist，直接启动源码可执行 start-desktop.bat。只修改 Vue 源码后，需在 web 下 npm ci、npm run build 才会更新桌面加载的页面。

独立检查：

    python -m pytest backend/tests -q
    python tools/check_protocol.py
    cd web
    npm ci
    npm test

Qt 实际窗口与 QWebChannel 集成检查（仅模拟，自动退出）：

    python desktop_launcher.py --data-dir artifacts/validation-data --smoke-report artifacts/desktop-smoke.json

--smoke-report 是验证模式，会在隔离数据目录连接模拟器并执行模拟操作；请始终配合 --data-dir 使用。

## PLC 当前状态

配套工程是 AxisFix v11，使用 XS Studio V2.3.2a；本轮复制其原始字节，没有修改 PLC 控制逻辑。官方 CODESYS ModbusTCP Slave，端口 1502，Holding 32 WORD、Input 1830 WORD，签名 0x584A5632。唯一 PLC_PRG 调用位于 4ms EtherCAT_Task，所选总线周期对齐该任务。精确地址来自 protocol-v1.json。

最近一次完整编译和代码生成记录为 2026-10-30，0 错误、0 警告；34 个当前源码 SHA-256 均与 build-status.json 一致。隔离自测：配置 61、运行时 32、移植 13、轴接口 20，均 0 失败。axis-alarm-selftest 是确定性 MC 替身测试，不证明真实驱动器运动。

当前绑定 3 轴，气缸实际未绑定；气缸传感器和阀输出没有完整实际映射，40/41 未开放。正式业务流程尚未接入，2/3/4 在此条件下拒绝 12。额定值仍需按驱动器核实。脉冲轴 OpenLoop 默认在线不代表已使能或到位。清故障成功会自动请求使能。运动许可由 PLC 决策，未增加参与掩码或保持区运动门禁。

本轮桌面模拟验证、Python 源码测试、PLC 历史编译与现场验收分别记录。没有完成本轮 PLC 编译或真实机器验收，没有执行真实 PLC 连接、下载、复位、使能或运动。目标工控机的触摸/输入法/GPU、长期运行、真实链路时序与停车距离仍需现场验证。不据此标记整机或任何未通过 DoD 的阶段完成。

本轮完整仓库检查为 Python 327 项通过、223 个子测试通过，前端 21 项通过，协议检查 0 错误。交付源码独立检查为 Python 288 项通过、28 个子测试通过，前端 21 项通过并可构建；计数不同源于排除依赖旧模板工程和历史参考源码的五个测试文件，未改变运行时测试。Python 两条既有依赖弃用警告仍存在。Qt 源码和打包 EXE 的模拟集成均覆盖离线启动、连接、轴使能、名称与参数读回、点位示教、气缸/I/O/诊断页面、最小化/重载/关闭时点动撤销，以及通信线程退出。

## 分发组件

运行包使用 PySide6 6.11.1 与 Qt WebEngine，包含 Python、Qt 和其他依赖。请保留随包提供的许可与第三方说明；对外分发前按实际使用模块和 LGPL/GPL/第三方许可要求处理。Qt 动态库按目录发布，不做单文件内嵌。浏览器开发入口仅作源码开发入口保留，旧发布程序和历史 PLC 工程不进入交付。
