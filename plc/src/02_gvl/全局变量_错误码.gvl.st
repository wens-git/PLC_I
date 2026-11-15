(* 拒绝/错误码集中定义。FB 只引用名称，避免数字散落各文件。
   数值与协议 register-map 的拒绝码一致，新增码必须同步协议表。 *)
VAR_GLOBAL CONSTANT
    ERR_已受理   : WORD := 0;
    ERR_签名     : WORD := 1;
    ERR_通信离线 : WORD := 2;
    ERR_急停     : WORD := 3;
    ERR_未绑定   : WORD := 4;
    ERR_离线     : WORD := 5;
    ERR_未使能   : WORD := 6;
    ERR_模式     : WORD := 7;
    ERR_复位中   : WORD := 8;
    ERR_参数     : WORD := 9;
    ERR_忙       : WORD := 10;
    ERR_待复位   : WORD := 11;
    ERR_正式流程 : WORD := 12;
    ERR_未接入   : WORD := 14;
    ERR_非法     : WORD := 15;
    ERR_纪元     : WORD := 16;
    ERR_故障     : WORD := 17;
    ERR_无点位   : WORD := 18;
    ERR_取消     : WORD := 19;
    ERR_定标     : WORD := 20;
    ERR_软限位   : WORD := 21;
    ERR_速度     : WORD := 22;
    ERR_P0       : WORD := 26;
    ERR_目标越限 : WORD := 27;
    ERR_速度无效 : WORD := 28;
END_VAR
