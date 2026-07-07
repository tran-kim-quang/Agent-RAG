from langchain.tools import tool

from backend.src.monitoring import agent_run_monitor
from backend.src.retrieval.graph_search import graph_search


@tool
def graph_search_tool(query: str) -> str:
    """
    Search the document graph index.
    Finds the most relevant document chunks by semantic similarity,
    then expands context via document relationships (NEXT_CHUNK).
    Input should be a search query string.
    """
    agent_run_monitor.append_event(
        "graph_search_tool_start",
        "Retrieval tool is querying the indexed document graph.",
        {"query_length": len(query)},
        status="processing",
    )
    results = graph_search(query)

    if not results:
        agent_run_monitor.append_event(
            "graph_search_tool_complete",
            "Retrieval tool found no relevant chunks.",
            {"result_count": 0},
            status="processing",
        )
        return "No relevant documents found."

    parts = []
    for i, r in enumerate(results, 1):
        score_str = f"(score: {r['score']:.4f})" if r["score"] is not None else "(related)"
        source = r["metadata"].get("source", "unknown")
        chunk_index = r["metadata"].get("chunk_index", "?")
        parts.append(
            f"[{i}] {score_str} source={source}, chunk={chunk_index}\n{r['content']}"
        )

    agent_run_monitor.append_event(
        "graph_search_tool_complete",
        "Retrieval tool found relevant chunks from the document graph.",
        {"result_count": len(results)},
        status="processing",
    )
    return "\n\n---\n\n".join(parts)
