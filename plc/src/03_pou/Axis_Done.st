FUNCTION Axis_Done : BOOL
VAR_INPUT
    ui轴号 : UINT;
END_VAR

Axis_Done := FALSE;
IF ui轴号 >= 16 THEN RETURN; END_IF;
Axis_Done := 全局变量_轴请求.ast请求[ui轴号].b完成;
END_FUNCTION
