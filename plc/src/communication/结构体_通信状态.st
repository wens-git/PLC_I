(* Volatile protocol result owned by Server. Publication reads this small value
   after arbitration; no Runtime/Store snapshot is retained in a child FB. *)
TYPE 结构体_通信状态 :
STRUCT
    w应答序列 : WORD;
    w应答结果 : WORD;
    w应答对象 : WORD;
    w应答纪元 : WORD;
    w上次拒绝 : WORD;
    w配置纪元 : WORD;
    bHMI在线 : BOOL;
    b点动忙 : BOOL;
END_STRUCT
END_TYPE
