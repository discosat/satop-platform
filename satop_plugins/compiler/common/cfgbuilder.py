import networkx as nx
import itertools

from ..common.csh import ParamGeneralRegister


class Instruction:
    """Instructino class for the Control Flow Graph. 
    Needed for liveness analysis, with wich params are 
    used and set, and their liveness during analysis.
    """
    sets: set
    uses: set
    live_in: set
    live_out: set

    def __init__(self, sets=None, uses=None) -> None:
        if not sets:
            sets = set()
        if not uses:
            uses = set()
        self.sets = sets
        self.uses = uses
        self.live_in = set()
        self.live_out = set()

    def __str__(self) -> str:
        return f"Instruction(sets {self.sets}, uses {self.uses})"

    def __repr__(self) -> str:
        return self.__str__()


class Block:
    """A block/node in the control flow graph. Contains a set of instructions, 
    and are implemented as a doubly linked list for traversal with preceeding 
    and succeeding blocks.
    """
    name: str

    live_in: set
    live_out: set

    instructions: list[Instruction]
    predecessors: set
    successors: set

    def __init__(self, name) -> None:
        self.name = name
        self.instructions = []
        self.predecessors = set()
        self.successors = set()
        self.live_in = set()
        self.live_out = set()

    def __str__(self) -> str:
        return f"Block({self.name}, {self.instructions})"

    def __repr__(self) -> str:
        return self.__str__()

    def add_instruction(self, instruction):
        self.instructions.append(instruction)


