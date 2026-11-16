(* Single control-task mailbox. Never persist or write from another task. *)
{attribute 'qualified_only'}
VAR_GLOBAL
    ast请求 : ARRAY[0..15] OF 结构体_轴请求;
END_VAR
