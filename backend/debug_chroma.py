"""Test with larger k to find the resume past the Medical_book noise."""
from services.bedrock_service import vector_store

def test_query(query, k=50):
    print(f"\n{'='*60}")
    print(f"Query: '{query}' (k={k})")
    print(f"{'='*60}")
    results = vector_store.similarity_search_with_score(query, k=k)
    
    # Deduplicate
    seen = set()
    unique_results = []
    for doc, dist in results:
        key = doc.page_content[:200]
        if key not in seen:
            seen.add(key)
            unique_results.append((doc, dist))
    
    print(f"Raw results: {len(results)}, After dedup: {len(unique_results)}")
    for doc, dist in unique_results[:15]:
        similarity = 1.0 / (1.0 + dist)
        source = doc.metadata.get('source_filename', 'N/A')
        status = "PASS" if similarity >= 0.35 else "FILTERED"
        print(f"  [{status}] Sim={similarity:.4f} (dist={dist:.4f}) | {source} | {doc.page_content[:80]}...")

test_query("tell me something about vishal", k=50)
test_query("vishal education skills resume", k=50)
