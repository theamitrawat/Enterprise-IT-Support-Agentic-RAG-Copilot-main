import logging
import json
import string
from typing import Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from app.core.config import get_settings
from app.rag.state import AgentState, EvidenceGrade
from app.rag.vectorstore import get_retriever

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = None


def llm():
    global _llm
    if _llm is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is missing")
        _llm = ChatGroq(
            model=settings.groq_model,
            temperature=0,
            groq_api_key=settings.groq_api_key,
            timeout=20,
            max_retries=0,
        )
    return _llm


def add_trace(state: AgentState, message: str):
    return [*state.get("trace", []), message]


def is_simple_chat(question: str) -> bool:
    text = question.strip().lower().strip(string.punctuation + " ")
    simple_messages = {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
    }
    return text in simple_messages or text.startswith(("hello ", "hi ", "hey "))


def route_question(state: AgentState):
    route = "direct" if is_simple_chat(state["question"]) else "kb"
    return {"source_used": route, "trace": add_trace(state, f"Router -> {route.upper()}")}


def route_after_router(state: AgentState) -> Literal["retrieve_kb", "direct_answer"]:
    return "retrieve_kb" if state["source_used"] == "kb" else "direct_answer"


def retrieve_kb(state: AgentState):
    logger.info("Retrieving from ChromaDB...")
    docs = get_retriever().invoke(state["current_query"])
    logger.info(f"ChromaDB returned {len(docs)} chunks")
    return {"kb_docs": docs, "trace": add_trace(state, f"Private KB retrieval -> {len(docs)} chunks")}


def grade_kb(state: AgentState):
    if not state["kb_docs"]:
        return {
            "kb_grade": "weak",
            "trace": add_trace(state, "KB evidence grade -> WEAK (no matching documents)"),
        }
    logger.info("Grading KB evidence...")
    grader = llm().with_structured_output(EvidenceGrade, method="json_mode")
    context = "\n\n".join(
        f"Source: {d.metadata.get('source','unknown')}\n{d.page_content}" for d in state["kb_docs"])
    grade = grader.invoke(f"""
You grade evidence for an enterprise IT support assistant.
Question: {state['question']}
Private company KB evidence:\n{context}
Return good only if the evidence is sufficient to answer confidently and specifically.
Otherwise return weak. JSON: {{"grade":"good"}} or {{"grade":"weak"}}.
""")
    return {"kb_grade": grade.grade, "trace": add_trace(state, f"KB evidence grade -> {grade.grade.upper()}")}


def after_kb(state: AgentState) -> Literal["generate_from_kb", "search_web", "insufficient"]:
    if state["kb_grade"] == "good":
        return "generate_from_kb"
    return "search_web" if settings.tavily_api_key else "insufficient"


def search_web(state: AgentState):
    logger.info("Searching web with Tavily...")
    payload = json.dumps({
        "query": state["current_query"],
        "max_results": 5,
        "topic": "general",
        "include_answer": True,
        "include_raw_content": False,
    }).encode("utf-8")
    request = Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.tavily_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.web_search_timeout_seconds) as response:
            result = json.loads(response.read())
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Tavily search failed; continuing without web evidence: %s", exc)
        return {
            "web_results": "",
            "citations": [],
            "source_used": "web",
            "trace": add_trace(state, "Web fallback failed -> continuing without search evidence"),
        }

    lines, citations = [], []
    if isinstance(result, dict):
        if result.get("answer"):
            lines.append("Search answer: " + result["answer"])
        for item in result.get("results", []):
            title, url, content = item.get("title", ""), item.get(
                "url", ""), item.get("content", "")
            lines.append(f"Title: {title}\nURL: {url}\nContent: {content}")
            citations.append(
                {"title": title or url, "url": url, "type": "web"})
    else:
        lines.append(str(result))
    return {
        "web_results": "\n\n".join(lines),
        "citations": citations,
        "source_used": "web",
        "trace": add_trace(state, "Web fallback -> Tavily search"),
    }


def grade_web(state: AgentState):
    if not state["web_results"].strip():
        return {
            "web_grade": "weak",
            "trace": add_trace(state, "Web evidence grade -> WEAK (no search results)"),
        }
    grader = llm().with_structured_output(EvidenceGrade, method="json_mode")
    grade = grader.invoke(f"""
Question: {state['question']}
Web evidence:\n{state['web_results']}
Return good if the evidence is sufficient and directly relevant; otherwise weak.
Return valid JSON like {{"grade":"good"}}.
""")
    return {"web_grade": grade.grade, "trace": add_trace(state, f"Web evidence grade -> {grade.grade.upper()}")}


def after_web(state: AgentState) -> Literal["generate_from_web", "rewrite_query", "insufficient"]:
    if state["web_grade"] == "good":
        return "generate_from_web"
    if not state["web_results"].strip():
        return "insufficient"
    if state["retry_count"] < settings.max_retries:
        return "rewrite_query"
    return "insufficient"


