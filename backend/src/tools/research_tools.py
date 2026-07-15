from __future__ import annotations

import time

import arxiv as _arxiv
import wikipedia as _wiki_pkg
from langchain.tools import tool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper


_arxiv_client = _arxiv.Client()

_wiki_pkg.set_user_agent("LiAn-Visual-Agent/0.1 (contact: trankimquang1603@gmail.com)")


@tool("arxiv")
def arxiv_tool(query: str) -> str:
    """Search for research papers on arXiv. Input should be a plain-text search query."""
    search = _arxiv.Search(
        query=query,
        max_results=5,
        sort_by=_arxiv.SortCriterion.Relevance,
    )
    for attempt in range(3):
        try:
            results = list(_arxiv_client.results(search))
            if not results:
                return "No papers found for that query."
            parts = []
            for result in results[:2]:
                authors = ", ".join(str(author) for author in result.authors[:3])
                parts.append(
                    f"Title: {result.title}\n"
                    f"Authors: {authors}\n"
                    f"Summary: {result.summary[:600]}\n"
                    f"URL: {result.entry_id}"
                )
            return "\n\n---\n\n".join(parts)
        except Exception as exc:
            message = str(exc)
            if "429" in message or "too many requests" in message.lower():
                if attempt < 2:
                    time.sleep(12 * (attempt + 1))
                    continue
                return "arXiv rate-limited after retries. Please try again later."
            return f"arXiv error: {message}"
    return "arXiv search failed."


wikipedia_tool = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=2000),
    description="Search Wikipedia for factual information. Input should be a search query.",
)
