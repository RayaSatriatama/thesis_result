import os
import json
import uuid
import logging
from typing import Dict
import networkx as nx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
import redis
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

# Workspaces
WORKSPACES = ["id", "en"]
BASE_STORAGE_PATH = "/media/raya/Data1/Projects/Programming_Projects/Skripsi/LightRAG"

# DB Connections
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

def migrate_neo4j_batch(workspace: str, filepath: str):
    logger.info(f"Neo4j: Migrating graph {filepath} for workspace {workspace}")
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return
    
    G = nx.read_graphml(filepath)
    workspace_label = workspace
    
    nodes_batch = []
    for node_id, data in G.nodes(data=True):
        entity_type = data.get("entity_type", "UNKNOWN")
        if "`" in entity_type or "," in entity_type or not entity_type.strip():
            entity_type = entity_type.replace("`", "").strip()
            if "," in entity_type:
                entity_type = entity_type.split(",")[0].strip()
            if not entity_type:
                entity_type = "UNKNOWN"
        data["entity_type"] = entity_type
        # Add required meta
        props = dict(data)
        props["entity_id"] = str(node_id)
        nodes_batch.append({"entity_id": str(node_id), "type": entity_type, "props": props})
        
    edges_batch = []
    for source, target, data in G.edges(data=True):
        props = dict(data)
        for key, default in [("weight", 1.0), ("source_id", str(source)), ("target_id", str(target)), ("description", ""), ("keywords", "")]:
            if key not in props:
                props[key] = default
        edges_batch.append({"source": str(source), "target": str(target), "props": props})
    
    logger.info(f"Neo4j: Unwinding {len(nodes_batch)} nodes and {len(edges_batch)} edges for {workspace}...")
    
    with n_driver.session() as session:
        # Fast insert nodes
        if nodes_batch:
            node_batch_size = 5000
            for i in range(0, len(nodes_batch), node_batch_size):
                sub_batch = nodes_batch[i:i+node_batch_size]
                logger.info(f"Neo4j: Inserting nodes batch {i} to {i+len(sub_batch)}")
                session.run(f"""
                UNWIND $batch AS row
                MERGE (n:`{workspace_label}` {{entity_id: row.entity_id}})
                SET n += row.props
                WITH n, row
                CALL apoc.create.addLabels(n, [row.type]) YIELD node
                RETURN count(node)
                """, batch=sub_batch)
            
        # Fast insert edges
        if edges_batch:
            edge_batch_size = 5000
            for i in range(0, len(edges_batch), edge_batch_size):
                sub_batch = edges_batch[i:i+edge_batch_size]
                logger.info(f"Neo4j: Inserting edges batch {i} to {i+len(sub_batch)}")
                session.run(f"""
                UNWIND $batch AS row
                MATCH (source:`{workspace_label}` {{entity_id: row.source}})
                MATCH (target:`{workspace_label}` {{entity_id: row.target}})
                MERGE (source)-[r:DIRECTED]->(target)
                SET r += row.props
                """, batch=sub_batch)

def main():
    for lang in WORKSPACES:
        storage_path = os.path.join(BASE_STORAGE_PATH, f"LightRAG-{lang}", "data", "rag_storage")
        if not os.path.exists(storage_path):
            logger.warning(f"Skipping {lang} - {storage_path} not found")
            continue
            
        logger.info(f"\n--- Migrating workspace '{lang}' ---")
        
        # 1. Redis
        for filename in os.listdir(storage_path):
            if filename.startswith("kv_store_") and filename.endswith(".json"):
                namespace = filename.replace("kv_store_", "").replace(".json", "")
                with open(os.path.join(storage_path, filename), "r") as f:
                    data = json.load(f)
                    migrate_redis(lang, namespace, data)
        
        # 2. Qdrant
        vdb_files = ["vdb_chunks.json", "vdb_entities.json", "vdb_relationships.json"]
        for filename in vdb_files:
            filepath = os.path.join(storage_path, filename)
            if os.path.exists(filepath):
                namespace = filename.replace("vdb_", "").replace(".json", "")
                with open(filepath, "r") as f:
                    d = json.load(f)
                    if "data" in d:
                        migrate_qdrant(lang, namespace, d["data"])
                        
        # 3. Neo4j
        graph_file = os.path.join(storage_path, "graph_chunk_entity_relation.graphml")
        migrate_neo4j_batch(lang, graph_file)

    logger.info("\nMigration complete!")

if __name__ == "__main__":
    main()
