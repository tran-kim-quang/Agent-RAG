from langchain.tools import tool
from backend.src.retrieval.graph_search import graph_search


@tool
def graph_search_tool(query: str) -> str:
    """
    Search the document graph index.
    Finds the most relevant document chunks by semantic similarity,
    then expands context via document relationships (NEXT_CHUNK).
    Input should be a search query string.
    """
    results = graph_search(query)

    if not results:
        return "No relevant documents found."

    parts = []
    for i, r in enumerate(results, 1):
        score_str = f"(score: {r['score']:.4f})" if r["score"] is not None else "(related)"
        source = r["metadata"].get("source", "unknown")
        chunk_index = r["metadata"].get("chunk_index", "?")
        parts.append(
            f"[{i}] {score_str} source={source}, chunk={chunk_index}\n{r['content']}"
        )

    return "\n\n---\n\n".join(parts)
