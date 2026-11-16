# PySide6 + Web + PLC 当前交付

## PLC 架构重构与归档

PLC 已按职责整理为七个域，服务端与主循环职责拆分，Axis/Cy请求提交合并；说明见 [PLC架构](docs/PLC架构.md)。本轮生产工程及证据以格式2清单为准。完整交付包由 `python tools/archive_delivery.py --output artifacts/releases/PLC_I-architecture.zip` 生成，并附SHA256；Git仓库保留源码、正式工程和验证证据，桌面大体积运行库在本地完整归档中。

## 本次交付状态与重建规则

本轮 P1 控制链修复与安全状态以当前源码及本轮 evidence 为准：清故障不自动使能，故障清除后仍须用户显式请求使能。详细结果见 [本轮修复报告](docs/修复结果-20261115.md)。PLC 编译、桌面模拟与真实设备验收分别记录，不能互相替代。

本源码仓库允许保留历史 PLC 基线；正式工程由新生成的 MANIFEST.json 的 `production_project.path` 唯一指定，不能通过统计整个目录的 `.project` 数量判断。下文日期记录为历史说明，不是当前源码的编译、打包或实机验收结论。仓库中的旧 MANIFEST 格式 1 也不是当前交付证明，必须重新生成格式 2。

Windows 运行包必须同时具有 `App/FM_GPTPRO.exe` 和完整的 `App/_internal`。源码检出没有 App 时，启动脚本会说明缺包并返回失败；按“源码开发和重建”执行完整构建后才可启动。构建会部署 App，保留前一包在 `artifacts/desktop-deploy-previous`。源码开发工具、IDE 和现场设备均不能由历史验收记录替代。

## 历史记录：2026-11-14 安全修正（同一1.3协议）

在1.3基础上修正了控制链路的实际缺陷，协议字段不变：

- 新增气缸物理IO映射层（输入/输出映像、真实模块在线位），`映射有效` 由绑定与配置推导，不再手工置位；未映射时气缸保持离线、输出全0。
- 轴硬限位未接线时必须保持软限位启用，否则拒绝运动；清故障不再自动使能。
- 真空缸动作超时保持吸附并报警，等待人工释放；普通缸超时撤销输出。
- 42按阀型区分物理含义，上位机按钮同步标注；双电控不会因“取消”而停止运动。
- 跨缸输入/输出地址重复被拒绝；绑定纪元随绑定表变化自动递增。
- 气缸配置改为一缸一行的 `Cy气缸配置`：`已绑定`、`e阀型`、`out动点/out原点`、`e动点确认/in动点`、`e原点确认/in原点`，枚举用 `Cy阀型` / `Cy确认`；业务接口改为 `Cy动点/原点/取消/忙/完成/故障`，设备内部保存请求号，业务不再手写令牌。

编译记录见 [safety-fix-build-status.json](plc/evidence/safety-fix-build-status.json)，当前55个源码文件离线编译及代码生成0错误0警告。物理接线与模块诊断仍需现场完成。

## 2026-11-13 气缸/真空升级（协议1.3）

当前源码新增中文气缸业务接口、统一手自动请求、两侧独立确认延时和真空模式；上位机同步显示传感器确认/延时完成。签名升级为0x584A5633，旧1.2运行包和PLC不能与新版本混用。使用说明见 [气缸配置与业务接口](docs/气缸配置与业务接口.md)。物理气缸仍全部未绑定，不推测现场接线。本次PLC工程为 [FM_XJV1_Cylinder_v13.project](plc/project/FM_XJV1_Cylinder_v13.project)，原FM_XJV1.project保留为1.2基线；新工程已离线编译及代码生成0错误0警告，47个源码hash对应本次记录。App已更新为1.3，原运行包备份在artifacts/App-before-cylinder-v13。本次构建与验证结果见 [气缸升级验证](Validation/cylinder-upgrade-results.json)；下文2026-11-09记录仅说明原始交付，不能用作本次改动的编译/实机证明。

