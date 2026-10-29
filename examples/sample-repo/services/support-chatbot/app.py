"""Customer support chatbot for the Northwind Parcels help centre (synthetic)."""

import os
from pathlib import Path

import chromadb
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "test-key-not-real"))
store = chromadb.PersistentClient(path=".chroma").get_or_create_collection("help-articles")
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text()


def answer(question: str, customer: dict) -> str:
    """Answer a customer question using help articles as context."""
    docs = store.query(query_texts=[question], n_results=3)["documents"][0]
    greeting = f"Customer: {customer['full_name']} <{customer['email']}>"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": greeting + "\n\n" + "\n".join(docs) + "\n\n" + question},
        ],
    )
    return response.choices[0].message.content
