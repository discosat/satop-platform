class ParamType:
    value = None
    type_name = None
    register_name = None
    num_registers = 0
    def __init__(self, value) -> None:
        self.value = value
        
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"({self.type_name}) {self.value}"

class IntParamType(ParamType):
    min_val = None
    max_val = None
    
    def __init__(self, value):
        if self.min_val is not None and value < self.min_val:
            raise ValueError(f"Value {value} is less than minimum value {self.min_val}")
        if self.max_val is not None and value > self.max_val:
            raise ValueError(f"Value {value} is greater than maximum value {self.max_val}")

        super().__init__(value)

class Int8(IntParamType):
    min_val = -128
    max_val =  127
    type_name = "I8"
    register_name = "_p_int8"
    num_registers = 32

class Int16(IntParamType):
    min_val = -32_768
    max_val =  32_767
    type_name = "I16"
    register_name = "_p_int16"
    num_registers = 32

class Int32(IntParamType):
    min_val = -2_147_483_648
    max_val =  2_147_483_647
    type_name = "I32"
    register_name = "_p_int32"
    num_registers = 32

class Int64(IntParamType):
    min_val = -9_223_372_036_854_775_808
    max_val =  9_223_372_036_854_775_807
    type_name = "I64"
    register_name = "_p_int64"
    num_registers = 32

class UInt8(IntParamType):
    min_val = 0
    max_val = 255
    type_name = "U8"
    register_name = "_p_uint8"
    num_registers = 32

class UInt16(IntParamType):
    min_val = 0
    max_val = 65_535
    type_name = "U16"
    register_name = "_p_uint16"
    num_registers = 32

class UInt32(IntParamType):
    min_val = 0
    max_val = 4_294_967_295
    type_name = "U32"
    register_name = "_p_uint32"
    num_registers = 32

class UInt64(IntParamType):
    min_val = 0
    max_val = 18_446_744_073_709_551_615
    type_name = "U64"
    register_name = "_p_uint64"
    num_registers = 32

class Float32(ParamType):
    type_name = "Float"
    register_name = "_p_float"
    num_registers = 32

class Double64(ParamType):
    type_name = "Double"
    register_name = "_p_double"
    num_registers = 16

class String(ParamType):
    type_name = "String"
    register_name = "_p_string"
    num_registers = 32

class OperandType:
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return f"{type(self).__name__}"

class ComparisonOp(OperandType):
    pass

class EqOp(ComparisonOp):
    def __str__(self):
        return "=="

class NeqOp(ComparisonOp):
    def __str__(self):
        return "!="
    
class LtOp(ComparisonOp):
    def __str__(self):
        return "<"

class GtOp(ComparisonOp):
    def __str__(self):
        return ">"

class LteOp(ComparisonOp):
    def __str__(self):
        return "<="

class GteOp(ComparisonOp):
    def __str__(self):
        return ">="

class BinaryOp(OperandType):
    pass

class AddOp(BinaryOp):
    def __str__(self):
        return "+"
    
class SubOp(BinaryOp):
    def __str__(self):
        return "-"

class MulOp(BinaryOp):
    def __str__(self):
        return "*"

class DivOp(BinaryOp):
    def __str__(self):
        return "/"
    
class ModOp(BinaryOp):
    def __str__(self):
        return "%"

class LshiftOp(BinaryOp):
    def __str__(self):
        return "<<"

class RshiftOp(BinaryOp):
    def __str__(self):
        return ">>"

class BitAndOp(BinaryOp):
    def __str__(self):
        return "&"

class BitOrOp(BinaryOp):
    def __str__(self):
        return "|"

class BitXorOp(BinaryOp):
    def __str__(self):
        return "^"

class UnaryOp(OperandType):
    pass

class IncrOp(UnaryOp):
    def __str__(self):
        return "++"

class DecrOp(UnaryOp):
    def __str__(self):
        return "--"

class NegOp(UnaryOp):
    def __str__(self):
        return "-"

class NotOp(UnaryOp):
    def __str__(self):
        return "!"

class IdentLocalOp(UnaryOp):
    def __str__(self):
        return "idt"

class IdentRemoteOp(UnaryOp):
    def __str__(self):
        return "rmt"





class Expression:
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return f"{type(self).__name__}()"

    def __pprint__(self, depth=0):
        return [(depth, self.__str__())]
    
    def pprint(self, depth=0, indent=2):
        lines = []
        for d, s in self.__pprint__(depth):
            lines.append(" " * indent * d + s)

        return "\n".join(lines)


class ParamExp(Expression):
    def __init__(self, val: ParamType):
        self.val: ParamType = val
    
    def __str__(self):
        return f"ParamExp({self.val})"


class NoopExp(Expression):
    pass


class SeqExp(Expression):
    def __init__(self, exps):
        self.exps = exps

    def __str__(self):
        return f"SeqExp({self.exps})"

    def __pprint__(self, depth=0):
        lines = [(depth, "SeqExp([")]
        for x in self.exps:
            lines += x.__pprint__(depth+1)
        lines.append((depth, "])"))

        return lines

class IfElseExp(Expression):
    def __init__(self, a, op, b, then, else_):
        self.a = a
        self.b = b
        self.op = op
        self.then = then
        self.else_ = else_
        
        self.cond = f"{self.a} {self.op} {self.b}"
    
    def __str__(self):
        return f"IfElseExp({self.cond}, {self.then}, {self.else_})"

    def __pprint__(self, depth=0):
        return [
            (depth, f"IfElseExp({self.cond}"),
            self.then.__pprint__(depth+1),
            self.else_.__pprint__(depth+1),
            (depth, ")")
        ]

class WaitTimeExp(Expression):
    time: UInt32
    def __init__(self, time: UInt32):
        self.time = time
    
    def __str__(self):
        return f"WaitTimeExp({self.time})"

class RepeatExp(Expression):
    count: UInt32
    exps: list[Expression]
    def __init__(self, count: UInt32, exps: list[Expression]):
        self.count = count
        self.exps = exps
    
    def __str__(self):
        return f"RepeatExp({self.count}, {self.exps})"

    def __pprint__(self, depth=0):
        lines = [(depth, f"RepeatExp({self.count}, [")]
        for x in self.exps:
            lines += x.__pprint__(depth+1)
        lines.append((depth, "])"))

        return lines


class ProcSetExp(Expression):
    name: str
    value: ParamType
    def __init__(self, name: str, value: ParamType):
        self.name = name
        self.value = value
    
    def __str__(self):
        return f"ProcSetExp({self.name}, {self.value})"

class ProcCaptureImages(Expression):
    """
    Args:
        cameraID (String): The model of the camera to capture with.
        cameraType (String): The camera type to capture with.
        exposure (int): Exposure in microseconds.
        iso (float): ISO or gain.
        numOfImages (int): Number of images to capture.
        interval (int): Delay between images in microseconds (excluding exposure).
    """
    cameraID: String
    cameraType: String
    exposure: Int64
    iso: Double64
    numOfImages: Int64
    interval: Int64

    def __init__(self, cameraID: String, cameraType: String, exposure: Int64, iso: Double64, numOfImages: Int64, interval: Int64):
        self.cameraID = cameraID
        self.cameraType = cameraType
        self.exposure = exposure
        self.iso = iso
        self.numOfImages = numOfImages
        self.interval = interval

    def __str__(self):
        return f"ProcCaptureImages({self.cameraID}, {self.cameraType}, {self.exposure}, {self.iso}, {self.numOfImages}, {self.interval})"
