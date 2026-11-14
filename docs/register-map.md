# XJV1 Register Map

Generated from `protocol-v1.json`. Do not edit by hand.

Revision 1.3, signature 0x584A5633, Modbus TCP port 1502, Unit ID 1. All addresses are zero-based PDU addresses.

| Area | Words | Functions |
|---|---|---|
| holding | 32 | Holding Register（FC03 读 / FC06、FC16 写） |
| input | 1830 | Input Register（FC04 只读） |
| names | 0 | host configuration store, no PLC register |
| total | 1862 | 3724 bytes |

| Window | Area | Base | End | Stride | Count | Access |
|---|---|---|---|---|---|---|
| command | holding | 0 | 31 | 32 | 1 | write |
| status | input | 0 | 103 | 104 | 1 | read |
| io | input | 104 | 123 | 20 | 1 | read |
| axis_live | input | 124 | 379 | 16 | 16 | read |
| cylinder_live | input | 380 | 541 | 3 | 54 | read |
| axis_config | input | 542 | 797 | 16 | 16 | read |
| cylinder_config | input | 798 | 1229 | 8 | 54 | read |
| points | input | 1230 | 1829 | 5 | 120 | read |

## command

| Field | Offset | Words | Type |
|---|---|---|---|
| signature | +0 | 2 | DWORD |
| heartbeat | +2 | 1 | WORD |
| code | +3 | 1 | WORD |
| commit | +4 | 1 | WORD |
| object | +5 | 1 | WORD |
| a | +6 | 2 | DWORD |
| b | +8 | 2 | DWORD |
| c | +10 | 2 | DWORD |
| jog_renew | +12 | 1 | WORD |
| jog_object | +13 | 1 | WORD |
| jog_seq | +14 | 1 | WORD |
| reserved_header | +15 | 1 | ZERO |
| staging | +16 | 16 | WORD[] |

## status

| Field | Offset | Words | Type |
|---|---|---|---|
| signature | +0 | 2 | DWORD |
| heartbeat | +2 | 1 | WORD |
| ack_seq | +3 | 1 | WORD |
| ack_result | +4 | 1 | WORD |
| ack_object | +5 | 1 | WORD |
| ack_epoch | +6 | 1 | WORD |
| system | +7 | 1 | WORD |
| capacity | +8 | 1 | WORD |
| axis_bound | +9 | 1 | WORD |
| cylinder_bound | +10 | 4 | LWORD |
| axis_online | +14 | 1 | WORD |
| cylinder_online | +15 | 4 | LWORD |
| global_permit | +19 | 1 | WORD |
| global_reason | +20 | 1 | WORD |
| axis_summary | +21 | 16 | WORD[] |
| cylinder_summary | +37 | 54 | WORD[] |
| first_alarm | +91 | 1 | WORD |
| first_alarm_object | +92 | 1 | WORD |
| alarm_count | +93 | 1 | WORD |
| last_rejection | +94 | 1 | WORD |
| step | +95 | 2 | UDINT |
| uptime_s | +97 | 2 | UDINT |
| binding_epoch | +99 | 1 | WORD |
| config_epoch | +100 | 1 | WORD |
| features | +101 | 1 | WORD |
| point_pool | +102 | 1 | WORD |
| snapshot_epoch | +103 | 1 | WORD |

## io

| Field | Offset | Words | Type |
|---|---|---|---|
| x_count | +0 | 1 | UINT |
| y_count | +1 | 1 | UINT |
| x | +2 | 8 | WORD[] |
| y | +10 | 8 | WORD[] |
| reserved | +18 | 2 | ZERO |

## axis_live

| Field | Offset | Words | Type |
|---|---|---|---|
| position | +0 | 2 | DINT |
| velocity | +2 | 2 | DINT |
| target | +4 | 2 | DINT |
| permit | +6 | 1 | WORD |
| reason | +7 | 1 | WORD |
| alarm | +8 | 1 | WORD |
| drive_error | +9 | 2 | DWORD |
| active_seq | +11 | 1 | WORD |
| motion_result | +12 | 1 | WORD |
| limits | +13 | 1 | WORD |
| reserved | +14 | 2 | ZERO |

## cylinder_live

| Field | Offset | Words | Type |
|---|---|---|---|
| permit | +0 | 1 | WORD |
| reason | +1 | 1 | WORD |
| alarm | +2 | 1 | WORD |

## axis_config

| Field | Offset | Words | Type |
|---|---|---|---|
| positive_limit | +0 | 2 | DINT |
| negative_limit | +2 | 2 | DINT |
| manual_speed | +4 | 2 | UDINT |
| auto_speed | +6 | 2 | UDINT |
| acceleration | +8 | 2 | UDINT |
| deceleration | +10 | 2 | UDINT |
| estop_deceleration | +12 | 2 | UDINT |
| flags | +14 | 1 | WORD |
| reserved | +15 | 1 | ZERO |

## cylinder_config

