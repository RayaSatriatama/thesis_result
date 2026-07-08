# LightRAG Documentation

**LightRAG** adalah sistem Retrieval-Augmented Generation (RAG) yang sederhana dan cepat berbasis Python yang menggabungkan konstruksi knowledge graph dengan vector search untuk memungkinkan querying dokumen yang intelligent. Sistem ini secara otomatis mengekstrak entities dan relationships dari dokumen menggunakan large language models, menyimpannya dalam arsitektur hybrid knowledge graph dan vector database, serta menyediakan multiple query modes (naive, local, global, hybrid, mix) untuk mengambil informasi yang relevan secara kontekstual.

## Daftar Isi
1. [Spesifikasi LightRAG Proyek Ini](#spesifikasi-lightrag-proyek-ini)
2. [Inisialisasi LightRAG](#inisialisasi-lightrag)
3. [Insert Documents](#insert-documents)
4. [Query dengan Different Modes](#query-modes)
5. [Custom Storage Backends](#storage-backends)
6. [Insert Custom Knowledge Graph](#custom-kg)
7. [Manage Entities dan Relations](#manage-entities)
8. [Delete Data](#delete-data)
9. [Reranking untuk Better Retrieval](#reranking)
10. [Export Knowledge Graph](#export-kg)
11. [REST API Server](#rest-api)

---

## Spesifikasi LightRAG Proyek Ini (Current Tech Stack)

Berikut adalah spesifikasi teknis dan parameter lengkap terkait implementasi sistem LightRAG yang berjalan pada sistem (berdasarkan konfigurasi environment saat ini). Karena proyek ini mendukung dua bahasa, informasi selengkapnya mengenai statik injeksi dan parameternya dipecah menjadi dua dokumen:

*   **[Spesifikasi Lengkap Sistem EN (English)](lightrag/lightrag_specification_en.md):** 1530 Nodes, 1487 Edges. 
*   **[Spesifikasi Lengkap Sistem ID (Indonesian)](lightrag/lightrag_specification_id.md):** 6454 Nodes, 6307 Edges.
*   **[Indeks folder LightRAG](lightrag/README.md):** spesifikasi EN/ID + dokumentasi pengembangan WikiEval dalam satu indeks.

Secara arsitektural umum, baik node EN maupun ID menggunakan konfigurasi sebagai berikut:

**1. Teknologi Database (Database Tech Stack)**
*   **Graph Storage (Knowledge Graph):** Neo4J (`bolt://neo4j:7687`, Workspace: `id` / `en`) -> *(Kustom)*
*   **Vector Storage:** Qdrant (`http://qdrant:6333`, Workspace: `id` / `en`) -> *(Kustom)*
*   **Key-Value (KV) Storage:** Redis (`redis://redis:6379`, Workspace: `id` / `en`) -> *(Kustom)*
*   **Document Status Storage:** Redis (`redis://redis:6379`) -> *(Kustom)*

**2. Spesifikasi Model Machine Learning (via OpenRouter)**
*   **LLM Model:** `google/gemini-2.5-flash-lite` (Binding: `openai`) -> *(Kustom)*
*   **Embedding Model:** `google/gemini-embedding-001` -> *(Kustom)*
*   **Concurrency:** 16 Async Tasks, Batch Size: 12

**3. Parameter Konfigurasi Ingestion & Retrieval (Client Node)**
*   **URL Server LightRAG:** `http://100.68.196.58:9621` atau localhost
*   **Ingestion:** `CHUNK_SIZE` = 1200, `CHUNK_OVERLAP` = 100 -> *(Default LightRAG)*
*   **Selective Ingestion:** Aktif (`LIGHTRAG_SELECTIVE_INGESTION=true`, minimal 800 karakter) -> *(Kustom)*
*   **Query:** Mode = `hybrid`, `TOP_K` = 5 -> *(Default LightRAG)*

---

## Inisialisasi LightRAG

Buat dan inisialisasi instance LightRAG dengan custom LLM dan embedding functions. Kedua `initialize_storages()` dan `initialize_pipeline_status()` harus dipanggil sebelum penggunaan.

```python
import os
import asyncio
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

WORKING_DIR = "./rag_storage"
os.makedirs(WORKING_DIR, exist_ok=True)

async def initialize_rag():
    # Buat LightRAG instance dengan OpenAI models
    rag = LightRAG(
        working_dir=WORKING_DIR,
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete,
        # Optional: Configure storage backends (defaults to in-memory)
        kv_storage="JsonKVStorage",
        vector_storage="NanoVectorDBStorage",
        graph_storage="NetworkXStorage",
        doc_status_storage="JsonDocStatusStorage"
    )

    # REQUIRED: Initialize storage backends
    await rag.initialize_storages()

    # REQUIRED: Initialize processing pipeline
    await initialize_pipeline_status()

    return rag

async def main():
    try:
        # Set OpenAI API key
        os.environ["OPENAI_API_KEY"] = "sk-your-api-key"

        rag = await initialize_rag()

        # Verify initialization by testing embedding
        test_embedding = await rag.embedding_func(["test"])
        print(f"Embedding dimension: {test_embedding.shape[1]}")

        # Ready to use
        await rag.ainsert("Sample document content")
        result = await rag.aquery(
            "What is this about?",
            param=QueryParam(mode="naive")
        )
        print(f"Query result: {result}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if rag:
            await rag.finalize_storages()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Insert Documents

Insert dokumen tunggal atau multiple dengan optional IDs dan file paths untuk citation tracking.

```python
import asyncio
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

async def insert_documents():
    rag = LightRAG(
        working_dir="./docs_storage",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete,
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()

    try:
        # Single document insert
        await rag.ainsert("Alice works at CompanyX on AI research.")

        # Batch insert dengan custom IDs
        documents = [
            "Bob is a data scientist at UniversityY.",
            "CompanyX develops advanced machine learning products.",
            "Alice and Bob collaborate on quantum computing."
        ]
        ids = ["doc-001", "doc-002", "doc-003"]
        await rag.ainsert(documents, ids=ids)

        # Insert dengan file paths untuk citation support
        doc_with_citation = [
            "The research paper discusses transformer architectures.",
            "Neural networks have evolved significantly."
        ]
        file_paths = [
            "/papers/transformers.pdf",
            "/papers/neural_nets.pdf"
        ]
        await rag.ainsert(doc_with_citation, file_paths=file_paths)

        # Batch insert dengan concurrency control
        rag_parallel = LightRAG(
            working_dir="./parallel_storage",
            embedding_func=openai_embed,
            llm_model_func=gpt_4o_mini_complete,
            max_parallel_insert=4  # Process 4 documents concurrently
        )
        await rag_parallel.initialize_storages()
        await initialize_pipeline_status()

        large_batch = [f"Document {i} content" for i in range(20)]
        await rag_parallel.ainsert(large_batch)

        print("✓ All documents inserted successfully")

    except Exception as e:
        print(f"Insert failed: {e}")
    finally:
        await rag.finalize_storages()

asyncio.run(insert_documents())
```

---

## Query Modes

Query knowledge graph menggunakan berbagai retrieval strategies dengan streaming support.

### Penjelasan Query Modes:

- **Naive Mode**: Simple vector search pada chunks
- **Local Mode**: Entity-focused retrieval
- **Global Mode**: High-level community summaries
- **Hybrid Mode**: Menggabungkan local dan global
- **Mix Mode**: Knowledge graph + vector retrieval

```python
import asyncio
import inspect
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

async def query_examples():
    rag = LightRAG(
        working_dir="./query_storage",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete,
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()

    # Insert sample data
    await rag.ainsert("Alice is a researcher at MIT focusing on quantum computing.")

    query = "Who is Alice and what does she do?"

    try:
        # Naive mode: Simple vector search on chunks
        result_naive = await rag.aquery(
            query,
            param=QueryParam(mode="naive", top_k=20)
        )
        print(f"Naive: {result_naive[:100]}...")

        # Local mode: Entity-focused retrieval
        result_local = await rag.aquery(
            query,
            param=QueryParam(
                mode="local",
                top_k=60,
                max_entity_tokens=6000
            )
        )
        print(f"Local: {result_local[:100]}...")

        # Global mode: High-level community summaries
        result_global = await rag.aquery(
            query,
            param=QueryParam(
                mode="global",
                top_k=60,
                max_relation_tokens=8000
            )
        )
        print(f"Global: {result_global[:100]}...")

        # Hybrid mode: Combines local and global
        result_hybrid = await rag.aquery(
            query,
            param=QueryParam(mode="hybrid")
        )
        print(f"Hybrid: {result_hybrid[:100]}...")

        # Mix mode: Knowledge graph + vector retrieval
        result_mix = await rag.aquery(
            query,
            param=QueryParam(mode="mix")
        )
        print(f"Mix: {result_mix[:100]}...")

        # Streaming response
        stream = await rag.aquery(
            query,
            param=QueryParam(mode="hybrid", stream=True)
        )

        if inspect.isasyncgen(stream):
            print("Streaming: ", end="")
            async for chunk in stream:
                print(chunk, end="", flush=True)
            print()

        # Get only context without LLM generation
        context = await rag.aquery(
            query,
            param=QueryParam(mode="hybrid", only_need_context=True)
        )
        print(f"Context only: {context[:200]}...")

        # Add conversation history
        result_with_history = await rag.aquery(
            "What else can you tell me?",
            param=QueryParam(
                mode="hybrid",
                conversation_history=[
                    {"role": "user", "content": "Who is Alice?"},
                    {"role": "assistant", "content": "Alice is a researcher."}
                ]
            )
        )
        print(f"With history: {result_with_history[:100]}...")

    except Exception as e:
        print(f"Query failed: {e}")
    finally:
        await rag.finalize_storages()

asyncio.run(query_examples())
```

---

## Storage Backends

Gunakan PostgreSQL, Neo4j, atau database eksternal lainnya untuk production deployments.

```python
import asyncio
import os
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

async def setup_postgresql_storage():
    # Configure PostgreSQL environment variables
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5432"
    os.environ["POSTGRES_USER"] = "lightrag"
    os.environ["POSTGRES_PASSWORD"] = "your-password"
    os.environ["POSTGRES_DB"] = "lightrag_db"

    rag_postgres = LightRAG(
        working_dir="./pg_storage",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete,
        # PostgreSQL for all storage types
        kv_storage="PGKVStorage",
        vector_storage="PGVectorStorage",
        graph_storage="PGGraphStorage",
        doc_status_storage="PGDocStatusStorage",
        workspace="production"  # Logical data isolation
    )

    await rag_postgres.initialize_storages()
    await initialize_pipeline_status()

    await rag_postgres.ainsert("Sample document for PostgreSQL storage")
    result = await rag_postgres.aquery("What is stored?")
    print(f"PostgreSQL result: {result}")

    await rag_postgres.finalize_storages()

async def setup_neo4j_storage():
    # Configure Neo4j environment variables
    os.environ["NEO4J_URI"] = "neo4j://localhost:7687"
    os.environ["NEO4J_USERNAME"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "your-neo4j-password"

    rag_neo4j = LightRAG(
        working_dir="./neo4j_storage",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete,
        graph_storage="Neo4JStorage",  # Use Neo4j for graph
        vector_storage="MilvusVectorDBStorage",  # Use Milvus for vectors
        workspace="dev"
    )

    await rag_neo4j.initialize_storages()
    await initialize_pipeline_status()

    await rag_neo4j.ainsert("Neo4j knowledge graph example")
    result = await rag_neo4j.aquery("What is this?")
    print(f"Neo4j result: {result}")

    await rag_neo4j.finalize_storages()

async def setup_mixed_storage():
    # Mix and match storage backends
    rag_mixed = LightRAG(
        working_dir="./mixed_storage",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete,
        kv_storage="RedisKVStorage",
        vector_storage="QdrantVectorDBStorage",
        graph_storage="Neo4JStorage",
        doc_status_storage="MongoDocStatusStorage"
    )

    await rag_mixed.initialize_storages()
    await initialize_pipeline_status()

    print("Mixed storage backend configured")

    await rag_mixed.finalize_storages()

async def main():
    try:
        await setup_postgresql_storage()
        await setup_neo4j_storage()
        await setup_mixed_storage()
    except Exception as e:
        print(f"Storage setup error: {e}")

asyncio.run(main())
```

---

## Insert Custom Knowledge Graph

Directly insert pre-built entities, relationships, dan chunks tanpa LLM extraction.

```python
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete

# Initialize RAG
rag = LightRAG(
    working_dir="./custom_kg",
    llm_model_func=gpt_4o_mini_complete
)

# Define custom knowledge graph structure
custom_kg = {
    "entities": [
        {
            "entity_name": "Alice",
            "entity_type": "person",
            "description": "Alice is a researcher specializing in quantum physics.",
            "source_id": "doc-1",
            "file_path": "research_team.txt"
        },
        {
            "entity_name": "Bob",
            "entity_type": "person",
            "description": "Bob is a mathematician working on cryptography.",
            "source_id": "doc-1",
            "file_path": "research_team.txt"
        },
        {
            "entity_name": "Quantum Computing",
            "entity_type": "technology",
            "description": "Field of study using quantum mechanics for computation.",
            "source_id": "doc-1",
            "file_path": "research_team.txt"
        }
    ],
    "relationships": [
        {
            "src_id": "Alice",
            "tgt_id": "Bob",
            "description": "Alice and Bob are research partners.",
            "keywords": "collaboration research partnership",
            "weight": 1.0,
            "source_id": "doc-1",
            "file_path": "research_team.txt"
        },
        {
            "src_id": "Alice",
            "tgt_id": "Quantum Computing",
            "description": "Alice conducts research on quantum computing.",
            "keywords": "research expertise specialization",
            "weight": 1.0,
            "source_id": "doc-1",
            "file_path": "research_team.txt"
        },
        {
            "src_id": "Bob",
            "tgt_id": "Quantum Computing",
            "description": "Bob applies mathematics to quantum computing problems.",
            "keywords": "research application mathematics",
            "weight": 0.8,
            "source_id": "doc-1",
            "file_path": "research_team.txt"
        }
    ],
    "chunks": [
        {
            "content": "Alice and Bob collaborate on quantum computing research at the university.",
            "source_id": "doc-1",
            "source_chunk_index": 0,
            "file_path": "research_team.txt"
        },
        {
            "content": "Their work focuses on quantum algorithms and error correction.",
            "source_id": "doc-1",
            "source_chunk_index": 1,
            "file_path": "research_team.txt"
        }
    ]
}

# Insert custom knowledge graph
try:
    rag.insert_custom_kg(custom_kg)
    print("✓ Custom knowledge graph inserted successfully")

    # Query the custom knowledge graph
    result = rag.query("Who are Alice and Bob?")
    print(f"Query result: {result}")

except Exception as e:
    print(f"Failed to insert custom KG: {e}")
```

---

## Manage Entities dan Relations

Buat, edit, dan merge entities dan relationships dalam knowledge graph.

```python
import asyncio
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

async def manage_entities():
    rag = LightRAG(
        working_dir="./entity_mgmt",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()

    try:
        # Create new entities
        entity_google = await rag.acreate_entity("Google", {
            "description": "Google is a multinational technology company.",
            "entity_type": "company"
        })
        print(f"Created: {entity_google}")

        entity_gmail = await rag.acreate_entity("Gmail", {
            "description": "Gmail is an email service by Google.",
            "entity_type": "product"
        })

        # Create relationship between entities
        relation = await rag.acreate_relation("Google", "Gmail", {
            "description": "Google develops and operates Gmail.",
            "keywords": "develops operates maintains",
            "weight": 2.0
        })
        print(f"Created relation: {relation}")

        # Edit existing entity
        updated = await rag.aedit_entity("Google", {
            "description": "Google is a subsidiary of Alphabet Inc., founded in 1998.",
            "entity_type": "tech_company"
        })
        print(f"Updated: {updated}")

        # Rename entity (all relationships are migrated)
        renamed = await rag.aedit_entity("Gmail", {
            "entity_name": "Google Mail",
            "description": "Google Mail (formerly Gmail) is an email service."
        })
        print(f"Renamed: {renamed}")

        # Edit relationship
        updated_rel = await rag.aedit_relation("Google", "Google Mail", {
            "description": "Google created and maintains Google Mail.",
            "keywords": "creates maintains email cloud",
            "weight": 3.0
        })
        print(f"Updated relation: {updated_rel}")

        # Merge duplicate entities
        await rag.amerge_entities(
            source_entities=["AI", "Artificial Intelligence", "Machine Intelligence"],
            target_entity="Artificial Intelligence",
            merge_strategy={
                "description": "concatenate",
                "entity_type": "keep_first",
                "source_id": "join_unique"
            },
            target_entity_data={
                "entity_type": "technology",
                "description": "AI is the simulation of human intelligence by machines."
            }
        )
        print("✓ Entities merged")

        # Query to verify changes
        result = await rag.aquery("What is Google?")
        print(f"Query result: {result[:200]}...")

    except Exception as e:
        print(f"Entity management error: {e}")
    finally:
        await rag.finalize_storages()

asyncio.run(manage_entities())
```

---

## Delete Data

Hapus entities, relationships, atau seluruh dokumen dari knowledge graph.

```python
import asyncio
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

async def delete_operations():
    rag = LightRAG(
        working_dir="./delete_storage",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()

    try:
        # Insert test data
        docs = [
            "Alice works at CompanyX.",
            "Bob is a colleague of Alice.",
            "CompanyX develops AI software."
        ]
        doc_ids = ["doc-001", "doc-002", "doc-003"]
        await rag.ainsert(docs, ids=doc_ids)

        # Delete specific entity (removes entity and all its relationships)
        await rag.adelete_by_entity("Alice")
        print("✓ Deleted entity 'Alice' and all relationships")

        # Delete specific relationship (preserves entities)
        await rag.adelete_by_relation("Bob", "CompanyX")
        print("✓ Deleted relationship between Bob and CompanyX")

        # Delete entire document by ID
        # This performs smart cleanup:
        # - Removes entities/relations unique to this document
        # - Preserves shared knowledge
        # - Rebuilds affected entity descriptions
        await rag.adelete_by_doc_id("doc-003")
        print("✓ Deleted document doc-003")

        # Verify deletion
        result = await rag.aquery("Who is Alice?")
        print(f"Query after deletion: {result}")

        # Synchronous versions also available
        rag.delete_by_entity("SomeEntity")
        rag.delete_by_relation("EntityA", "EntityB")

    except Exception as e:
        print(f"Deletion error: {e}")
    finally:
        await rag.finalize_storages()

asyncio.run(delete_operations())
```

---

## Reranking untuk Better Retrieval

Gunakan reranking models untuk meningkatkan kualitas retrieval dengan me-reorder chunks berdasarkan relevance.

```python
import asyncio
import os
import numpy as np
from functools import partial
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.rerank import cohere_rerank
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status

async def setup_with_reranking():
    # Configure reranking function
    rerank_func = partial(
        cohere_rerank,
        model="BAAI/bge-reranker-v2-m3",
        api_key=os.getenv("RERANK_API_KEY"),
        base_url="http://localhost:8000/v1/rerank"  # vLLM endpoint
    )

    # Create embedding function
    async def embedding_func(texts: list[str]) -> np.ndarray:
        return await openai_embed(
            texts,
            model="text-embedding-3-large",
            api_key=os.getenv("OPENAI_API_KEY")
        )

    # Test embedding dimension
    test_emb = await embedding_func(["test"])
    embedding_dim = test_emb.shape[1]

    # Initialize with reranking
    rag = LightRAG(
        working_dir="./rerank_storage",
        llm_model_func=lambda prompt, **kwargs: openai_complete_if_cache(
            "gpt-4o-mini", prompt, **kwargs
        ),
        embedding_func=EmbeddingFunc(
            embedding_dim=embedding_dim,
            func=embedding_func
        ),
        rerank_model_func=rerank_func  # Enable reranking
    )

    await rag.initialize_storages()
    await initialize_pipeline_status()

    try:
        # Insert documents
        docs = [
            "Reranking improves retrieval quality by re-ordering results.",
            "Vector databases enable similarity search in embeddings.",
            "LightRAG supports multiple query modes for different needs.",
            "Natural language processing uses transformers for understanding."
        ]
        await rag.ainsert(docs)

        query = "How does reranking improve retrieval?"

        # Query with reranking enabled (default)
        result_with_rerank = await rag.aquery(
            query,
            param=QueryParam(
                mode="naive",
                top_k=10,
                chunk_top_k=5,
                enable_rerank=True  # Explicitly enable
            )
        )
        print(f"With rerank: {result_with_rerank[:150]}...")

        # Query without reranking
        result_no_rerank = await rag.aquery(
            query,
            param=QueryParam(
                mode="naive",
                top_k=10,
                chunk_top_k=5,
                enable_rerank=False  # Disable for this query
            )
        )
        print(f"Without rerank: {result_no_rerank[:150]}...")

        # Test rerank function directly
        test_docs = [
            "Reranking significantly improves quality",
            "The quick brown fox jumps over the lazy dog",
            "Vector search finds similar documents"
        ]
        reranked = await rerank_func(
            query="rerank improve quality",
            documents=test_docs,
            top_n=3
        )
        print("\nDirect rerank results:")
        for item in reranked:
            print(f"  Score {item['relevance_score']:.3f}: {test_docs[item['index']]}")

    except Exception as e:
        print(f"Reranking error: {e}")
    finally:
        await rag.finalize_storages()

asyncio.run(setup_with_reranking())
```

---

## Export Knowledge Graph

Export entities, relationships, dan chunks ke berbagai format file untuk analysis dan backup.

```python
import asyncio
from lightrag import LightRAG
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.kg.shared_storage import initialize_pipeline_status

async def export_knowledge_graph():
    rag = LightRAG(
        working_dir="./export_storage",
        embedding_func=openai_embed,
        llm_model_func=gpt_4o_mini_complete
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()

    try:
        # Insert sample data
        docs = [
            "Apple is a technology company founded by Steve Jobs.",
            "The iPhone is Apple's flagship product.",
            "Steve Jobs was a visionary entrepreneur."
        ]
        await rag.ainsert(docs)

        # Export to CSV (default format)
        await rag.aexport_data("knowledge_graph.csv")
        print("✓ Exported to CSV")

        # Export to Excel
        await rag.aexport_data("knowledge_graph.xlsx", file_format="excel")
        print("✓ Exported to Excel")

        # Export to Markdown
        await rag.aexport_data("knowledge_graph.md", file_format="md")
        print("✓ Exported to Markdown")

        # Export to plain text
        await rag.aexport_data("knowledge_graph.txt", file_format="txt")
        print("✓ Exported to text")

        # Export with vector embeddings included
        await rag.aexport_data(
            "complete_data.csv",
            include_vector_data=True
        )
        print("✓ Exported with vector data")

        # Synchronous version
        rag.export_data("sync_export.csv")

        print("\nExported files contain:")
        print("  - Entity information (names, types, descriptions)")
        print("  - Relationship data (connections, weights, keywords)")
        print("  - Text chunks with source tracking")

    except Exception as e:
        print(f"Export error: {e}")
    finally:
        await rag.finalize_storages()

asyncio.run(export_knowledge_graph())
```

---

## REST API Server

Mulai server LightRAG dengan Web UI dan REST API endpoints untuk document management dan querying.

### Instalasi dan Setup

```bash
# Install dengan API support
pip install "lightrag-hku[api]"

# Buat environment configuration
cat > .env << EOF
# LLM Configuration
LLM_BINDING=openai
LLM_MODEL=gpt-4o-mini
LLM_BINDING_HOST=https://api.openai.com/v1
LLM_BINDING_API_KEY=your-api-key

# Embedding Configuration
EMBEDDING_BINDING=ollama
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_DIM=1024
EMBEDDING_BINDING_HOST=http://localhost:11434

# Server Configuration
PORT=9621
WORKERS=2
WORKING_DIR=./rag_storage

# Storage Configuration (optional)
LIGHTRAG_KV_STORAGE=PGKVStorage
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage
LIGHTRAG_GRAPH_STORAGE=PGGraphStorage

# Authentication (optional)
LIGHTRAG_API_KEY=your-secure-api-key
AUTH_ACCOUNTS=admin:admin123
EOF

# Start server (simple mode)
lightrag-server

# Start server (production mode with Gunicorn)
lightrag-gunicorn --workers 4

# Access Web UI
# http://localhost:9621

# View API documentation
# http://localhost:9621/docs
# http://localhost:9621/redoc
```

### REST API Endpoints

```bash
# Upload document
curl -X POST "http://localhost:9621/documents/upload" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf"

# Insert text
curl -X POST "http://localhost:9621/documents/text" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "text": "LightRAG is a powerful RAG system.",
    "description": "Sample document"
  }'

# Query knowledge graph
curl -X POST "http://localhost:9621/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "query": "What is LightRAG?",
    "mode": "hybrid",
    "top_k": 60,
    "enable_rerank": true
  }'

# Stream query response
curl -X POST "http://localhost:9621/query/stream" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "query": "Explain RAG systems",
    "mode": "local",
    "stream": true
  }'

# List documents
curl -X GET "http://localhost:9621/documents/list" \
  -H "X-API-Key: your-api-key"

# Delete document by ID
curl -X DELETE "http://localhost:9621/documents/doc-12345" \
  -H "X-API-Key: your-api-key"

# Export knowledge graph
curl -X POST "http://localhost:9621/graph/export" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "format": "csv",
    "include_vectors": false
  }'

# Get entity details
curl -X GET "http://localhost:9621/graph/entity/Alice" \
  -H "X-API-Key: your-api-key"

# Track document processing status
curl -X GET "http://localhost:9621/track_status/track-id-12345" \
  -H "X-API-Key: your-api-key"

# Health check (no auth required by default)
curl -X GET "http://localhost:9621/health"
```

### Ollama Emulation Mode

```bash
# LightRAG provides Ollama-compatible API endpoints
# Connect Open WebUI atau Ollama clients lainnya ke LightRAG

# Tambahkan koneksi di Open WebUI admin panel:
# URL: http://localhost:9621
# Model: lightrag:latest

# Query prefixes control modes in chat:
# /local What is this about?
# /global Summarize the dataset
# /hybrid Combined query
# /mix Knowledge graph + vector search
# /bypass Direct LLM (no RAG)
# /context Return only context

# Tambahkan user prompt dengan square brackets:
# /hybrid[Use bullet points] Explain the concept
# /mix[Generate mermaid diagram] Show relationships
```

---

## Use Cases dan Integration Patterns

LightRAG unggul dalam skenario yang memerlukan pemahaman dokumen yang mendalam dengan kesadaran entity relationship. Aplikasi umum meliputi:

1. **Research Document Analysis**: Sistem secara otomatis mengonstruksi knowledge graphs dari scientific papers, memungkinkan queries tentang research methodologies, author collaborations, dan concept relationships across large corpora.

2. **Enterprise Knowledge Management**: Kemampuan LightRAG untuk indexing technical documentation, meeting notes, dan emails ke dalam queryable knowledge graph yang melestarikan organizational context.

3. **Customer Support Systems**: LightRAG digunakan untuk membangun dynamic knowledge bases dari support tickets dan product documentation, dengan hybrid query mode menyediakan baik technical details yang spesifik maupun general product overviews.

4. **Production Deployment**: Multi-storage backend support membuat LightRAG cocok baik untuk prototyping dengan in-memory databases maupun production deployment dengan PostgreSQL atau Neo4j.

### Integration Workflow Umum:

1. Inisialisasi LightRAG dengan chosen storage backends dan LLM/embedding providers
2. Batch insert dokumen dengan proper metadata untuk citation tracking
3. Optional: configure reranking untuk improved retrieval quality
4. Query menggunakan appropriate modes berdasarkan information needs
5. Periodically export knowledge graphs untuk analysis atau backup
6. Untuk production systems, gunakan REST API server dengan Web UI untuk document management

---

## Repository Information

- **Repository**: LightRAG (hkuds)
- **Trust Score**: 8.7
- **Code Snippets**: 257
- **Language**: Python
- **License**: Sesuai dengan repository asli
- **GitHub**: https://github.com/hkuds/lightrag

