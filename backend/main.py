import argparse
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_CONFIG_PATH = Path(__file__).parent / "configs" / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def ingest(sample_size: int | None = None) -> None:
    """Run the full ingest pipeline: load → clean → chunk → index."""
    from backend.src.ingest.loader import load_documents
    from backend.src.ingest.cleaner import clean_documents
    from backend.src.ingest.chunker import chunk_documents
    from backend.src.index.graph_index import build_graph_index

    config = _load_config()

    print("Loading documents...")
    docs = load_documents(config, sample_size=sample_size)
    print(f"  {len(docs)} documents loaded")

    print("Cleaning documents...")
    docs = clean_documents(docs)

    print("Chunking documents...")
    chunks = chunk_documents(docs)
    print(f"  {len(chunks)} chunks created")

    print("Building graph index...")
    build_graph_index(chunks)
    print("  Graph index ready")


def query(question: str) -> str:
    """Run a single query through the multi-agent pipeline."""
    from backend.src.agents.orchestrator import run
    return run(question)


def interactive() -> None:
    """Start an interactive query loop."""
    print("Agent-RAG ready. Type 'quit' to exit.\n")
    while True:
        try:
            question = input("Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question or question.lower() in ("quit", "exit"):
            break
        print(f"\n{query(question)}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent-RAG pipeline")
    sub = parser.add_subparsers(dest="command")

    p_ingest = sub.add_parser("ingest", help="Run the ingest pipeline")
    p_ingest.add_argument(
        "--sample", type=int, default=None, metavar="N",
        help="Limit to N documents (useful for testing)"
    )

    p_query = sub.add_parser("query", help="Ask a single question")
    p_query.add_argument("question", type=str)

    sub.add_parser("interactive", help="Start an interactive query loop")

    args = parser.parse_args()

    if args.command == "ingest":
        ingest(sample_size=args.sample)
    elif args.command == "query":
        print(query(args.question))
    elif args.command == "interactive":
        interactive()
    else:
        parser.print_help()
