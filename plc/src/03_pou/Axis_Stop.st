FUNCTION Axis_Stop : BOOL
VAR_INPUT
    ui轴号 : UINT;
END_VAR

Axis_Stop := FALSE;
IF ui轴号 >= 16 THEN RETURN; END_IF;
全局变量_轴请求.ast请求[ui轴号].b完成 := FALSE;
全局变量_轴请求.ast请求[ui轴号].w错误 := 19;
全局变量_轴请求.ast请求[ui轴号].w命令 := 26;
全局变量_轴请求.ast请求[ui轴号].b忙 := TRUE;
全局变量_轴请求.ast请求[ui轴号].b已下发 := FALSE;
全局变量_轴请求.ast请求[ui轴号].b已接收 := FALSE;
Axis_Stop := TRUE;
END_FUNCTION
