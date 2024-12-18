from .types import *


class CSH_Command:
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return f"{type(self).__name__}"

    def __node_str__(self):
        return f" [{self.node}]" if self.node else ""
    
    def update_params(self, param_map: dict):
        pass
    
    def update_slots(self, slot_map: dict):
        pass

    def command_string(self):
        return f"# undefined {type(self).__name__}"

class ParamRef:
    name: str
    array_idx: int|None
    
    def __init__(self, name: str, array_idx: int|None = None):
        self.name = name
        self.array_idx = array_idx
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return f"{self.name}" + (f"[{self.array_idx}]" if self.array_idx is not None else "")

class ParamGeneralRegister(ParamRef):
    type_: ParamType
    def __init__(self, type_: type, name: str):
        if not issubclass(type_, ParamType):
            raise ValueError(f"Expected a subclass of ParamType, got {type_}")
        self.type_ = type_
        super().__init__(name)

    def __str__(self):
        return f"({self.type_.__name__}) {self.name}"



# Proc Procedure Management Commands

class ProcNew(CSH_Command):
    def command_string(self):
        return f"proc new"


class ProcDel(CSH_Command):
    def __init__(self, slot, node=0):
        self.slot = slot
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.slot}" + self.__node_str__()

    def update_slots(self, slot_map: dict):
        if self.slot in slot_map:
            self.slot = slot_map[self.slot]

    def command_string(self):
        return f"proc del {self.slot}" + (f" {self.node}" if self.node else "")

class ProcPull(CSH_Command):
    def __init__(self, slot, node=0):
        self.slot = slot
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.slot}" + self.__node_str__()

    def update_slots(self, slot_map: dict):
        if self.slot in slot_map:
            self.slot = slot_map[self.slot]

    def command_string(self):
        return f"proc pull {self.slot}" + (f" {self.node}" if self.node else "")

class ProcPush(CSH_Command):
    def __init__(self, slot, node=0):
        self.slot = slot
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.slot}" + self.__node_str__()

    def update_slots(self, slot_map: dict):
        if self.slot in slot_map:
            self.slot = slot_map[self.slot]

    def command_string(self):
        return f"proc push {self.slot}" + (f" {self.node}" if self.node else "")

class ProcRun(CSH_Command):
    def __init__(self, slot, node=0):
        self.slot = slot
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.slot}" + self.__node_str__()

    def update_slots(self, slot_map: dict):
        if self.slot in slot_map:
            self.slot = slot_map[self.slot]

    def command_string(self):
        return f"proc run {self.slot}" + (f" {self.node}" if self.node else "")

## Mostly for manual control 
class ProcPop(CSH_Command):
    def __init__(self, instruction_index=None):
        self.idx = instruction_index

    def command_string(self):
        if self.node == 0:
            return f"proc pop"

class ProcSize(CSH_Command):
    def __init__(self) -> None:
        super().__init__()
        raise NotImplementedError

class ProcList(CSH_Command):
    def __init__(self) -> None:
        super().__init__()
        raise NotImplementedError

class ProcSlots(CSH_Command):
    def __init__(self, node=0):
        self.node = node
    
    def __str__(self):
        return super().__str__() + self.__node_str__()

    def command_string(self):
        return f"proc run {self.slot}" + (f" {self.node}" if self.node else "")


# Proc Control-Flow and Arithmetic Operations
"""


    proc block <param a> <op> <param b> [node]: Blocks execution of the procedure until the specified condition is met. <op> can be one of: ==, !=, <, >, <=, >=.

    proc ifelse <param a> <op> <param b> [node]: Skips the next instruction if the condition is not met, and the following instruction if it is met. This command cannot be nested in the default runtime - i.e. it cannot be used again within the following 2 instructions.

    proc noop: Performs no operation. Useful in combination with ifelse instructions.

    proc set <param> <value> [node]: Sets the value of a parameter. The type of value is always inferred from the libparam type of the parameter.

    proc unop <param> <op> <result> [node]: Applies a unary operator to a parameter and stores the result. <op> can be one of: ++, --, !, -, idt, rmt. idt and rmt are both identity operators.

    proc binop <param a> <op> <param b> <result> [node]: Applies a binary operator to parameters <param a> and <param b> and stores the result. <op> can be one of: +, -, *, /, %, <<, >>, &, |, ^.

    proc call <procedure slot> [node]: Inserts an instruction to run the procedure in the specified slot.

"""

