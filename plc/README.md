# PLC 当前架构与交付

正式工程为 [FM_XJV1_Cylinder_v13.project](project/FM_XJV1_Cylinder_v13.project)。协议1.3，签名0x584A5633，1502端口，32 Holding/1830 Input，4ms EtherCAT_Task。

源码现按职责分为 entry、application、communication、configuration、motion、cylinder、hardware 七个域；XS工程使用对应SRC_*文件夹。架构、调用顺序、状态拥有者和维护规范见 [PLC架构](../docs/PLC架构.md)。

服务端拆为命令仲裁、诊断、发布、复位；主循环只展示扫描顺序，模式管理与轴组独立。Axis/Cy保留语义API，内部统一提交。单轴MC实例仍由唯一轴FB拥有，不分散到多个调用者。

本轮编译证据见 [architecture-build-status.json](evidence/architecture-build-status.json)，实际工程对象核对见 [architecture-project-verification.json](evidence/architecture-project-verification.json)。历史证据保留追溯，不作为本轮源码通过证明。

重建使用 tools/rebuild_current.py，从正式工程复制设备配置、导入当前源码、清理退役对象并镜像域文件夹；不登录、不下载。仓库只保留 `FM_XJV1_Cylinder_v13.project` 一个正式工程，1.2 基线已删除，历史版本可由 Git 记录追溯。

物理气缸默认未绑定。I/O、真实模块诊断、限位接线及额定值仍需现场验收。IEC扫描自测未执行，不把Python源码契约测试或编译结果当作真实运动证明。
