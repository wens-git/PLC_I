(* 唯一工程配置源。全部默认未绑定；经现场核验后填写类型与X/Y编号。
   绑定不是模块在线。模块就绪由实际IO诊断单独提供，不得从本表推导。 *)
{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    lw绑定 : LWORD := 0;
    aw类型 : ARRAY[0..53] OF WORD := [54(0)];
    aw动点输出 : ARRAY[0..53] OF WORD := [54(65535)];
    aw原点输出 : ARRAY[0..53] OF WORD := [54(65535)];
    aw动点输入 : ARRAY[0..53] OF WORD := [54(65535)];
    aw原点输入 : ARRAY[0..53] OF WORD := [54(65535)];
END_VAR
