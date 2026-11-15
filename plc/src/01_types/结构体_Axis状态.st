(* 轴接口状态：忙、完成、错误一次返回。 *)
TYPE 结构体_Axis状态 :
STRUCT
    b忙 : BOOL;
    b完成 : BOOL;
    b错误 : BOOL;
    w错误码 : WORD;
END_STRUCT
END_TYPE
