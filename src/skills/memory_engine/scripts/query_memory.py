import os
import sys
import json
import re
import math
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from util.load_config import load_memory_config, resolve_paths, parse_summary_yaml, map_and_filter_entities
from db import db_helper

config = load_memory_config()
ACTIVE_MEMORY_DIR, ARCHIVED_MEMORY_DIR = resolve_paths(config)
SUMMARIES_DIR = os.path.join(ACTIVE_MEMORY_DIR, "summaries")
RETRIEVAL_LOG_PATH = os.path.join(ACTIVE_MEMORY_DIR, "retrieval.log")
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")

def calculate_match_score(content, query):
    content_lower = content.lower()
    query_words = [w.strip().lower() for w in query.split() if len(w.strip()) > 2]
    if not query_words:
        return 0, 0
        
    unique_matches = 0
    total_freq = 0
    for w in query_words:
        count = content_lower.count(w)
        if count > 0:
            unique_matches += 1
            total_freq += count
            
    return unique_matches, total_freq


def calculate_summary_rank(hybrid_score, unique_matches, total_freq):
    """Keep hybrid ranking primary and use keyword matches as a secondary boost."""
    keyword_boost = (unique_matches * 0.02) + (min(total_freq, 20) * 0.005)
    return hybrid_score + keyword_boost

def calculate_hybrid_score(semantic_score, date_str, weights, decay_constant):
    metadata = parse_summary_yaml(date_str, SUMMARIES_DIR, ARCHIVED_MEMORY_DIR)
    importance = metadata.get("importance", 5)

    try:
        days_diff = (datetime.today().date() - datetime.strptime(date_str, "%Y-%m-%d").date()).days
    except ValueError:
        days_diff = 365

    recency_decay = math.exp(-decay_constant * days_diff)
    
    try:
        importance_val = float(importance)
    except (ValueError, TypeError):
        importance_val = 5.0
    importance_norm = importance_val / 10.0

    final_score = (
        weights["semantic"] * semantic_score
        + weights["importance"] * importance_norm
        + weights["recency"] * recency_decay
    )
    return final_score, metadata

