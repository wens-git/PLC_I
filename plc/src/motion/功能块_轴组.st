(* 物理轴组适配：本工程3轴，每轴MC拥有者每扫描恰好调用一次。
   参数兜底、物理轴引用、请求完成回收均集中此层。 *)
FUNCTION_BLOCK 功能块_轴组
VAR_IN_OUT Runtime : 结构体_运行时; END_VAR
VAR
    fb轴0 : 功能块_轴;
    fb轴1 : 功能块_轴;
    fb轴2 : 功能块_轴;
    fb轴请求监视 : 功能块_轴请求监视;
    i循环 : UINT;
    udi兜底 : UDINT;
END_VAR
(* 停止减速度必须始终可下发：配置为 0 时按配置值兜底、仍为 0 则用 1 mm/s²。
   否则任何停止请求都会因为“没有减速度”被判无效。 *)
FOR i循环 := 0 TO 15 DO
    IF ((w已绑定轴 AND SHL(WORD#1, i循环)) <> 0)
    AND (Runtime.audi轴停止减速度[i循环] = 0) THEN
        udi兜底 := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 12]), 16)
            OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 13]));
        IF udi兜底 = 0 THEN udi兜底 := 1; END_IF;
        Runtime.audi轴停止减速度[i循环] := udi兜底;
    END_IF;
END_FOR;

(* ===== 区域 4：物理轴驱动（每个轴每扫描一次） ===== *)
fb轴0(Axis := XJ_Axis0, State := Runtime.ast轴[0],
    OpenLoop := TRUE,
    Code := Runtime.aw轴命令[0], Sequence := Runtime.aw轴序列[0],
    Target := Runtime.adi轴目标[0], Speed := Runtime.audi轴速度[0],
    Acceleration := Runtime.audi轴加速度[0], Deceleration := Runtime.audi轴减速度[0],
    StopDeceleration := Runtime.audi轴停止减速度[0],
    HardEstop := Runtime.b硬急停,
    (* Pulse axes have no external presence/Ready feedback. *)
    PositiveLimit := ab正限位[0], NegativeLimit := ab负限位[0]);
fb轴1(Axis := XJ_Axis1, State := Runtime.ast轴[1],
    OpenLoop := TRUE,
    Code := Runtime.aw轴命令[1], Sequence := Runtime.aw轴序列[1],
    Target := Runtime.adi轴目标[1], Speed := Runtime.audi轴速度[1],
    Acceleration := Runtime.audi轴加速度[1], Deceleration := Runtime.audi轴减速度[1],
    StopDeceleration := Runtime.audi轴停止减速度[1],
    HardEstop := Runtime.b硬急停,
    PositiveLimit := ab正限位[1], NegativeLimit := ab负限位[1]);
fb轴2(Axis := BusMotionAxis, State := Runtime.ast轴[2],
    Code := Runtime.aw轴命令[2], Sequence := Runtime.aw轴序列[2],
    Target := Runtime.adi轴目标[2], Speed := Runtime.audi轴速度[2],
    Acceleration := Runtime.audi轴加速度[2], Deceleration := Runtime.audi轴减速度[2],
    StopDeceleration := Runtime.audi轴停止减速度[2],
    HardEstop := Runtime.b硬急停,
    PositiveLimit := ab正限位[2], NegativeLimit := ab负限位[2],
    BusOperational := BusAxis.wState = 8);
fb轴请求监视(Runtime := Runtime);
END_FUNCTION_BLOCK
