(* Import as the application's persistent variable list; never map it writable
   through Modbus. One control task owns all access to these retained records. *)
VAR_GLOBAL PERSISTENT RETAIN
    Store : 结构体_配置;
END_VAR