class ProcBlock(CSH_Command):
    __match_args__ = ('a', 'op', 'b', 'node')
    def __init__(self, a, op:ComparisonOp, b, node=0):
        self.a = a
        self.op = op
        self.b = b
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.a} {self.op} {self.b}" + self.__node_str__()
    
    def update_params(self, param_map: dict):
        for k,v in param_map.items():
            if k == self.a:
                self.a = v
            if k == self.b:
                self.b = v

    def command_string(self):
        return f"proc block {self.a} {self.op} {self.b}" + (f" {self.node}" if self.node else "")

class ProcIfElse(CSH_Command):
    __match_args__ = ('a', 'op', 'b', 'node')
    def __init__(self, a, op:ComparisonOp , b, node=0):
        self.a = a
        self.op = op
        self.b = b
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.a} {self.op} {self.b}" + self.__node_str__()
    
    def update_params(self, param_map: dict):
        for k,v in param_map.items():
            if k == self.a:
                self.a = v
            if k == self.b:
                self.b = v

    def command_string(self):
        return f"proc ifelse {self.a} {self.op} {self.b}" + (f" {self.node}" if self.node else "")

class ProcNoop(CSH_Command):
    def command_string(self):
        return "proc noop"

class ProcSet(CSH_Command):
    __match_args__ = ('param', 'value', 'node')
    def __init__(self, param:ParamRef, value:ParamType, node=0):
        self.param = param
        self.value = value
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.param} {self.value}" + self.__node_str__()
    
    def update_params(self, param_map: dict):
        for k,v in param_map.items():
            if k == self.param:
                self.param = v

    def command_string(self):
        return f"proc set {self.param} {self.value.value}" + (f" {self.node}" if self.node else "")

class ProcUnop(CSH_Command):
    __match_args__ = ('param', 'op', 'result', 'node')
    def __init__(self, param:ParamRef, op:UnaryOp, result:ParamRef, node=0):
        self.param = param
        self.op = op
        self.result = result
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.param} {self.op} {self.result}" + self.__node_str__()
    
    def update_params(self, param_map: dict):
        for k,v in param_map.items():
            if k == self.param:
                self.param = v
            if k == self.result:
                self.result = v

    def command_string(self):
        return f"proc unop {self.param} {self.op} {self.result}" + (f" {self.node}" if self.node else "")

class ProcBinop(CSH_Command):
    __match_args__ = ('a', 'op', 'b', 'result', 'node')
    def __init__(self, a:ParamRef, op:BinaryOp, b:ParamRef, result:ParamRef, node=0):
        self.a = a
        self.op = op
        self.b = b
        self.result = result
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.a} {self.op} {self.b} {self.result}" + self.__node_str__()
    
    def update_params(self, param_map: dict):
        for k,v in param_map.items():
            if k == self.a:
                self.a = v
            if k == self.b:
                self.b = v
            if k == self.result:
                self.result = v

    def command_string(self):
        return f"proc binop {self.a} {self.op} {self.b} {self.result}" + (f" {self.node}" if self.node else "")

class ProcCall(CSH_Command):
    __match_args__ = ('slot', 'node')
    def __init__(self, slot, node=0):
        self.slot = slot
        self.node = node
    
    def __str__(self):
        return super().__str__() + f" {self.slot}" + self.__node_str__()
    
    def update_slots(self, slot_map: dict):
        if self.slot in slot_map:
            self.slot = slot_map[self.slot]

    def command_string(self):
        return f"proc call {self.slot}" + (f" {self.node}" if self.node else "")