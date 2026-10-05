from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Part:
    """One builder's share of the graph."""
    defs: dict = field(default_factory=dict)                       # node id -> (first line, last line)
    edges: dict = field(default_factory=lambda: defaultdict(set))  # node id -> {node ids it can call}
    bases: dict = field(default_factory=dict)                      # class node id -> {base class names}
    unparsed: list = field(default_factory=list)                   # files it couldn't parse: invisible to reach
