import os
import json
import logging
import uuid
import networkx as nx
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
import redis
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_en")

# Bundle backup: init-100-context (WikiEval baseline)
BASE_STORAGE_PATH = "/media/raya/Data1/Projects/Programming_Projects/Skripsi/data/backups/lightrag_storage_backup_init_100_context"
LANG = "en"
WORKSPACE_LABEL = "en" # Ini harus sesuai dengan NEO4J_WORKSPACE di file .env LightRAG-en

r_client = redis.Redis.from_url("redis://localhost:16379", decode_responses=True)
q_client = QdrantClient("http://localhost:16333")
n_driver = GraphDatabase.driver("bolt://localhost:17687", auth=("neo4j", "25710R@Y@STneo4j"))

def migrate_redis(workspace: str, namespace: str, data: Dict):
    final_namespace = f"{workspace}_{namespace}"
    if not data:
        logger.info(f"Redis: Skipping empty namespace {final_namespace}")
        return
    logger.info(f"Redis: Migrating {len(data)} items to {final_namespace}:*")
    count = 0
    with r_client.pipeline() as pipe:
        for k, v in data.items():
            pipe.set(f"{final_namespace}:{k}", json.dumps(v, ensure_ascii=False))
            count += 1
            if count % 1000 == 0:
                pipe.execute()
        pipe.execute()

def migrate_qdrant(workspace: str, namespace: str, data_list: list):
    if not data_list:
        return
        
    vector_size = 1536
    collection_name = f"lightrag_vdb_{namespace}_google_gemini_embedding_001_1536d"
    
    logger.info(f"Qdrant: Migrating {len(data_list)} points to {collection_name} (workspace: {workspace})")
            
    if not q_client.collection_exists(collection_name):
        logger.info(f"Creating Qdrant collection {collection_name} with size {vector_size}")
        q_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        
    points = []
    for item in data_list:
        meta = {k: v for k, v in item.items() if k not in ["vector", "__vector__", "__id__"]}
        item_id = item.get("__id__") or item.get("id")
        meta["id"] = item_id
        meta["workspace_id"] = workspace
        meta["workspace"] = workspace
        
        try:
            uuid_obj = uuid.UUID(item_id)
            point_id = str(uuid_obj)
        except ValueError:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item_id))
            
        vec = item.get("vector") or item.get("__vector__")
        
        if isinstance(vec, str):
            import zlib, struct, base64
            decomp = zlib.decompress(base64.b64decode(vec))
            vec = list(struct.unpack(f"{len(decomp)//4}f", decomp))
        
        if vec:
            points.append(PointStruct(id=point_id, vector=vec, payload=meta))
    
    if points:
        batch_size = 100
        for i in range(0, len(points), batch_size):
            q_client.upsert(
                collection_name=collection_name,
                points=points[i:i+batch_size]
            )

def migrate_neo4j_batch(filepath: str):
    logger.info(f"Neo4j: Migrating graph {filepath} for workspace {WORKSPACE_LABEL}")
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return
    
    G = nx.read_graphml(filepath)
    
    nodes_batch = []
    for node_id, data in G.nodes(data=True):
        entity_type = data.get("entity_type", "UNKNOWN")
        if isinstance(entity_type, str):
            entity_type = entity_type.replace("`", "").strip()
            if "," in entity_type: 
                entity_type = entity_type.split(",")[0].strip()
        if not entity_type: 
            entity_type = "UNKNOWN"
        data["entity_type"] = entity_type
        
        props = dict(data)
        props["entity_id"] = str(node_id)
        nodes_batch.append({"entity_id": str(node_id), "type": str(entity_type), "props": props})
        
    edges_batch = []
    for source, target, data in G.edges(data=True):
        props = dict(data)
        for key, default in [("weight", 1.0), ("source_id", str(source)), ("target_id", str(target)), ("description", ""), ("keywords", "")]:
            if key not in props: props[key] = default
        edges_batch.append({"source": str(source), "target": str(target), "props": props})
    
    logger.info(f"Neo4j: Unwinding {len(nodes_batch)} nodes and {len(edges_batch)} edges...")
    
    with n_driver.session() as session:
        # Hapus data 'en' lama agar bersih
        session.run(f"MATCH (n:`{WORKSPACE_LABEL}`) DETACH DELETE n")
        logger.info("Old 'en' data wiped.")

        if nodes_batch:
            node_batch_size = 5000
            for i in range(0, len(nodes_batch), node_batch_size):
                sub_batch = nodes_batch[i:i+node_batch_size]
                logger.info(f"Neo4j: Inserting nodes batch {i} to {i+len(sub_batch)}")
                session.run(f"""
                UNWIND $batch AS row
                MERGE (n:`{WORKSPACE_LABEL}` {{entity_id: row.entity_id}})
                SET n += row.props
                WITH n, row
                CALL apoc.create.addLabels(n, [row.type]) YIELD node
                RETURN count(node)
                """, batch=sub_batch)
                
        if edges_batch:
            edge_batch_size = 5000
            for i in range(0, len(edges_batch), edge_batch_size):
                sub_batch = edges_batch[i:i+edge_batch_size]
                logger.info(f"Neo4j: Inserting edges batch {i} to {i+len(sub_batch)}")
                session.run(f"""
                UNWIND $batch AS row
                MATCH (source:`{WORKSPACE_LABEL}` {{entity_id: row.source}})
                MATCH (target:`{WORKSPACE_LABEL}` {{entity_id: row.target}})
                MERGE (source)-[r:DIRECTED]->(target)
                SET r += row.props
                """, batch=sub_batch)

def main():
    storage_path = os.path.join(BASE_STORAGE_PATH, f"lightrag-{LANG}")
    
    # Redis
    for filename in os.listdir(storage_path):
        if filename.startswith("kv_store_") and filename.endswith(".json"):
            namespace = filename.replace("kv_store_", "").replace(".json", "")
            with open(os.path.join(storage_path, filename), "r") as f:
                data = json.load(f)
                migrate_redis(LANG, namespace, data)
                
    # Qdrant
    vdb_files = ["vdb_chunks.json", "vdb_entities.json", "vdb_relationships.json"]
    for filename in vdb_files:
        filepath = os.path.join(storage_path, filename)
        if os.path.exists(filepath):
            namespace = filename.replace("vdb_", "").replace(".json", "")
            with open(filepath, "r") as f:
                d = json.load(f)
                if "data" in d:
                    migrate_qdrant(LANG, namespace, d["data"])
                    
    # Neo4j
    graph_file = os.path.join(storage_path, "graph_chunk_entity_relation.graphml")
    migrate_neo4j_batch(graph_file)
    logger.info("Migration complete for EN!")

if __name__ == "__main__":
    main()