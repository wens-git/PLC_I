FUNCTION Axis_Stop : BOOL
VAR_INPUT
    ui轴号 : UINT;
END_VAR
Axis_Stop := Axis_提交(ui轴号 := ui轴号, w命令 := 26, ui槽号 := 0);
END_FUNCTION
