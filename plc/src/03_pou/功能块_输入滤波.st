(* 现场输入去抖。语义与原程序 功能块_输入滤波 一致：
   模式 0 直通；模式 1 按真/假时间分别计时，先到者生效。
   安全输入（急停 X3）不经过本块，避免滤波延迟安全响应。
   X0/X1/X2 走 20 ms 去抖，与原程序 子程序_IO映射__采集 一致。 *)
FUNCTION_BLOCK 功能块_输入滤波
VAR_INPUT
    b信号 : BOOL;
    i模式 : INT; (* 0 = 直通，1 = 去抖 *)
    di滤波时间真 : DINT; (* ms *)
    di滤波时间假 : DINT; (* ms *)
END_VAR
VAR_OUTPUT
    b滤波信号 : BOOL;
END_VAR
VAR
    tmr延时真 : TON;
    tmr延时假 : TON;
END_VAR

CASE i模式 OF
    0:
        tmr延时真(IN := FALSE, PT := DINT_TO_TIME(di滤波时间真));
        tmr延时假(IN := FALSE, PT := DINT_TO_TIME(di滤波时间假));
        b滤波信号 := b信号;
    1:
        tmr延时真(IN := b信号, PT := DINT_TO_TIME(di滤波时间真));
        tmr延时假(IN := NOT b信号, PT := DINT_TO_TIME(di滤波时间假));

        IF tmr延时真.Q THEN
            b滤波信号 := TRUE;
        END_IF;

        IF tmr延时假.Q THEN
            b滤波信号 := FALSE;
        END_IF;
ELSE
    (* 非法模式按直通处理，绝不因为配置错误把一个输入永久锁死。 *)
    tmr延时真(IN := FALSE, PT := DINT_TO_TIME(di滤波时间真));
    tmr延时假(IN := FALSE, PT := DINT_TO_TIME(di滤波时间假));
    b滤波信号 := b信号;
END_CASE;
END_FUNCTION_BLOCK
