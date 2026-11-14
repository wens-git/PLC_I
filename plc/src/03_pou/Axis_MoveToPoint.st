FUNCTION Axis_MoveToPoint : BOOL
VAR_INPUT
    ui轴号 : UINT;
    ui槽号 : UINT;
END_VAR

Axis_MoveToPoint := FALSE;
IF ui轴号 >= 16 THEN RETURN; END_IF;
IF 全局变量_轴请求.ast请求[ui轴号].b忙 THEN RETURN; END_IF;
全局变量_轴请求.ast请求[ui轴号].b完成 := FALSE;
全局变量_轴请求.ast请求[ui轴号].w错误 := 0;
IF ui槽号 >= 120 THEN
    全局变量_轴请求.ast请求[ui轴号].w错误 := 9;
    RETURN;
END_IF;
全局变量_轴请求.ast请求[ui轴号].ui槽号 := ui槽号;
全局变量_轴请求.ast请求[ui轴号].w命令 := 29;
全局变量_轴请求.ast请求[ui轴号].b忙 := TRUE;
全局变量_轴请求.ast请求[ui轴号].b已下发 := FALSE;
全局变量_轴请求.ast请求[ui轴号].b已接收 := FALSE;
Axis_MoveToPoint := TRUE;
END_FUNCTION
