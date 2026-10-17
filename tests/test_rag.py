import gc
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

from app.rag import vectorstore, workflow


class FakeStructuredLLM:
    def invoke(self, _prompt):
        return SimpleNamespace(grade="good")


class FakeLLM:
    def with_structured_output(self, *_args, **_kwargs):
        return FakeStructuredLLM()

    def invoke(self, _prompt):
        return SimpleNamespace(content="Restart the VPN client and try another gateway.")


class RagTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.chroma_dir = Path(self.temp_dir.name) / "chroma"
        self.directory_patch = patch.object(vectorstore, "CHROMA_DIR", self.chroma_dir)
        self.collection_patch = patch.object(
            vectorstore, "COLLECTION_NAME", "test_enterprise_it_support"
        )
        self.directory_patch.start()
        self.collection_patch.start()
        vectorstore._vectorstore = None
        vectorstore._embeddings = None

    def tearDown(self):
        store = vectorstore._vectorstore
        if store is not None:
            store._client.close()
        vectorstore._vectorstore = None
        vectorstore._embeddings = None
        gc.collect()
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
        self.directory_patch.stop()
        self.collection_patch.stop()
        self.temp_dir.cleanup()

    def test_chroma_persists_and_reuses_chunk_ids(self):
        chunk = Document(
            page_content="For VPN failures, restart the client and try another gateway.",
            metadata={"source": "handbook.md", "start_index": 0},
        )

        first_id = vectorstore.add_documents([chunk])[0]
        vectorstore.add_documents([chunk])
        self.assertEqual(vectorstore.get_document_count(), 1)

        updated_chunk = Document(
            page_content="For VPN failures, contact the IT Service Desk.",
            metadata={"source": "handbook.md", "start_index": 0},
        )
        vectorstore.add_documents([updated_chunk])
        self.assertEqual(vectorstore.get_document_count(), 1)

        vectorstore._vectorstore._client.close()
        vectorstore._vectorstore = None
        gc.collect()
        self.assertEqual(vectorstore.get_document_count(), 1)
        results = vectorstore.get_retriever().invoke("VPN connection problem")
        self.assertTrue(results)
        self.assertEqual(results[0].metadata["source"], "handbook.md")
        self.assertEqual(len(first_id), 64)
        self.assertIn("contact the IT Service Desk", results[0].page_content)

    def test_query_returns_grounded_answer_without_extra_router_call(self):
        chunk = Document(
            page_content="For VPN failures, restart the client and try another gateway.",
            metadata={"source": "handbook.md", "start_index": 0},
        )
        vectorstore.add_documents([chunk])

        with patch.object(workflow, "llm", return_value=FakeLLM()):
            result = workflow.ask("My VPN connection keeps failing. What should I check?")

        self.assertIn("Restart the VPN client", result["answer"])
        self.assertEqual(result["source_used"], "private_kb")
        self.assertEqual(result["citations"][0]["title"], "handbook.md")
        self.assertEqual(result["trace"][0], "Router -> KB")

    def test_simple_greeting_does_not_require_external_services(self):
        result = workflow.ask("hello")
        self.assertEqual(result["source_used"], "direct")
        self.assertIn("Ask me an IT support question", result["answer"])

    def test_tavily_timeout_returns_without_hanging_the_chat(self):
        state = {"current_query": "VPN troubleshooting", "trace": []}
        with patch(
            "app.rag.workflow.urlopen",
            side_effect=TimeoutError("request timed out"),
        ):
            result = workflow.search_web(state)

        self.assertEqual(result["web_results"], "")
        self.assertIn("Web fallback failed", result["trace"][-1])


if __name__ == "__main__":
    unittest.main()
