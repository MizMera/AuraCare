import os
from functools import lru_cache

from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings


QA_PROMPT = PromptTemplate.from_template(
    """You are AuraCare assistant. Answer using only the provided context.
If context is missing, say you do not have enough data.
Be concise and practical for caregivers/family.

Context:
{context}

Question:
{question}

Answer:"""
)


@lru_cache(maxsize=1)
def _get_embeddings():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _get_llm():
    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    ).strip().strip('"').strip("'")
    if not api_key:
        raise ValueError(
            "Gemini API key is missing. Set GEMINI_API_KEY (or GOOGLE_API_KEY) in backend/.env."
        )
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.2,
    )


def answer_from_documents(question, documents):
    if not documents:
        return "I do not have enough data to answer that yet."

    vectorstore = FAISS.from_texts(documents, embedding=_get_embeddings())
    retriever = vectorstore.as_retriever(search_kwargs={"k": min(6, len(documents))})
    retrieved_docs = retriever.invoke(question)
    def build_chain(model_name):
        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        ).strip().strip('"').strip("'")
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2,
        )
        return RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=False,
            chain_type_kwargs={"prompt": QA_PROMPT},
        )

    preferred_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    fallback_models = [preferred_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
    # de-duplicate while preserving order
    fallback_models = list(dict.fromkeys([m for m in fallback_models if m]))

    try:
        last_exc = None
        for model_name in fallback_models:
            try:
                qa_chain = build_chain(model_name)
                result = qa_chain.invoke({"query": question})
                if isinstance(result, dict):
                    return (result.get("result") or "").strip()
                return str(result).strip()
            except Exception as exc:
                last_exc = exc
                if "NOT_FOUND" in str(exc) or "not found" in str(exc).lower():
                    continue
                raise
        raise RuntimeError(f"No compatible Gemini model found. Last error: {last_exc}")
    except Exception as exc:
        error_text = str(exc)
        if "RESOURCE_EXHAUSTED" in error_text or "quota" in error_text.lower():
            snippets = []
            for doc in retrieved_docs[:4]:
                text = (doc.page_content or "").strip()
                if text:
                    snippets.append(f"- {text[:260]}")
            if not snippets:
                return "Gemini quota is exhausted and no matching records were found."
            return (
                "Gemini quota is currently exhausted. Here is the closest matching data from your database:\n"
                + "\n".join(snippets)
            )
        raise
