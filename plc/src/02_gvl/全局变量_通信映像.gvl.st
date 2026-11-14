(* Process images of the official ModbusTCP_Slave_XJV1 device (Ethernet,
   port 1502). The import script maps the holding-register channel (id 1000)
   -> aw保持区 and the input-register channel (id 2000) -> aw发布区; do not add
   AT addresses here. Non-retained by design:
   a power cycle must never replay a command.
   aw保持区 is written only by the Modbus master; the application only reads it.
   aw发布区 is written only by 功能块_服务端. *)
VAR_GLOBAL
    aw保持区 : ARRAY[0..31] OF WORD;
    aw发布区 : ARRAY[0..1829] OF WORD;
END_VAR