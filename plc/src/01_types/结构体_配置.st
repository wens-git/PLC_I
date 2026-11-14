(* XJV1 retained wire records; runtime state, epochs and display names are
   intentionally absent. Names are owned by the host (protocol 1.2). *)
TYPE 结构体_配置 :
STRUCT
    dw签名 : DWORD;
    aw轴配置 : ARRAY[0..15, 0..15] OF WORD;
    aw气缸配置 : ARRAY[0..53, 0..7] OF WORD;
    aw点位 : ARRAY[0..119, 0..4] OF WORD;
    b已确认 : BOOL;
END_STRUCT
END_TYPE
