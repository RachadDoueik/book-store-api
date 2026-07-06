from app.schemas.chat import (
    BookContext,
    ChatMessage,
    MessageRole,
    RetrievalRoute,
    RouterResult,
)

MAX_HISTORY_TURNS = 6  # keep last 6 user+assistant pairs
MAX_DESCRIPTION_CHARS = 400  # truncate long descriptions to stay within token budget

SYSTEM_PROMPT_WITH_CONTEXT = """
You are a helpful assistant for The Wisdom Vault, an independent bookshop.

## Behavioral contract

**For catalog questions** (prices, stock, what titles we carry, which authors we stock):
- Answer ONLY from the catalog context below. Never invent titles, prices, or authors.
- If a book is not in the context, say "We don't seem to carry that title."
- If the context is empty, tell the user you couldn't find a match and suggest
  they refine their search (different author name, category, or keyword).
- If the user asks about entire catalogue , respond with a message telling them to be specific , and seacrh the catalogue for what they need
- You are not able to reserve copies due to concurency
- If you are asked about available number of copies , tell the user the number but also tell to double check



**For general literary questions** (plot summaries, themes, author biography, historical context):
- Answer freely from your own knowledge.
- ONLY ANSWER QUESTIONS ABOUT BOOKS , NOTHING ELSE IS ALLOWED
- Distinguish clearly between "what we carry" and "general information."

**Tone**: warm, knowledgeable, concise — like a well-read independent bookshop owner.

---

## Catalog results

{context_block}

---

Answer the user's question using the rules above.
""".strip()

SYSTEM_PROMPT_NO_CONTEXT = """
You are a helpful assistant for The Wisdom Vault, an independent bookshop.

The user is asking a general literary question not tied to our specific catalog.
Answer freely from your own knowledge. Be warm, concise, and knowledgeable.

If the user asks what books we carry, our prices, or our stock,
let them know you can search the catalog — they just need to tell you
what author, genre, or theme they're looking for.

ONLY ANSWER BOOK RELATED QUESTIONS AND NOTHING ELSE !!!
""".strip()


def _format_book(book: BookContext) -> str:
    lines = [f"Title: {book.title}"]

    if book.authors:
        # Join multiple authors with commas — reflects the many-to-many relationship
        lines.append(f"Authors: {', '.join(book.authors)}")

    if book.category:
        lines.append(f"Category: {book.category}")

    if book.stock:
        lines.append(f"Copies Available = Stock Count: {book.stock}")

    if book.page_count:
        lines.append(f"Pages: {book.page_count}")

    if book.price is not None:
        lines.append(f"Price: ${book.price:.2f}")

    lines.append(f"In stock: {'Yes' if book.in_stock else 'No'}")

    if book.isbn:
        lines.append(f"ISBN: {book.isbn}")

    if book.release_date:
        lines.append(f"Release date: {book.release_date}")

    if book.description:
        desc = book.description[:MAX_DESCRIPTION_CHARS]
        if len(book.description) > MAX_DESCRIPTION_CHARS:
            desc += "..."
        lines.append(f"Description: {desc}")

    return "\n".join(lines)


def _build_context_block(books: list[BookContext]) -> str:
    if not books:
        return "(No catalog results found for this query.)"
    sections = [f"[Book {i + 1}]\n{_format_book(b)}" for i, b in enumerate(books)]
    return "\n\n".join(sections)


class PromptBuilder:
    def build(
        self,
        user_message: str,
        router_result: RouterResult,
        retrieved_books: list[BookContext],
        conversation_history: list[ChatMessage],
    ) -> tuple[str, list[ChatMessage]]:
        """
        Returns (system_prompt, messages) ready to pass to the LLM provider.
        """
        if router_result.route == RetrievalRoute.NO_RETRIEVAL:
            system_prompt = SYSTEM_PROMPT_NO_CONTEXT
        else:
            context_block = _build_context_block(retrieved_books)
            system_prompt = SYSTEM_PROMPT_WITH_CONTEXT.format(
                context_block=context_block
            )

        # Trim history to stay within token budget (each turn = user + assistant)
        recent_history = conversation_history[-(MAX_HISTORY_TURNS * 2) :]

        messages = recent_history + [
            ChatMessage(role=MessageRole.USER, content=user_message)
        ]

        return system_prompt, messages
