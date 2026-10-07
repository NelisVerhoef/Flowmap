"""Call-graph builders: one per language, all spelling nodes the same way.

A builder module exposes:
    EXT = (".py",)                                  # file suffixes it parses
    build(files, read) -> Part                      # definitions, call edges, classes
    symbols(text) -> [(start, end, "Qual.name")]    # places diff lines on definitions
    signature(text, "Qual.name") -> str | None      # a def's parameters, for contract changes
and optionally, so lens can ignore edits that change nothing:
    live(text) -> {line numbers} | None             # module-level lines that run
    same(base_text, head_text, "Qual.name") -> bool # the def changed only in docs or formatting
and, so the atlas can say what a function is for:
    doc(text, "Qual.name") -> str | None            # the first paragraph of its docstring

Node ids are "repo/relative/file:Qual.name", the spelling adapters use for handlers, so every
entry point's handler is a node the graph can walk from (`flowmap callgraph check` says which
are not). `read(rel) -> text | None` lets a builder parse any git revision.
"""

from . import python
from .part import Part  # noqa: F401

BUILDERS = [python]


def builder_for(rel):
    return next((b for b in BUILDERS if rel.endswith(b.EXT)), None)


def suffixes():
    return tuple(s for b in BUILDERS for s in b.EXT)
