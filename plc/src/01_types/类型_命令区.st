(* Import each TYPE as a separate DUT in XS Studio.
   Both images are zero-based and match the official ModbusTCP Slave Device:
   类型_命令区  = Holding Register 0..31 (host writes, PLC reads %IW),
   类型_发布区 = Input Register 0..1829 (PLC writes %QW, host FC04 reads).
   Server publishes through the generated XJV1_*_BASE constants directly. *)
TYPE 类型_命令区 : ARRAY[0..31] OF WORD; END_TYPE
TYPE 类型_发布区 : ARRAY[0..1829] OF WORD; END_TYPE