## 原始交付记录（2026-11-09）

本版把上位机重构为 PySide6 桌面程序。Vue 页面在 QWebEngineView 中运行，操作请求、结果回包和状态推送通过 QWebChannel 连接 Python 共享服务，再由唯一 CommWorker 访问 PLC。桌面入口不启动 FastAPI/Uvicorn、不打开系统浏览器、不监听 HTTP 端口。现有 Vue 页面、协议编解码和 PLC 控制实现继续复用。

## 启动

双击交付根目录的“启动上位机.bat”，或运行 App/FM_GPTPRO.exe。必须保留 EXE 旁的 _internal 目录。无需另装 Python、Node 或浏览器；随包携带 Qt WebEngine。默认离线，连接设置中选择模拟或 Modbus TCP；真实 PLC 默认 192.168.6.6:1502，Unit ID 1。每个 Windows 用户只允许一个桌面实例。全屏模式使用 FM_GPTPRO.exe --fullscreen。

默认数据位置为 %LOCALAPPDATA%/FM_GPTPRO，沿用现有 names.json、simulation.json；桌面日志为 desktop.log，自动轮转。调试可用 --data-dir 指定隔离目录。名称仅保存在上位机，不写 PLC。模拟数据不代表现场配置或 PLC 掉电保持。

## 目录

- App：本次构建的唯一 Windows 上位机运行包。
- backend、desktop、web、tools：可重建的 Python、PySide6、Vue 源码、测试与构建脚本。
- plc/project：可含历史基线；正式主工程以 MANIFEST.json 的 `production_project.path` 为准，不能把基线下载为当前版本。
- plc/src：当前 PLC 源码；清单逐文件记录哈希，不沿用历史源码数量。
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

构建先执行协议/Python/前端检查，再打包到 `artifacts/desktop-release/FM_GPTPRO`，完整复制并部署到 `App`，生成 `artifacts/desktop-build-evidence.json`。失败时脚本抛错，不生成成功凭据；打包中源码改变也会拒绝成功凭据。运行中的 App 可能阻止目录替换，应先关闭它。此脚本不会生成 MANIFEST，也不会执行打包 EXE 的窗口模拟检查。直接启动源码可执行 start-desktop.bat；修改 Vue 后需重新构建资源和运行包。

完成本轮构建及计划内验证后，由交付负责人生成清单（例中的工程路径须与本轮真实工程一致）：

    python tools/generate_manifest.py --production-project plc/project/FM_XJV1_Cylinder_v13.project --desktop-evidence artifacts/desktop-build-evidence.json --plc-evidence plc/evidence/review-fix-build-status.json
    python tools/verify_delivery.py --require-builds

未执行 PLC 编译时省略 `--plc-evidence`，其状态保持 `not_run`；普通 `verify_delivery.py` 验证文件完整性并打印未跑项，`--require-builds` 则要求当前 PLC 与桌面构建证据都通过。两者都不声称现场验收成功。EXE 缺失、主工程缺失、哈希不符、漏列文件或证据与当前源码不符均返回非零。

格式 2 不读取旧 MANIFEST 的验收字段。它排除 artifacts（显式引用证据除外）、缓存、运行日志、用户 `*-data`、IDE `.opt` 等可变文件，并逐项登记源码、App、主工程和证据。历史基线可纳入完整性清单，但不会被指定为第二个正式工程。

构建证据 JSON 必须具有 `success: true`、带时区的 `completed_at`、完整 `sources` 路径到 SHA-256 映射。PLC 证据还须有 `production_project`（交付相对路径）与 `project_sha256`；桌面证据须有 `executable_sha256`。PLC 的 `sources` 必须覆盖本轮全部 `plc/src/**/*.st`，桌面映射由 `tools/generate_manifest.py` 的 `source_hashes(root, 'desktop')` 生成。证据时间不得晚于清单，证据哈希和全部源码哈希都必须匹配；历史无时间/无主工程哈希的记录不能冒充本次编译。