def log_retrieval(query, scored_dates):
    entry = {
        "ts": datetime.now().isoformat() + "Z",
        "query": query,
        "returned_dates": [d for d, _, _ in scored_dates],
        "scores": [s for _, s, _ in scored_dates],
    }
    with open(RETRIEVAL_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

def vector_search(query):
    try:
        return db_helper.vector_search(query, limit=10)
    except Exception as e:
        print(f"⚠️ Vector search failed: {e}")
    return []

def read_summary_from_nas(date_str):
    path = os.path.join(SUMMARIES_DIR, f"{date_str}.summary.md")
    if not os.path.exists(path):
        path = os.path.join(ARCHIVED_MEMORY_DIR, "daily_sessions/summaries", f"{date_str}.summary.md")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
        
        # Strip frontmatter/codeblock
        pattern_yaml = r"^(?:```yaml|---)\n(.*?)\n(?:```|---)\n(.*)"
        match_yaml = re.match(pattern_yaml, content, re.DOTALL)
        if match_yaml:
            body_text = match_yaml.group(2).strip()
        else:
            body_text = content
            
        # Strip Links line at the bottom
        pattern_links = r"\n\n(?:🔗\s*Links:\s*|(?:\*\*|__)🔗\s*Links:(?:\*\*|__)\s*)(.*)"
        body_text = re.sub(pattern_links, "", body_text, flags=re.IGNORECASE).strip()
        
        return body_text
    except Exception as e:
        print(f"⚠️ Error reading summary for {date_str}: {e}")
    return None

def search_keyword_in_nas_summaries(query):
    query_lower = query.lower()
    matches = []
    nas_summaries_dir = os.path.join(ARCHIVED_MEMORY_DIR, "daily_sessions/summaries")
    
    # Check local summaries first
    local_files = []
    if os.path.exists(SUMMARIES_DIR):
        local_files = [os.path.join(SUMMARIES_DIR, f) for f in os.listdir(SUMMARIES_DIR) if f.endswith(".summary.md")]
        
    nas_files = []
    if os.path.exists(nas_summaries_dir):
        nas_files = [os.path.join(nas_summaries_dir, f) for f in os.listdir(nas_summaries_dir) if f.endswith(".summary.md")]
        
    all_paths = list(set(local_files + nas_files))
    
    for path in all_paths:
        filename = os.path.basename(path)
        date_str = filename.replace(".summary.md", "")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file_obj:
                content = file_obj.read()
                if query_lower in content.lower():
                    # Extract clean summary
                    pattern_yaml = r"^(?:```yaml|---)\n(.*?)\n(?:```|---)\n(.*)"
                    match_yaml = re.match(pattern_yaml, content, re.DOTALL)
                    body_text = match_yaml.group(2).strip() if match_yaml else content
                    pattern_links = r"\n\n(?:🔗\s*Links:\s*|(?:\*\*|__)🔗\s*Links:(?:\*\*|__)\s*)(.*)"
                    body_text = re.sub(pattern_links, "", body_text, flags=re.IGNORECASE).strip()
                    
                    matches.append({
                        "date": date_str,
                        "summary": body_text
                    })
        except Exception:
            pass
    return matches

def map_and_filter_entities_local(entities_list, category, config):
    return map_and_filter_entities(entities_list, category, config)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Unified Memory Query (RAG Semantic Search + NAS Fallback)")
    parser.add_argument("query", help="The query/question to search for")

    args = parser.parse_args()
    query = args.query
    
    print(f"🔍 Searching memories for: '{query}'...")

    # Step 1: Run Vector Search (Semantic Search)
    results = vector_search(query)
    
    date_scores = {}
    rag_chunks = []
    
    for r in results:
        text = r.get("text", "")
        score = r.get("score", 0.5)
        # Check if chunk is from MEMORY_INDEX.md
        if "MEMORY_INDEX.md" in text or "Historical Memory Map" in text or "### 📅" in text:
            # Extract dates
            for date_match in DATE_PATTERN.findall(text):
                date_scores[date_match] = max(date_scores.get(date_match, 0.0), score)
        else:
            # Normal chunk (e.g. from MEMORY.md or recent 7 days log)
            rag_chunks.append(r)
            
    # Step 2: Hybrid Scoring & 1-Hop Related Dates Expansion
    weights = config.get("retrieval_weights", {"semantic": 0.5, "importance": 0.3, "recency": 0.2})
    decay_constant = config.get("decay_constant", 0.005)
    
    # Perform a 1-hop expansion using related_dates from YAML metadata
    expanded_date_scores = {}
    for d, score in date_scores.items():
        expanded_date_scores[d] = max(expanded_date_scores.get(d, 0.0), score)
        
        # Read related_dates from YAML summary
        metadata = parse_summary_yaml(d, SUMMARIES_DIR, ARCHIVED_MEMORY_DIR)
        related = metadata.get("related_dates", [])
        if isinstance(related, list):
            for r_date in related:
                if r_date:
                    # Apply a 30% decay relative to the parent semantic score
                    decayed_score = score * 0.7
                    expanded_date_scores[r_date] = max(expanded_date_scores.get(r_date, 0.0), decayed_score)
                    
    visited_dates = {} # date -> (final_score, metadata)
    for d, score in expanded_date_scores.items():
        final_score, metadata = calculate_hybrid_score(score, d, weights, decay_constant)
        visited_dates[d] = (final_score, metadata)

    scored_dates = [(d, score_meta[0], score_meta[1]) for d, score_meta in visited_dates.items()]
    scored_dates.sort(key=lambda x: x[1], reverse=True)
    log_retrieval(query, scored_dates)
    
    found_dates_ordered = [d for d, _, _ in scored_dates]
            
    # Step 3: Fetch clean summaries from local/NAS if index dates were found
    summaries_content = []
    if found_dates_ordered:
        print(f"📍 RAG Index pointed to historical dates (ranked): {found_dates_ordered}")
        for d in found_dates_ordered:
            summary_text = read_summary_from_nas(d)
            if summary_text:
                summaries_content.append({
                    "date": d,
                    "summary": summary_text,
                    "hybrid_score": visited_dates.get(d, (0.0, {}))[0],
                })
            
    # Step 4: Always run keyword search in summaries and merge/deduplicate
    print("🔍 Running direct keyword search in summaries...")
    keyword_matches = search_keyword_in_nas_summaries(query)
    for m in keyword_matches:
        existing = next((x for x in summaries_content if x["date"] == m["date"]), None)
        if existing:
            continue
        summaries_content.append({
            "date": m["date"],
            "summary": m["summary"],
            "hybrid_score": 0.0,
        })

    # Step 5: Rank summaries with hybrid score as the primary signal and keyword matches as a boost
    if summaries_content:
        ranked_contents = []
        for c in summaries_content:
            uniq, freq = calculate_match_score(c["summary"], query)
            final_rank = calculate_summary_rank(c.get("hybrid_score", 0.0), uniq, freq)
            ranked_contents.append((c, uniq, freq, final_rank))
        ranked_contents.sort(key=lambda x: (x[3], x[1], x[2], x[0]["date"]), reverse=True)
        summaries_content = [x[0] for x in ranked_contents]

    # Step 6: Output Consolidated Results for the Agent
    print("\n" + "="*50)
    print("CONSOLIDATED MEMORY SEARCH RESULTS")
    print("="*50)
    
    if rag_chunks:
        print("\n--- [RAG Semantic Matches (MEMORY.md / Recent Logs)] ---")
        for idx, r in enumerate(rag_chunks[:3], 1):
            print(f"Chunk #{idx} (Score: {r.get('score')})")
            print(r.get("text").strip())
            print("-" * 30)
            
    if summaries_content:
        print("\n--- [NAS Archive Matches (Summaries)] ---")
        for idx, c in enumerate(summaries_content[:5], 1): # Limit to top 5 summaries
            # Load metadata from summary yaml
            metadata = parse_summary_yaml(c['date'], SUMMARIES_DIR, ARCHIVED_MEMORY_DIR)
            mapped_people = map_and_filter_entities_local(metadata.get("people", []), "people", config)
            mapped_projects = map_and_filter_entities_local(metadata.get("projects", []), "projects", config)
            links_list = [f"[[{p}]]" for p in mapped_people] + [f"[[{prj}]]" for prj in mapped_projects]
            links_str = " · ".join(links_list) if links_list else "None"
            
            print(f"#### {idx}. {c['date']}")
            print(c['summary'].strip())
            print(f"Path: {os.path.join(ARCHIVED_MEMORY_DIR, 'daily_sessions', c['date'])}/")
            print(f"Links: {links_str}")
            print()
            
    if not rag_chunks and not summaries_content:
        print("❌ No matching memories found in RAG or NAS archives.")
        
    print("\n" + "="*50)

if __name__ == "__main__":
    main()
