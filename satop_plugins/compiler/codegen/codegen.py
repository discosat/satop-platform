import itertools
from ..common.types import *
from ..common import csh
from ..common.cfgbuilder import ControlFlowGraph, Instruction
from ..common import types


class CodeGen:
    """Class for generating code from an expression tree

    Raises:
        NotImplementedError: _description_
    """
    
    cfg = ControlFlowGraph()
    procedures: dict[str, list[csh.CSH_Command]]
    main: list[csh.CSH_Command]
    
    procs: int = 0
    params: dict[type, int] = {}
    
    def __init__(self) -> None:
        self.main = []
        self.procedures = {}
    
    def _next_proc_id(self) -> str:
        """Increments the procedure counter and returns the next procedure id. This is used to ensure unique procedure names.

        Returns:
            string: The next procedure id
        """
        self.procs += 1
        return f"proc${self.procs}"

    def _next_param_id(self, type_: type) -> str:
        """Increments the parameter counter for the given type and returns the next parameter id. This is used to ensure unique parameter identifiers.

        Args:
            type_ (type): The type of the parameter. Makes it easier to distinguish between different types of parameters, as the general arrays for those are separate.

        Returns:
            string: The next parameter id
        """
        if type_ not in self.params:
            self.params[type_] = 0
        
        self.params[type_] += 1
        return f"param${type_.type_name}${self.params[type_]}"
    
    def _next_param(self, type_: type) -> csh.ParamGeneralRegister:
        """Increment the parameter counter for the given type and returns a new parameter object.

        Args:
            type_ (type): Given type of the parameter

        Returns:
            csh.ParamGeneralRegister: General (placeholder) parameter object
        """
        return csh.ParamGeneralRegister(type_, self._next_param_id(type_))
    
    def _sub_proc(self, exps: list[Expression]) -> str:
        """Helper function to generate a sub-procedure from a list of expressions

        Args:
            exps (list[Expression]): List of expressions to be converted to a sub-procedure

        Returns:
            str: Proc slot id of the generated procedure
        """
        body = []
        for x in exps:
            self._code_gen(x, body)
        
        id = self._next_proc_id()
        self.procedures[id] = body
        
        return id

    def _code_gen(self, exp: Expression, procedure: list[csh.CSH_Command]):
        """Recursive function to generate code from an expression tree.
        Instructions are added to the given procedure list, and the control flow graph is built accordingly, keeping track of how params are used by instructions. 
        
        The function builds on a match statement to pattern match the given expression. This must be updated as new expression types are added.

        Args:
            exp (Expression): _description_
            procedure (list[csh.CSH_Command]): _description_

        Raises:
            NotImplementedError: _description_

        Returns:
            None
        """
        match exp:
            case SeqExp():
                for x in exp.exps:
                    self._code_gen(x, procedure)
            
            case RepeatExp():
                body = []
                loop = []

                proc_body_id = self._next_proc_id()
                counter = self._next_param(UInt32)
                limit = self._next_param(UInt32)
                loop_id = self._next_proc_id()


                procedure.append(csh.ProcCall(loop_id))

                cfgprev = self.cfg.current_block
                self.cfg.block_end()

                # CFG Head
                cfghead = self.cfg.block_start("repeat_head", succeeds=cfgprev)

                loop += [
                    csh.ProcSet(counter, UInt32(0)),
                    csh.ProcSet(limit, exp.count),
                    csh.ProcCall(proc_body_id), 
                ]
                self.cfg.add_instruction(Instruction(sets={counter}))
                self.cfg.add_instruction(Instruction(sets={limit}))
                self.cfg.block_end()

                # CFG Body
                cfgbody = self.cfg.block_start("repeat_body", succeeds=cfghead)

                for x in exp.exps:
                    self._code_gen(x, body)
                
                self.procedures[proc_body_id] = body

                self.cfg.block_end()

                
                # CFG Loop check/tail
                cfgtail = self.cfg.block_start("repeat_tail", succeeds=cfgbody)

                loop += [
                    csh.ProcUnop(counter, IncrOp(), counter),
                    csh.ProcIfElse(counter, LtOp(), limit),
                        csh.ProcCall(loop_id),
                        csh.ProcNoop(),
                ]

                self.cfg.add_instruction(Instruction(sets={counter}, uses={counter}))
                self.cfg.add_instruction(Instruction(uses={counter, limit}))
                self.cfg.block_end()
                cfgtail.successors.add(cfghead)
                cfghead.predecessors.add(cfgtail)

                self.procedures[loop_id] = loop
                
                cfgmerge = self.cfg.block_start("repeat_merge", succeeds=cfgtail)
                
            case IfElseExp():
                cfgprev = self.cfg.current_block
                self.cfg.block_end()

                # Head
                cfghead = self.cfg.block_start("if_head", cfgprev)

                procedure.append(csh.ProcIfElse(exp.a, exp.op, exp.b))
                self.cfg.add_instruction(Instruction(uses={exp.a, exp.b}))
                self.cfg.block_end()
                
                def handle_seq(then_or_else, block_name):
                    cfgblock = self.cfg.block_start(f"if_{block_name}", succeeds=cfghead)
                    if isinstance(then_or_else, SeqExp):
                        id = self._sub_proc(then_or_else.exps)
                        procedure.append(csh.ProcCall(id))
                    else:
                        self._code_gen(then_or_else, procedure)
                    self.cfg.block_end()
                    return cfgblock
                
                cfgthen = handle_seq(exp.then, 'then')
                cfgelse = handle_seq(exp.else_, 'else')

                cfgmerge = self.cfg.block_start("if_merge", succeeds=[cfgthen, cfgelse])
                
            
            case WaitTimeExp():
                # Copy current time to a param
                # Add specified time to the param
                # Block until current time is greater than the param
                
                tmp = self._next_param(UInt32)
                tmp2 = self._next_param(UInt32)
                time = csh.ParamRef("time")
                
                # Don't add time to the CFG as it is a hardcoded param name
                procedure.append(csh.ProcUnop(time, IdentLocalOp(), tmp))
                self.cfg.add_instruction(Instruction(sets={tmp}))

                procedure.append(csh.ProcSet(tmp2, exp.time))
                self.cfg.add_instruction(Instruction(sets={tmp2}))

                procedure.append(csh.ProcBinop(tmp, AddOp(), tmp2, tmp))
                self.cfg.add_instruction(Instruction(sets={tmp},uses={tmp, tmp2}))

                procedure.append(csh.ProcBlock(time, GteOp(), tmp))
                self.cfg.add_instruction(Instruction(uses={tmp}))

                
            case ProcSetExp():
                procedure.append(csh.ProcSet(csh.ParamRef(exp.name), exp.value))

            case ProcCaptureImages():
                value = (
                    f"\"CAMERA_TYPE={exp.cameraType.value};"
                    f"CAMERA_ID={exp.cameraID.value};"
                    f"NUM_IMAGES={exp.numOfImages.value};"
                    f"EXPOSURE={exp.exposure.value};"
                    f"ISO={exp.iso.value};"
                    f"INTERVAL={exp.interval.value};\""
                )

                self._code_gen(ProcSetExp("capture_params", String(value)), procedure)

            case _:
                raise NotImplementedError
            
    
    def code_gen(self, exp: Expression) -> list[str]:
        """Main function to generate code from an expression tree. This function is called to start the code generation process and the required sub processes.

        Args:
            exp (Expression): The main expression tree to generate code from
            
        Returns:
            list[str]: The generated code in the form of a list of strings
        """
        
        main_prefix = [
            csh.ProcNew(),
        ]
        
        main_suffix = [
            csh.ProcDel(10),
            csh.ProcPush(10),
            csh.ProcRun(10),
        ]
        
        self.cfg.block_start("main")

        self._code_gen(exp, self.main)

        self.cfg.block_end()
        
        print("Procedures:")
        for k,v in self.procedures.items():
            print(k)
            for x in v:
                print(f"\t{x}")
        
        print("Main:")
        for x in self.main:
            print(f"\t{x}")
        
        def all_subclasses(cls):
            return set(cls.__subclasses__()).union(
                [s for c in cls.__subclasses__() for s in all_subclasses(c)])
        
        # Register allocation:
        color_maps = self.cfg.calc_liveness()
        
        param_map = dict()
        for reg, color_map in color_maps.items():
            for param, i in color_map.items():
                for typ in all_subclasses(types.ParamType):
                    if typ.register_name == reg and typ.num_registers <= i:
                        raise Exception("Not enough registers for ", reg, f"({i}/{typ.num_registers})")
                ref = csh.ParamRef(reg, i)
                param_map[param] = ref
        

        # TODO: Slot allocation

        MAIN_SLOT_ID = 10
        MIN_SLOT_ID = 11
        MAX_SLOT_ID = 255
        AVAIL_SLOT_IDS = MAX_SLOT_ID - MIN_SLOT_ID

        # get all proc slots
        temp_slots = list(self.procedures.keys()).copy()
        if len(temp_slots) > AVAIL_SLOT_IDS:
            raise Exception('Not enough slots. Too many procedures generated')
        
        slot_map = dict()
        for i, k in enumerate(temp_slots):
            n = i + MIN_SLOT_ID
            slot_map[k] = n
            self.procedures[n] = self.procedures.pop(k)

        ## Use itertools to iterate over all commands in main and procedures as if a single list
        for cmd in itertools.chain(self.main, itertools.chain.from_iterable(self.procedures.values())):
            print(cmd)
            cmd.update_params(param_map)
            cmd.update_slots(slot_map)
        
        
        print("POST COLORING:")
        
        print("Procedures:")
        for k,v in self.procedures.items():
            print(k)
            for x in v:
                print(f"\t{x}")
        
        print("Main:")
        for x in self.main:
            print(f"\t{x}")
        
        
        
        # TODO: From python objects to lines of code 
        


        REMOTE_NODE = 12

        instruction_list: list[csh.CSH_Command] = []

        def add_proc(proc_id, instructions):
            instruction_list.append(csh.ProcDel(proc_id, REMOTE_NODE))
            instruction_list.append(csh.ProcNew())
            for instr in instructions:
                instruction_list.append(instr)
            instruction_list.append(csh.ProcPush(proc_id, REMOTE_NODE))

        add_proc(MAIN_SLOT_ID, self.main)
        for proc, instructions in self.procedures.items():
            add_proc(proc, instructions)
        
        instruction_list.append(csh.ProcRun(MAIN_SLOT_ID, REMOTE_NODE))

        commands: list[str] = []

        for instruction in instruction_list:
            commands.append(instruction.command_string())


        return commands
        