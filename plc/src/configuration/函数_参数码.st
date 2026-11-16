(* 把笼统的 9（参数超出范围）细分到具体额定值字段。

   2/3 都是速度字段（回原速度 / 运行速度），都对照 audi额定速度；
   4/5/6 分别是加速度、减速度、停止减速度。 *)
FUNCTION 函数_参数码 : WORD
VAR_INPUT
    Field : UINT;
END_VAR
CASE Field OF
    2, 3: 函数_参数码 := 22;
    4: 函数_参数码 := 23;
    5: 函数_参数码 := 24;
    6: 函数_参数码 := 25;
ELSE
    函数_参数码 := 9;
END_CASE
END_FUNCTION
