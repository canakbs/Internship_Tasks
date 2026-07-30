"""
GraphRAG Flask Web Uygulamasi
Wikipedia + Neo4j + Gemini ile GraphRAG Sistemi Web Arayuzu
SSE Streaming + Sohbet Bellegi destekli
"""
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
from neo4j import GraphDatabase

import config
from pipeline.step7_query import ask_graph_rag_stream

# Flask uygulamasi
app = Flask(__name__)

# Loglama ayarlari
logger = config.setup_logging("INFO")

# Sohbet verisi dizini
CONVERSATIONS_DIR = config.DATA_DIR / "conversations"
CONVERSATIONS_DIR.mkdir(exist_ok=True)


# ================================================
# Yardimci fonksiyonlar
# ================================================
def get_conversation_path(conv_id: str) -> Path:
    return CONVERSATIONS_DIR / f"{conv_id}.json"


def load_conversation(conv_id: str) -> dict | None:
    path = get_conversation_path(conv_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_conversation(conv_data: dict):
    path = get_conversation_path(conv_data["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conv_data, f, ensure_ascii=False, indent=2)


def list_all_conversations() -> list:
    convs = []
    for f in sorted(CONVERSATIONS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                convs.append({
                    "id": data["id"],
                    "title": data.get("title", "Yeni Sohbet"),
                    "created_at": data.get("created_at", ""),
                    "message_count": len(data.get("messages", []))
                })
        except Exception:
            pass
    return convs


# ================================================
# Sayfalar
# ================================================
@app.route("/")
def index():
    return render_template("index.html")


# ================================================
# Sohbet CRUD API'leri
# ================================================
@app.route("/api/conversations", methods=["GET"])
def api_list_conversations():
    return jsonify(list_all_conversations())


@app.route("/api/conversations", methods=["POST"])
def api_create_conversation():
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    conv_data = {
        "id": conv_id,
        "title": "Yeni Sohbet",
        "created_at": datetime.now().isoformat(),
        "messages": []
    }
    save_conversation(conv_data)
    return jsonify(conv_data)


@app.route("/api/conversations/<conv_id>", methods=["GET"])
def api_get_conversation(conv_id):
    conv = load_conversation(conv_id)
    if not conv:
        return jsonify({"error": "Sohbet bulunamadi."}), 404
    return jsonify(conv)


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def api_delete_conversation(conv_id):
    path = get_conversation_path(conv_id)
    if path.exists():
        path.unlink()
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Sohbet bulunamadi."}), 404


@app.route("/api/conversations/<conv_id>/title", methods=["PUT"])
def api_update_title(conv_id):
    conv = load_conversation(conv_id)
    if not conv:
        return jsonify({"error": "Sohbet bulunamadi."}), 404
    data = request.get_json()
    conv["title"] = data.get("title", conv["title"])
    save_conversation(conv)
    return jsonify({"status": "updated"})


# ================================================
# GraphRAG SSE Streaming Sorgu
# ================================================
@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json()
    query_text = data.get("query", "").strip()
    conv_id = data.get("conversation_id", None)

    if not query_text:
        return jsonify({"error": "Soru bos olamaz."}), 400

    # Konusma gecmisini yukle
    conversation_history = []
    conv_data = None
    if conv_id:
        conv_data = load_conversation(conv_id)
        if conv_data:
            conversation_history = conv_data.get("messages", [])

    def generate():
        answer_text = ""
        sources = []
        pipeline_stages = []
        total_duration_ms = 0

        for event in ask_graph_rag_stream(query_text, conversation_history):
            event_type = event.get("event", "unknown")
            event_data = event.get("data", {})

            if event_type == "answer":
                answer_text = event_data.get("answer", "")
                sources = event_data.get("sources", [])
                pipeline_stages = event_data.get("pipeline_stages", [])
                total_duration_ms = event_data.get("total_duration_ms", 0)

            sse_line = f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            yield sse_line

        # Mesajlari sohbete kaydet
        if conv_data is not None:
            now = datetime.now().isoformat()
            conv_data["messages"].append({
                "role": "user",
                "content": query_text,
                "timestamp": now
            })
            conv_data["messages"].append({
                "role": "assistant",
                "content": answer_text,
                "timestamp": now,
                "sources": sources,
                "pipeline_stages": pipeline_stages,
                "total_duration_ms": total_duration_ms
            })
            # Ilk mesajsa baslik olustur (ilk 50 karakter)
            if len(conv_data["messages"]) == 2:
                conv_data["title"] = query_text[:50] + ("..." if len(query_text) > 50 else "")
            save_conversation(conv_data)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ================================================
# Neo4j Istatistikler
# ================================================
@app.route("/api/stats", methods=["GET"])
def api_stats():
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )
    db_name = config.NEO4J_DATABASE
    try:
        stats = {}
        for label, key in [("Entity", "entities"), ("Chunk", "chunks"),
                            ("Document", "documents"), ("Community", "communities")]:
            records, _, _ = driver.execute_query(
                f"MATCH (n:{label}) RETURN count(n) AS cnt", database_=db_name
            )
            stats[key] = records[0]["cnt"] if records else 0

        records, _, _ = driver.execute_query(
            """MATCH (:Entity)-[r]-(:Entity)
               WHERE NOT type(r) IN ['MENTIONS', 'PART_OF', 'IN_COMMUNITY']
               RETURN count(r) AS cnt""",
            database_=db_name
        )
        stats["relations"] = records[0]["cnt"] if records else 0
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Istatistik hatasi: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        driver.close()


@app.route("/api/graph", methods=["GET"])
def api_graph():
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )
    db_name = config.NEO4J_DATABASE
    try:
        query = """
        MATCH (e1:Entity)-[r]->(e2:Entity)
        WHERE NOT type(r) IN ['MENTIONS', 'PART_OF', 'IN_COMMUNITY']
        RETURN e1.name AS source, e1.type AS source_type,
               type(r) AS relation,
               e2.name AS target, e2.type AS target_type
        LIMIT 100
        """
        records, _, _ = driver.execute_query(query, database_=db_name)
        nodes = {}
        edges = []
        for r in records:
            src, tgt = r["source"], r["target"]
            if src not in nodes:
                nodes[src] = {"id": src, "label": src, "type": r.get("source_type", "Concept")}
            if tgt not in nodes:
                nodes[tgt] = {"id": tgt, "label": tgt, "type": r.get("target_type", "Concept")}
            edges.append({"source": src, "target": tgt, "relation": r["relation"]})
        return jsonify({"nodes": list(nodes.values()), "edges": edges})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  GraphRAG Web Arayuzu Baslatiliyor...")
    print("  URL: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
