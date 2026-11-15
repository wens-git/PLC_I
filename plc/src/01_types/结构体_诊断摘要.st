(* Current-scan derived limits and alarms. Edge history belongs to Diagnostics. *)
TYPE 结构体_诊断摘要 :
STRUCT
    aw限位 : ARRAY[0..15] OF WORD;
    w报警数 : WORD;
    w首报警 : WORD;
    w首报警对象 : WORD;
END_STRUCT
END_TYPE
