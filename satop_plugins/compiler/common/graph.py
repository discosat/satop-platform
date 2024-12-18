
class Graph:
    _nodes: dict[str, dict]
    _edges: set[tuple[str, str]]
    
    def __init__(self) -> None:
        pass
    
    def add_node(self, node: str, parent: str, data:dict):
        self._nodes[node] = data
        self._edges.add((parent, node))
    
    def get_children(self, node: str) -> list[str]:
        return set([child for parent,child in self._edges if parent == node])
    
    def get_parents(self, node: str) -> list[str]:
        return set([parent for parent,child in self._edges if child == node])
    

    