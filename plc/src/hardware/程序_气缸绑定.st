(* 把 Cy 配置表换算成绑定掩码与协议配置。每扫描最先执行。
   一行配置决定：是否绑定、阀型、两侧点地址和确认方式。
   选 Cy确认.延时 的一侧不绑定输入，由动作计时完成。 *)
PROGRAM 程序_气缸绑定
VAR
    i : UINT;
    w类型 : WORD;
    w动点输出 : WORD;
    w原点输出 : WORD;
    w动点输入 : WORD;
    w原点输入 : WORD;
    lw绑定 : LWORD;
END_VAR

lw绑定 := 0;
FOR i := 0 TO 53 DO
    w类型 := 0;
    w动点输出 := WORD#16#FFFF;
    w原点输出 := WORD#16#FFFF;
    w动点输入 := WORD#16#FFFF;
    w原点输入 := WORD#16#FFFF;
    IF 全局变量_气缸工程.Cy气缸配置[i].已绑定 THEN
        lw绑定 := lw绑定 OR SHL(LWORD#1, i);
        CASE 全局变量_气缸工程.Cy气缸配置[i].e阀型 OF
            Cy阀型.双线圈保持: w类型 := 1;
            Cy阀型.真空吸附: w类型 := 2;
            Cy阀型.真空带破真空: w类型 := 3;
        ELSE
            w类型 := 0;
        END_CASE;
        w动点输出 := 全局变量_气缸工程.Cy气缸配置[i].out动点;
        IF (w类型 = 1) OR (w类型 = 3) THEN
            w原点输出 := 全局变量_气缸工程.Cy气缸配置[i].out原点;
        END_IF;
        IF 全局变量_气缸工程.Cy气缸配置[i].e动点确认 = Cy确认.传感器 THEN
            w动点输入 := 全局变量_气缸工程.Cy气缸配置[i].in动点;
        END_IF;
        IF 全局变量_气缸工程.Cy气缸配置[i].e原点确认 = Cy确认.传感器 THEN
            w原点输入 := 全局变量_气缸工程.Cy气缸配置[i].in原点;
        END_IF;
        IF 全局变量_气缸工程.Cy气缸配置[i].动点反相 THEN w类型 := w类型 OR WORD#16#0004; END_IF;
        IF 全局变量_气缸工程.Cy气缸配置[i].原点反相 THEN w类型 := w类型 OR WORD#16#0008; END_IF;
    END_IF;
    (* 工程值变化时清掉现场确认，要求重新确认后才能进入自动流程。 *)
    IF (全局变量_保持区.Store.aw气缸配置[i, 0] <> w类型)
        OR (全局变量_保持区.Store.aw气缸配置[i, 1] <> w动点输出)
        OR (全局变量_保持区.Store.aw气缸配置[i, 2] <> w原点输出)
        OR (全局变量_保持区.Store.aw气缸配置[i, 3] <> w动点输入)
        OR (全局变量_保持区.Store.aw气缸配置[i, 4] <> w原点输入) THEN
        全局变量_保持区.Store.b已确认 := FALSE;
    END_IF;
    全局变量_保持区.Store.aw气缸配置[i, 0] := w类型;
    全局变量_保持区.Store.aw气缸配置[i, 1] := w动点输出;
    全局变量_保持区.Store.aw气缸配置[i, 2] := w原点输出;
    全局变量_保持区.Store.aw气缸配置[i, 3] := w动点输入;
    全局变量_保持区.Store.aw气缸配置[i, 4] := w原点输入;
END_FOR;
全局变量_绑定.lw已绑定气缸 := lw绑定;
END_PROGRAM