| Field | Offset | Words | Type |
|---|---|---|---|
| wiring_flags | +0 | 1 | WORD |
| move_y | +1 | 1 | WORD |
| home_y | +2 | 1 | WORD |
| move_x | +3 | 1 | WORD |
| home_x | +4 | 1 | WORD |
| delay_ms | +5 | 1 | UINT |
| timeout_ms | +6 | 1 | UINT |
| home_delay_ms | +7 | 1 | UINT |

## points

| Field | Offset | Words | Type |
|---|---|---|---|
| position | +0 | 2 | DINT |
| speed | +2 | 2 | UDINT |
| flags | +4 | 1 | WORD |

## axis Field Masks

| Field | Mask |
|---|---|
| positive_limit | 0x0001 |
| negative_limit | 0x0002 |
| manual_speed | 0x0004 |
| auto_speed | 0x0008 |
| acceleration | 0x0010 |
| deceleration | 0x0020 |
| estop_deceleration | 0x0040 |
| flags | 0x0080 |

## cylinder Field Masks

| Field | Mask |
|---|---|
| delay_ms | 0x0001 |
| timeout_ms | 0x0002 |
| home_delay_ms | 0x0004 |

## point Field Masks

| Field | Mask |
|---|---|
| position | 0x0001 |
| speed | 0x0002 |
| flags | 0x0004 |

## axis Permit Bits

| Bit | Command |
|---|---|
| 0 | 20 |
| 1 | 21 |
| 2 | 22 |
| 3 | 23 |
| 4 | 24 |
| 5 | 25 |
| 6 | 27 |
| 7 | 28 |
| 8 | 29 |
| 9 | 30 |
| 10 | 31 |
| 11 | 50 |

## cylinder Permit Bits

| Bit | Command |
|---|---|
| 0 | 40 |
| 1 | 41 |
| 2 | 50 |

## Point Flags

bit0 enabled, bit1 taught, bit2..5 owner axis 0..15, 0x0040 free slot (owner bits zero, not enabled, not taught). Other bits are zero.

## Alarms

| Code | Object | Message | Action |
|---|---|---|---|
| 1101 | axis | 轴通信离线：使能、运动或停止过程中驱动器失去在线状态 | 检查驱动器供电、总线/脉冲接线和通信状态后清故障 |
| 1103 | axis | 硬急停：轴已被强制断使能并清除回原状态 | 排除急停原因、释放急停后复位并重新回原 |
| 1104 | axis | 驱动器处于 ErrorStop（MC_ReadStatus.Errorstop），报警信息会附驱动错误码 | 看报警里的驱动错误码和驱动器面板：排除过流/编码器/限位/STO 等原因后点“清故障”（命令 23）；仍不复位就断驱动器电重启 |
| 1105 | axis | 运行中使能意外丢失（MC_Power.Status 掉落） | 检查驱动器使能回路、主电源和驱动器报警 |
| 1110 | axis | 读取轴状态失败（MC_ReadStatus.Error） | 按驱动错误码检查轴配置与驱动通信 |
| 1111 | axis | 读取实际位置失败（MC_ReadActualPosition.Error） | 按驱动错误码检查编码器反馈与轴配置 |
| 1112 | axis | 读取实际速度失败（MC_ReadActualVelocity.Error） | 按驱动错误码检查编码器反馈与轴配置 |
| 1120 | axis | 使能失败（MC_Power.Error） | 按驱动错误码检查驱动器就绪、主电源和使能信号 |
| 1121 | axis | 清故障失败：MC_Reset 报错，驱动器故障未消除 | 按报警里的驱动错误码排查；确认驱动器允许复位后重试，必要时断电重启驱动器 |
| 1122 | axis | 停止指令执行失败（MC_Stop.Error） | 立即检查现场，确认轴已停止；核对停止减速度参数 |
| 1123 | axis | 回原失败（MC_Home.Error） | 检查原点开关、回原方式和回原参数 |
| 1124 | axis | 点动执行失败（MC_Jog.Error） | 按驱动错误码检查点动速度、加减速度和限位 |
| 1125 | axis | 定位执行失败（MC_MoveAbsolute.Error） | 按驱动错误码检查目标位置、速度和软限位 |
| 1126 | axis | 运动被其他指令中断（CommandAborted） | 确认是否有并发停止或其他运动指令，重新下发动作 |
| 1127 | axis | 位置置零失败（MC_SetPosition.Error） | 轴静止且使能后重试，检查轴配置 |
| 1131 | axis | 运动参数无效：速度或停止减速度为 0 或超出范围 | 核对手动/自动速度、加减速度和急停减速度参数 |
| 1133 | axis | 位置或速度换算溢出：反馈值超出 DINT 范围 | 核对轴缩放系数和机械行程 |
| 1134 | axis | 限位阻止动作：已触发限位方向的运动或限位有效时回原 | 将轴移出限位，核对目标位置与限位方向 |
| 1140 | axis | 停止超时：30 秒内未确认轴静止 | 立即检查现场机械与驱动器，确认轴已停止 |
| 1142 | axis | 运动超时：回原/定位/置零 180 秒内未完成 | 检查机械卡滞、速度参数和目标位置 |
| 1143 | axis | 到位校验失败：停止后实际位置与目标偏差超出容差 | 检查机械间隙、丢步、编码器和缩放参数 |
| 1144 | axis | 使能超时：10 秒内驱动器未进入使能状态 | 检查驱动器就绪信号、主电源和使能接线 |
| 1145 | axis | 清故障超时：10 秒内复位未完成 | 检查驱动器是否仍在报警，排除后重试；反复超时需断电重启驱动器 |
| 2103 | cylinder | 硬急停触发：气缸输出已撤销 | 排除急停原因后复位 |
| 2110 | cylinder | 传感器冲突：动点与原点传感器同时为 ON | 检查两个磁性开关的位置和接线 |
| 2131 | cylinder | 气缸配置无效或动作中配置被修改 | 核对两侧确认延时均小于动作超时；无传感器侧延时必须大于0，检查阀类型和工程接线，动作结束后再修改参数 |
| 2140 | cylinder | 气缸动作超时：超时时间内未到达目标传感器 | 检查气压、电磁阀、气缸卡滞和目标传感器 |