class ControlFlowGraph:
    """Control flow graph used for liveness analysis and register allocation.
    """
    blocks: list[Block]
    current_block: Block

    block_id: int

    sub_graphs: list

    def __init__(self):
        self.blocks = []
        self.current_block = None
        self.block_id = 0
        self.sub_graphs = []

    def __str__(self) -> str:
        return (
            "ControlFlowGraph(\n\t"
            + "\n\t".join([str(x) for x in self.blocks])
            + "\n)"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def block_start(self, name: str, succeeds: Block | list[Block] = None) -> Block:
        """Begin a new block in the control flow graph.
        A previous block must be closed before starting a new one.

        Args:
            name (str): A name for the block. Useful for debugging.
            succeeds (Block | list[Block], optional): Specify to automatically create links to/from one or more predecessors. Defaults to None.

        Raises:
            Exception: "Block not terminated" if a block is already open.

        Returns:
            Block: The newly created block
        """
        if self.current_block:
            raise Exception("Block not terminated")

        self.current_block = Block(name + "#" + str(self.block_id))
        self.block_id += 1
        if succeeds:
            if isinstance(succeeds, list):
                for s in succeeds:
                    self.current_block.predecessors.add(s)
                    s.successors.add(self.current_block)
            else:
                self.current_block.predecessors.add(succeeds)
                succeeds.successors.add(self.current_block)
        return self.current_block

    def block_end(self) -> None:
        """End the current block. A block must already have been opened with block_start()

        Raises:
            Exception: If no block is open, an exception is raised.
        """
        if not self.current_block:
            raise Exception(
                "No block to end. Current blocks: " + str(self.blocks))
        self.blocks.append(self.current_block)
        self.current_block = None

    def add_instruction(self, instruction: Instruction):
        """Add an instruction to the currently open block. A block must be open.

        Args:
            instruction (Instruction): The instruction to add

        Raises:
            Exception: If no block is open, an exception is raised.
        """
        if not self.current_block:
            raise Exception("No block to add instruction to")
        self.current_block.add_instruction(instruction)

    def calc_liveness_global(self):
        """First step of the liveness analysis algorithm, 
        calculating liveness for the entire control flow graph, between blocks. 
        """
        
        # General principle of liveness analysis can be found online. The following 
        # video can be a good starting point for better understanding: 
        # https://www.youtube.com/watch?v=eeXk_ec1n6g
        
        
        '''
        Set equations for liveness analysis. 
        Repeat for each block until no changes are made.
        Apparently quicker convergence when done in reverse order.
        
        live_in = use(n) U (live_out - def(n))
        live_out = U (for all s in succ(n)) live_in(s)
        '''
        i = 0
        while True:
            print("Calculating liveness...", i)
            i += 1
            changed = False
            for block in reversed(self.blocks):
                print(f"Calculating liveness for block {block.name}")
                print(f"Old live_in: {block.live_in}")
                print(f"Old live_out: {block.live_out}")

                old_live_out = block.live_out.copy()
                old_live_in = block.live_in.copy()
                block.live_out = set()
                for s in block.successors:
                    block.live_out |= s.live_in

                block.live_in = block.live_out.copy()
                for instruction in reversed(block.instructions):
                    print(instruction)
                    block.live_in -= instruction.sets
                    block.live_in |= instruction.uses

                print(f"New live_in: {block.live_in}")
                print(f"New live_out: {block.live_out}\n")

                if block.live_out != old_live_out or block.live_in != old_live_in:
                    changed = True
            if not changed:
                break

    def calc_liveness_local(self, block: Block) -> "ControlFlowGraph":
        """Calculate liveness inside a single block. This is the 
        second step of the liveness analysis algorithm and must 
        be run after calc_liveness_global().
        
        This creates a small control flow graph for the block, with3 
        each instruction put in its own block. This enables more
        code reuse.

        Args:
            block (Block): The block to analyse

        Returns:
            ControlFlowGraph: The local control flow graph with liveness information of the block
        """
        local_cfg = ControlFlowGraph()
        local_cfg.blocks = []

        last_block = None

        for instruction in block.instructions:
            last_block = local_cfg.block_start("local", last_block)
            local_cfg.add_instruction(instruction)
            local_cfg.block_end()

        if last_block:
            last_block.successors = block.successors

        local_cfg.calc_liveness_global()

        return local_cfg

    def calc_liveness(self) -> dict[str, dict[ParamGeneralRegister, int]]:
        """Run the full liveness analysis algorithm on the control flow graph, 
        and run the register allocation algorithm by creating a graph of liveness 
        between parameters of the same type, and coloring the graph with a greedy 
        coloring algorithm to obtain fewest registers needed.

        Returns:
            param_type_color_map: Dictionary of type to register mapping. For each type, a dictionary of parameters to register index is returned. (dict[str, dict[ParamGeneralRegister, int]])
        """
        self.calc_liveness_global()
        for block in self.blocks:
            self.sub_graphs.append(self.calc_liveness_local(block))

        # Make liveness graph
        # 1. Create empty graph
        # 2. Iterate over all sub graphs
        # 3. for each block/instruction, add used/sets as nodes
        # 4. if two params are of the same type and ...

        # Dict over param types with corresponding edges
        typed_graphs: dict[str, nx.Graph] = dict()

        g: ControlFlowGraph
        for g in self.sub_graphs:
            for b in g.blocks:
                # Combine all live_in and live_out combination pairs. These correspond to edges in the graph.
                
                # Could possibly be optimized to only use either live_in or live_out, as live_in on one block is live_out on the previous. 
                # Proof needed though, to make sure that would not break with edge cases of root and leaf nodes. 
                x = set(itertools.chain(
                    itertools.combinations(b.live_in, 2),
                    itertools.combinations(b.live_out, 2)
                ))
                
                # Only add edges for parameter pairs of the same type. Maybe an itertools filter could be used here?? IDK about if that is more efficient.
                for a, b in x:
                    a: ParamGeneralRegister
                    b: ParamGeneralRegister
                    if a.type_ == b.type_:
                        typ = a.type_.register_name
                        if not typ in typed_graphs:
                            typed_graphs[typ] = nx.Graph()
                        typed_graphs[typ].add_edge(a, b)

        colored = dict()

        # Color the graph with the greedy DSATUR algorithm
        for typ, graph in typed_graphs.items():
            coloring_alg = nx.algorithms.coloring.strategy_saturation_largest_first
            colored[typ] = nx.coloring.greedy_color(graph, coloring_alg)

        return colored

    def pprint(self):
        """Pretty print the control flow graph
        """
        print('Control Flow Graph')
        for block in self.blocks:
            print(f"Block: {block.name}")
            print(f"\tInstructions:")
            for i in block.instructions:
                print(f"\t\t{i}")
            print(f"\tPredecessors: {[b.name for b in block.predecessors]}")
            print(f"\tSuccessors: {[b.name for b in block.successors]}")
            print(f"\tLive In: {block.live_in}")
            print(f"\tLive Out: {block.live_out}")
            print()
