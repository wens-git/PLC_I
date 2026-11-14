# 当前 PLC 交付

气缸升级工程：[FM_XJV1_Cylinder_v13.project](project/FM_XJV1_Cylinder_v13.project)，协议1.3、签名0x584A5633，47个ST源码文件。端口1502、32 Holding、1830 Input、4ms EtherCAT_Task保持不变。离线编译/代码生成0错误0警告，源码hash见[evidence/cylinder-upgrade-build-status.json](evidence/cylinder-upgrade-build-status.json)。本次没有连接或下载真实PLC，未完成现场验收。

原project/FM_XJV1.project保留为1.2基线，不能与新上位机混用。rebuild_current.py从原工程复制设备配置并按当前src新增/更新对象，在artifacts/plc-probe/build-*生成新工程和独立日志；不会覆盖原工程或连接设备。

使用方法见[气缸配置与业务接口](../docs/气缸配置与业务接口.md)。物理绑定默认全0，工程表中的未知I/O为65535；模块就绪须接真实诊断。新的气缸扫描自测源码位于tests，编译检查不等于执行通过。