def rewrite_query(state: AgentState):
    rewritten = llm().invoke(f"""
Rewrite this IT support question for better private knowledge retrieval and vendor web search.
Preserve intent, add useful technical keywords, do not answer, return only the query.
Question: {state['question']}
""").content.strip()
    return {
        "current_query": rewritten,
        "retry_count": state["retry_count"] + 1,
        "trace": add_trace(state, f"Query rewrite -> {rewritten}"),
    }


def generate_from_kb(state: AgentState):
    logger.info("Generating answer from KB...")
    context = "\n\n".join(
        f"[Source: {d.metadata.get('source','unknown')}]\n{d.page_content}" for d in state["kb_docs"])
    answer = llm().invoke(f"""
You are an enterprise IT support copilot. Answer ONLY from the private company KB below.
Be concise, actionable, and safe. If steps are present, present them clearly.
Do not invent policy details. Mention that the answer is based on the company's private knowledge base.
Question: {state['question']}\n\nPrivate KB:\n{context}
""").content
    citations = []
    seen = set()
    for d in state["kb_docs"]:
        src = d.metadata.get("source", "Private KB")
        if src not in seen:
            seen.add(src)
            citations.append({"title": src.replace("\\", "/").rsplit("/", 1)[-1], "url": "", "type": "private_kb"})
    return {"answer": answer, "source_used": "private_kb", "citations": citations, "trace": add_trace(state, "Answer generation -> PRIVATE KB")}


def generate_from_web(state: AgentState):
    answer = llm().invoke(f"""
You are an enterprise IT support copilot. The private company KB was insufficient.
Answer ONLY from the web evidence below. Clearly say this is external web information and may need IT validation before changing company-managed systems.
Question: {state['question']}\n\nWeb evidence:\n{state['web_results']}
""").content
    return {"answer": answer, "source_used": "web_search", "trace": add_trace(state, "Answer generation -> WEB SEARCH")}


def direct_answer(state: AgentState):
    if is_simple_chat(state["question"]):
        return {
            "answer": "Hello! Ask me an IT support question and I will try to help.",
            "source_used": "direct",
            "trace": add_trace(state, "Direct response -> no retrieval"),
        }

    answer = llm().invoke(
        f"Respond briefly and naturally to: {state['question']}").content
    return {"answer": answer, "source_used": "direct", "trace": add_trace(state, "Direct response -> no retrieval")}


def insufficient(state: AgentState):
    if settings.tavily_api_key:
        answer = (
            "I couldn't find enough reliable evidence in the company knowledge base "
            "or external search to answer confidently. Please contact the IT help desk "
            "or provide more details."
        )
    else:
        answer = (
            "I couldn't find enough reliable evidence in the company knowledge base, "
            "and external web search is not configured. Please contact the IT help desk "
            "or provide more details."
        )
    return {
        "answer": answer,
        "source_used": "insufficient_evidence",
        "trace": add_trace(state, "Stopped -> insufficient reliable evidence"),
    }


def build_graph():
    graph = StateGraph(AgentState)
    for name, fn in {
        "route_question": route_question,
        "retrieve_kb": retrieve_kb,
        "grade_kb": grade_kb,
        "search_web": search_web,
        "grade_web": grade_web,
        "rewrite_query": rewrite_query,
        "generate_from_kb": generate_from_kb,
        "generate_from_web": generate_from_web,
        "direct_answer": direct_answer,
        "insufficient": insufficient,
    }.items():
        graph.add_node(name, fn)

    graph.add_edge(START, "route_question")
    graph.add_conditional_edges("route_question", route_after_router, {
        "retrieve_kb": "retrieve_kb", "direct_answer": "direct_answer"
    })
    graph.add_edge("retrieve_kb", "grade_kb")
    graph.add_conditional_edges("grade_kb", after_kb, {
        "generate_from_kb": "generate_from_kb",
        "search_web": "search_web",
        "insufficient": "insufficient",
    })
    graph.add_edge("search_web", "grade_web")
    graph.add_conditional_edges("grade_web", after_web, {
        "generate_from_web": "generate_from_web", "rewrite_query": "rewrite_query", "insufficient": "insufficient"
    })
    graph.add_edge("rewrite_query", "retrieve_kb")
    graph.add_edge("generate_from_kb", END)
    graph.add_edge("generate_from_web", END)
    graph.add_edge("direct_answer", END)
    graph.add_edge("insufficient", END)
    return graph.compile()


agent_graph = build_graph()


def ask(question: str):
    initial: AgentState = {
        "question": question,
        "current_query": question,
        "kb_docs": [],
        "web_results": "",
        "kb_grade": "",
        "web_grade": "",
        "answer": "",
        "source_used": "",
        "retry_count": 0,
        "trace": [],
        "citations": [],
    }
    return agent_graph.invoke(initial)