独立验证结果可通过 `--verification 本轮结果.json` 传入，键为 `python_tests`、`frontend_tests`、`protocol_check`、`source_smoke`、`packaged_smoke`、`real_plc_acceptance`；每项为 `{"status":"passed","evidence":"相对报告路径"}` 或 `{"status":"not_run"}`。已跑报告同样须具有上述时间、success 和当前桌面 sources；打包窗口报告还须绑定 EXE 哈希。没有显式提供的项目一律 `not_run`，构建凭据的步骤记录不自动变成窗口或现场验收通过。

独立检查：

    python -m pytest backend/tests -q
    python tools/check_protocol.py
    cd web
    npm ci
    npm test

Qt 实际窗口与 QWebChannel 集成检查（仅模拟，自动退出）：

    python desktop_launcher.py --data-dir artifacts/validation-data --smoke-report artifacts/desktop-smoke.json

--smoke-report 是验证模式，会在隔离数据目录连接模拟器并执行模拟操作；请始终配合 --data-dir 使用。

## 历史 PLC 状态（原始交付，不代表本轮）

配套工程是 AxisFix v11，使用 XS Studio V2.3.2a；本轮复制其原始字节，没有修改 PLC 控制逻辑。官方 CODESYS ModbusTCP Slave，端口 1502，Holding 32 WORD、Input 1830 WORD，签名 0x584A5632。唯一 PLC_PRG 调用位于 4ms EtherCAT_Task，所选总线周期对齐该任务。精确地址来自 protocol-v1.json。

最近一次完整编译和代码生成记录为 2026-10-30，0 错误、0 警告；34 个当前源码 SHA-256 均与 build-status.json 一致。隔离自测：配置 61、运行时 32、移植 13、轴接口 20，均 0 失败。axis-alarm-selftest 是确定性 MC 替身测试，不证明真实驱动器运动。

当前绑定 3 轴，气缸实际未绑定；气缸传感器和阀输出没有完整实际映射，40/41 未开放。正式业务流程尚未接入，2/3/4 在此条件下拒绝 12。额定值仍需按驱动器核实。脉冲轴 OpenLoop 默认在线不代表已使能或到位。清故障成功会自动请求使能。运动许可由 PLC 决策，未增加参与掩码或保持区运动门禁。

本轮桌面模拟验证、Python 源码测试、PLC 历史编译与现场验收分别记录。没有完成本轮 PLC 编译或真实机器验收，没有执行真实 PLC 连接、下载、复位、使能或运动。目标工控机的触摸/输入法/GPU、长期运行、真实链路时序与停车距离仍需现场验证。不据此标记整机或任何未通过 DoD 的阶段完成。

本轮完整仓库检查为 Python 327 项通过、223 个子测试通过，前端 21 项通过，协议检查 0 错误。交付源码独立检查为 Python 288 项通过、28 个子测试通过，前端 21 项通过并可构建；计数不同源于排除依赖旧模板工程和历史参考源码的五个测试文件，未改变运行时测试。Python 两条既有依赖弃用警告仍存在。Qt 源码和打包 EXE 的模拟集成均覆盖离线启动、连接、轴使能、名称与参数读回、点位示教、气缸/I/O/诊断页面、最小化/重载/关闭时点动撤销，以及通信线程退出。

## 分发组件

运行包使用 PySide6 6.11.1 与 Qt WebEngine，包含 Python、Qt 和其他依赖。请保留随包提供的许可与第三方说明；对外分发前按实际使用模块和 LGPL/GPL/第三方许可要求处理。Qt 动态库按目录发布，不做单文件内嵌。浏览器开发入口仅作源码开发入口保留。历史 PLC 基线可保留在源码仓库，正式下载目标始终以清单的 production_project 为准。
