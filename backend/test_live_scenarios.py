import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"
FILENAME = "CS_ Syllabus_2023.pdf"

test_queries = [
    {
        "id": 1,
        "query": "What is included in Module I of Principles of Management?",
        "expected_mode": "rag",
        "description": "Focused answer based on relevant Module I content"
    },
    {
        "id": 2,
        "query": "Show me the complete Module II.",
        "expected_mode": "full_section",
        "context_hint": "Principles of Management",
        "description": "Entire Module II text from original extracted document, un-truncated"
    },
    {
        "id": 3,
        "query": "Give me the full Principles of Management syllabus.",
        "expected_mode": "full_course",
        "description": "All relevant modules and complete syllabus content in original order"
    },
    {
        "id": 4,
        "query": "What are the functions of inventory management?",
        "expected_mode": "rag",
        "description": "Focused RAG-generated answer"
    },
    {
        "id": 5,
        "query": "Show me the full section on inventory management.",
        "expected_mode": "full_section",
        "description": "Complete relevant source section"
    }
]

print("=" * 80)
print(f"DocScan Live Verification Test Suite on: '{FILENAME}'")
print("=" * 80)

results = []

for t in test_queries:
    print(f"\n--- Running Test Scenario {t['id']}: \"{t['query']}\" ---")
    payload = {
        "message": t["query"],
        "filename": FILENAME,
        "model_tier": "auto",
        "context_hint": t.get("context_hint", "Principles of Management")
    }
    t0 = time.time()
    try:
        res = requests.post(f"{BASE_URL}/chat", json=payload, timeout=90)
        dur = round(time.time() - t0, 2)
        if res.status_code == 200:
            data = res.json()
            mode = data.get("retrieval_mode")
            sec = data.get("matched_section") or {}
            response_text = data.get("response", "")
            
            print(f"⏱ Response Time: {dur}s | Status: 200 OK")
            print(f"🏷 Retrieval Mode: {mode} (Expected: {t['expected_mode']})")
            print(f"🤖 Model Used: {data.get('model_used')}")
            print(f"📑 Matched Section: {sec.get('section_title')} | {sec.get('page_range')}")
            print(f"📚 Parent Course: {sec.get('parent_title')}")
            print(f"📄 Response (first 250 chars):\n{response_text[:250]}...")
            if sec.get("full_text"):
                print(f"📋 Full Source Section Available: {len(sec['full_text'])} chars")
                print(f"   Source Sample: {sec['full_text'][:120]}...")
            
            success = (mode == t["expected_mode"])
            results.append({
                "id": t["id"],
                "query": t["query"],
                "success": success,
                "retrieval_mode": mode,
                "section": sec.get("section_title"),
                "pages": sec.get("page_range"),
                "parent": sec.get("parent_title"),
                "response_sample": response_text[:200],
                "source_length": len(sec.get("full_text", ""))
            })
        else:
            print(f"❌ HTTP Error {res.status_code}: {res.text}")
            results.append({"id": t["id"], "success": False, "error": res.text})
    except Exception as e:
        print(f"❌ Request Exception: {e}")
        results.append({"id": t["id"], "success": False, "error": str(e)})

print("\n" + "=" * 80)
print("TEST SUMMARY REPORT:")
print("=" * 80)
for r in results:
    status_icon = "✅ PASS" if r.get("success") else "❌ FAIL"
    print(f"Test {r['id']} [{status_icon}]: Mode={r.get('retrieval_mode')} | Section={r.get('section')} | Pages={r.get('pages')}")
