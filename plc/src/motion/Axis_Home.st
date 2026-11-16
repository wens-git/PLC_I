FUNCTION Axis_Home : BOOL
VAR_INPUT
    ui轴号 : UINT;
END_VAR
Axis_Home := Axis_提交(ui轴号 := ui轴号, w命令 := 22, ui槽号 := 0);
END_FUNCTION
