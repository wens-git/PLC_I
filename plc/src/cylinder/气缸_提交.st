(* 所有来源唯一单槽入口。返回0拒绝，否则返回调用者必须保存的请求号。 *)
FUNCTION 气缸_提交 : UDINT
VAR_INPUT
    缸号 : UINT;
    命令 : WORD;
    自动 : BOOL;
END_VAR
VAR_IN_OUT
    Runtime : 结构体_运行时;
END_VAR
VAR
    w许可 : WORD;
END_VAR
气缸_提交 := 0;
IF 缸号 >= 54 THEN RETURN; END_IF;
IF (命令 <> 40) AND (命令 <> 41) AND (命令 <> 42) THEN RETURN; END_IF;
w许可 := 函数_动作许可(Code := 命令, ObjectWord := WORD#16#0200 OR UINT_TO_WORD(缸号),
    HmiOnline := Runtime.bHMI在线, JogBusy := FALSE, Resetting := Runtime.b复位中,
    b自动请求 := 自动, Runtime := Runtime, Store := 全局变量_保持区.Store);
IF w许可 <> 0 THEN RETURN; END_IF;
(* 42可覆盖任何请求；普通动作不能覆盖忙或尚未消费的停止。 *)
IF (命令 <> 42) AND (全局变量_气缸请求.ast请求[缸号].b忙
    OR 全局变量_气缸请求.ast请求[缸号].b待下发) THEN RETURN; END_IF;
IF 全局变量_气缸请求.udi下个请求号 = UDINT#4294967295 THEN
    全局变量_气缸请求.udi下个请求号 := 1;
ELSE
    全局变量_气缸请求.udi下个请求号 := 全局变量_气缸请求.udi下个请求号 + 1;
END_IF;
全局变量_气缸请求.ast请求[缸号].udi请求号 := 全局变量_气缸请求.udi下个请求号;
全局变量_气缸请求.ast请求[缸号].udi完成号 := 0;
全局变量_气缸请求.ast请求[缸号].w命令 := 命令;
全局变量_气缸请求.ast请求[缸号].w错误 := 0;
全局变量_气缸请求.ast请求[缸号].b自动 := 自动;
全局变量_气缸请求.ast请求[缸号].b待下发 := TRUE;
全局变量_气缸请求.ast请求[缸号].b忙 := TRUE;
气缸_提交 := 全局变量_气缸请求.udi下个请求号;
END_FUNCTION
