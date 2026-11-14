TYPE 结构体_气缸请求 :
STRUCT
    udi请求号 : UDINT;
    udi完成号 : UDINT;
    w命令 : WORD;
    w错误 : WORD;
    b自动 : BOOL;
    b待下发 : BOOL;
    b忙 : BOOL;
END_STRUCT
END_TYPE
