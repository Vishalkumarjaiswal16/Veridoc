"""
Migration Script: Migrate ChromaDB from L2 to Cosine Distance
=============================================================
This script:
1. Exports all existing docs/embeddings/metadata from the old L2 collection
2. Creates a new collection with cosine distance
3. Re-imports everything with deduplication
4. Runs verification queries to confirm the migration worked
"""

import os
import sys
import chromadb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_vectorestore")

OLD_COLLECTION = "example_collection"
NEW_COLLECTION = "veridoc_cosine"
BATCH_SIZE = 5000  # ChromaDB max batch size is ~5461

def main():
    print("=" * 60)
    print("ChromaDB Migration: L2 -> Cosine Distance")
    print("=" * 60)
    
    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    # List existing collections
    collections = client.list_collections()
    collection_names = [c.name for c in collections]
    print(f"\nExisting collections: {collection_names}")
    
    if OLD_COLLECTION not in collection_names:
        print(f"\nERROR: Collection '{OLD_COLLECTION}' not found!")
        sys.exit(1)
    
    old_col = client.get_collection(OLD_COLLECTION)
    total_docs = old_col.count()
    print(f"\nOld collection '{OLD_COLLECTION}':")
    print(f"  Total documents: {total_docs}")
    print(f"  Metadata: {old_col.metadata}")
    
    if total_docs == 0:
        print("\nERROR: Old collection has no documents!")
        sys.exit(1)
    
    # ---- Step 1: Export all data in batches ----
    print(f"\n--- Step 1: Exporting {total_docs} documents ---")
    
    all_ids = []
    all_documents = []
    all_embeddings = []
    all_metadatas = []
    
    offset = 0
    while offset < total_docs:
        batch = old_col.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["documents", "embeddings", "metadatas"]
        )
        batch_size = len(batch["ids"])
        if batch_size == 0:
            break
            
        all_ids.extend(batch["ids"])
        all_documents.extend(batch["documents"])
        all_embeddings.extend(batch["embeddings"])
        all_metadatas.extend(batch["metadatas"])
        
        offset += batch_size
        print(f"  Exported {offset}/{total_docs} documents...")
    
    print(f"  Total exported: {len(all_ids)} documents")
    
    # ---- Step 2: Deduplicate ----
    print(f"\n--- Step 2: Deduplicating ---")
    
    seen_content = {}
    dedup_ids = []
    dedup_documents = []
    dedup_embeddings = []
    dedup_metadatas = []
    duplicates_removed = 0
    
    for i in range(len(all_ids)):
        # Use first 300 chars of content as dedup key
        content_key = (all_documents[i] or "")[:300]
        source = (all_metadatas[i] or {}).get("source_filename", "unknown")
        dedup_key = f"{source}::{content_key}"
        
        if dedup_key not in seen_content:
            seen_content[dedup_key] = True
            dedup_ids.append(all_ids[i])
            dedup_documents.append(all_documents[i])
            dedup_embeddings.append(all_embeddings[i])
            dedup_metadatas.append(all_metadatas[i])
        else:
            duplicates_removed += 1
    
    print(f"  Original: {len(all_ids)} documents")
    print(f"  Duplicates removed: {duplicates_removed}")
    print(f"  After dedup: {len(dedup_ids)} documents")
    
    # Show per-source breakdown
    source_counts = {}
    for meta in dedup_metadatas:
        source = (meta or {}).get("source_filename", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print(f"\n  Chunks per source (after dedup):")
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:5d} | {source}")
    
    # ---- Step 3: Delete old collection, create new with cosine ----
    print(f"\n--- Step 3: Creating new collection with cosine distance ---")
    
    # Check if new collection already exists
    if NEW_COLLECTION in collection_names:
        print(f"  Deleting existing '{NEW_COLLECTION}'...")
        client.delete_collection(NEW_COLLECTION)
    
    print(f"  Deleting old '{OLD_COLLECTION}'...")
    client.delete_collection(OLD_COLLECTION)
    
    print(f"  Creating '{NEW_COLLECTION}' with cosine distance...")
    new_col = client.create_collection(
        name=NEW_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"  New collection metadata: {new_col.metadata}")
    
    # ---- Step 4: Import into new collection in batches ----
    print(f"\n--- Step 4: Importing {len(dedup_ids)} documents ---")
    
    for i in range(0, len(dedup_ids), BATCH_SIZE):
        batch_end = min(i + BATCH_SIZE, len(dedup_ids))
        new_col.add(
            ids=dedup_ids[i:batch_end],
            documents=dedup_documents[i:batch_end],
            embeddings=dedup_embeddings[i:batch_end],
            metadatas=dedup_metadatas[i:batch_end],
        )
        print(f"  Imported {batch_end}/{len(dedup_ids)} documents...")
    
    # Verify count
    final_count = new_col.count()
    print(f"\n  Final count: {final_count} documents")
    
    # ---- Step 5: Verification queries ----
    print(f"\n--- Step 5: Verification ---")
    
    # We need embeddings to query, so import the embedding class
    from services.bedrock_service import embeddings as titan_embeddings
    
    test_queries = [
        ("tell me about vishal", "Resume.pdf"),
        ("what is air india", "Air India Fact Sheet.pdf"),
        ("capital of mars", None),
    ]
    
    for query, expected_source in test_queries:
        query_embedding = titan_embeddings.embed_query(query)
        results = new_col.query(
            query_embeddings=[query_embedding],
            n_results=5,
            include=["documents", "distances", "metadatas"]
        )
        
        print(f"\n  Query: '{query}'")
        if expected_source:
            print(f"  Expected top source: {expected_source}")
        
        for j in range(min(3, len(results["ids"][0]))):
            dist = results["distances"][0][j]
            similarity = 1.0 - dist / 2.0
            source = results["metadatas"][0][j].get("source_filename", "N/A")
            content = results["documents"][0][j][:80]
            status = "MATCH" if expected_source and expected_source in source else "---"
            print(f"    [{status}] Sim={similarity:.4f} (dist={dist:.4f}) | {source} | {content}...")
    
    print(f"\n{'=' * 60}")
    print("Migration complete!")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
