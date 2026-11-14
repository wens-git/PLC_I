"""Single-owner pymodbus transport with automatic write retries disabled."""
from pymodbus.client import ModbusTcpClient as Client


class ModbusTcpClient:
    def __init__(self, host, port=1502, unit=1, timeout=0.3):
        self.client = Client(host, port=port, timeout=timeout, retries=0)
        self.unit = unit

    def connect(self):
        if not self.client.connect():
            raise ConnectionError(f"无法连接PLC {self.client.comm_params.host}:{self.client.comm_params.port}（检查IP、网线、PLC是否运行、Modbus从站端口）")

    def close(self):
        self.client.close()

    def _check(self, response, function):
        if response is None or response.isError():
            raise ConnectionError(f"Modbus请求失败（功能码 {function}）：{response}")
        if response.function_code != function or response.dev_id != self.unit:
            raise ConnectionError(f"Modbus应答的功能码或站号与请求（FC{function:02d}/站号{self.unit}）不一致")
        return response

    def read_holding(self, address, count):
        if not 1 <= count <= 125:
            raise ValueError("FC03数量超出范围")
        result = self._check(self.client.read_holding_registers(address, count=count, device_id=self.unit), 3)
        if len(result.registers) != count:
            raise ConnectionError("Modbus读取长度不匹配")
        return result.registers

    def read_input(self, address, count):
        if not 1 <= count <= 125:
            raise ValueError("FC04数量超出范围")
        result = self._check(self.client.read_input_registers(address, count=count, device_id=self.unit), 4)
        if len(result.registers) != count:
            raise ConnectionError("Modbus输入寄存器读取长度不匹配")
        return result.registers

    def write_holding(self, address, values):
        if not 1 <= len(values) <= 123:
            raise ValueError("FC16数量超出范围")
        result = self._check(self.client.write_registers(address, values, device_id=self.unit), 16)
        if result.address != address or result.count != len(values):
            raise ConnectionError(f"FC16写入应答地址/数量与请求（{address}/{len(values)}）不符，写入结果未知")

    def write_single(self, address, value):
        result = self._check(self.client.write_register(address, value, device_id=self.unit), 6)
        if result.address != address or result.registers != [value]:
            raise ConnectionError(f"FC06写入应答与请求（地址 {address}）不符，写入结果未知")
