(* 一次查询返回设备最近一次请求的状态，避免三个函数重复比对令牌。 *)
TYPE 结构体_Cy状态 :
STRUCT
    b忙 : BOOL;
    b完成 : BOOL;
    w故障 : WORD;
END_STRUCT
END_TYPE