## Rejections

| Code | Message | Action |
|---|---|---|
| 0 | 已受理 | 运动完成请查看对象状态 |
| 1 | 协议签名不匹配：固件与上位机协议版本不一致 | 统一固件与上位机版本后重新握手 |
| 2 | 通信离线：1.5 s 内没有收到 PLC 心跳 | 检查网线、PLC 端口 1502、IP 与防火墙，恢复后重新连接 |
| 3 | 急停有效：X3 硬急停输入为 ON 或软急停已锁存 | 排除急停原因；软急停按“解除急停”后再执行复位 |
| 4 | 对象未绑定：PLC 绑定表里没有该轴或气缸 | 核对 PLC 工程绑定常量后重新编译下载 |
| 5 | 对象离线：驱动器或 IO 模块未就绪 | 检查驱动器供电、EtherCAT 或脉冲接线与通信状态 |
| 6 | 对象未使能：该轴还没有上电 | 先执行“使能”，确认驱动器就绪后再动作 |
| 7 | 当前模式不允许该命令（自动/手动不符） | 切到手动模式或停止整机运行后重试 |
| 8 | 复位或停止流程正在占用 | 等待流程结束后重试 |
| 9 | 参数超出范围（未细分的格式错误） | 核对参数格式与字段掩码 |
| 10 | 对象正在运动 | 先停止或等待运动完成 |
| 11 | 现场配置未确认，或确认后没有复位 | 完成现场配置确认后执行全局复位 |
| 12 | 正式流程未接入 | 先用单对象调试，接入正式流程后再启动 |
| 13 | 对象已被调试屏蔽 | 解除该对象的调试屏蔽 |
| 14 | 命令不支持 | 核对命令码与固件能力位 |
| 15 | 命令对象不合法 | 核对对象类型与索引 |
| 16 | 参数版本已变化（配置纪元不一致） | 重新读取参数后再提交 |
| 17 | 对象报警或当前状态不允许 | 查看该轴报警码，先复位清故障 |
| 18 | 点位未启用或未示教 | 先示教点位并勾选启用 |
| 19 | 保持区保存失败 | 检查 PLC 运行时保存诊断，不要反复重试 |
| 20 | 轴参数未定标：定标标志必须为 1、保留字必须为 0 | 在“轴参数”里启用定标、把保留字段清零后提交 |
| 21 | 软限位无效：负限位必须小于正限位 | 按机械行程重填正/负限位后提交 |
| 22 | 额定速度未整定或请求速度超限：audi额定速度[轴]=0 表示未整定 | 在 PLC 工程按驱动规格填写 audi额定速度 后重新编译下载；已填写则降低请求速度或回原速度 |
| 23 | 额定加速度未整定或请求超限：audi额定加速度[轴]=0 表示未整定 | 在 PLC 工程按驱动规格填写 audi额定加速度 后重新编译下载；已填写则降低加速度 |
| 24 | 额定减速度未整定或请求超限：audi额定减速度[轴]=0 表示未整定 | 在 PLC 工程按驱动规格填写 audi额定减速度 后重新编译下载；已填写则降低减速度 |
| 25 | 额定停止减速度未整定或请求超限：audi额定停止减速度[轴]=0 表示未整定 | 在 PLC 工程按驱动规格填写 audi额定停止减速度 后重新编译下载；已填写则降低停止减速度 |
| 26 | P0 点位位置超出软限位 | 把 P0 位置改到正/负限位之间并重新提交 |
| 27 | 目标位置超出软限位 | 把目标位置改到正/负限位之间 |
| 28 | 速度或加速度无效：为 0 或超过 2147483647 | 填写大于 0 且不超过 2147483647 的数值 |
