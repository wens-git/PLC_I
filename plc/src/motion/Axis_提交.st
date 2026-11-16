(* 轴业务API的唯一入槽入口；许可仍由服务端消费时统一校验。
   停止可覆盖忙请求，保留取消错误19；普通请求不覆盖忙槽。 *)
FUNCTION Axis_提交 : BOOL
VAR_INPUT
    ui轴号 : UINT;
    w命令 : WORD;
    ui槽号 : UINT;
END_VAR
Axis_提交 := FALSE;
IF ui轴号 >= 16 THEN RETURN; END_IF;
IF (w命令 <> 22) AND (w命令 <> 29) AND (w命令 <> 26) THEN RETURN; END_IF;
IF (w命令 <> 26) AND 全局变量_轴请求.ast请求[ui轴号].b忙 THEN RETURN; END_IF;
全局变量_轴请求.ast请求[ui轴号].b完成 := FALSE;
全局变量_轴请求.ast请求[ui轴号].w错误 := 0;
IF w命令 = 29 THEN
    IF ui槽号 >= 120 THEN
        全局变量_轴请求.ast请求[ui轴号].w错误 := 9;
        RETURN;
    END_IF;
    全局变量_轴请求.ast请求[ui轴号].ui槽号 := ui槽号;
ELSIF w命令 = 26 THEN
    全局变量_轴请求.ast请求[ui轴号].w错误 := 19;
END_IF;
全局变量_轴请求.ast请求[ui轴号].w命令 := w命令;
全局变量_轴请求.ast请求[ui轴号].b忙 := TRUE;
全局变量_轴请求.ast请求[ui轴号].b已下发 := FALSE;
全局变量_轴请求.ast请求[ui轴号].b已接收 := FALSE;
Axis_提交 := TRUE;
END_FUNCTION
