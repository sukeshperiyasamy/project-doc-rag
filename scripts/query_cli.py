"""
Command-Line Query Interface for Research Knowledge Base.
Supports mix, hybrid, local, global, and naive retrieval modes.
Prints answer with explicit source provenance and citations.
"""

import sys
import json
import argparse
import urllib.request
import urllib.error

SERVER_URL = "http://127.0.0.1:9621"

def query_server(query: str, mode: str = "mix", show_context: bool = False):
    req_url = f"{SERVER_URL}/query"
    payload = {
        "query": query,
        "mode": mode,
        "stream": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ResearchKB-CLI"
    }

    req = urllib.request.Request(req_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
            print("\n" + "=" * 80)
            print(f"QUERY: {query}")
            print(f"RETRIEVAL MODE: {mode.upper()}")
            print("=" * 80 + "\n")
            
            response_text = data.get("response", "")
            print("ANSWER:")
            print(response_text)
            print("\n" + "-" * 80)

            if "references" in data and data["references"]:
                print("SOURCE REFERENCES:")
                for ref in data["references"]:
                    print(f"  * {ref}")
                print("-" * 80)

            if show_context and "context" in data:
                print("RETRIEVED CONTEXT:")
                print(data["context"])
                print("-" * 80)

    except urllib.error.URLError as e:
        print(f"[ERROR] Failed to connect to LightRAG server at {SERVER_URL}: {e}")
        print("Please ensure the server is running using: scripts/start_server.ps1")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Query the Research Knowledge Graph.")
    parser.add_argument("query", nargs="*", help="The research question to ask")
    parser.add_argument("--mode", choices=["mix", "hybrid", "local", "global", "naive"], default="mix", help="Retrieval mode (default: mix)")
    parser.add_argument("--show-context", action="store_true", help="Display raw retrieved context chunks")
    args = parser.parse_args()

    q = " ".join(args.query).strip() if args.query else ""
    if not q:
        # Interactive prompt
        while True:
            try:
                user_input = input("\nEnter research query (or 'exit' to quit): ").strip()
                if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                    break
                query_server(user_input, mode=args.mode, show_context=args.show_context)
            except (KeyboardInterrupt, EOFError):
                break
    else:
        query_server(q, mode=args.mode, show_context=args.show_context)

if __name__ == "__main__":
    main()
