import json
import time
import logging
import sys
import urllib.parse
from pathlib import Path
from pydantic import BaseModel, Field
from neo4j import GraphDatabase

# Proje dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

logger = logging.getLogger("GraphRAG.Step7")

def clean_bibliography(response_text: str, sources_map: dict) -> tuple[str, dict]:
    """
    1. LLM'in ürettiği Kaynakça bölümünü tamamen siler.
    2. Gövde metninde hangi kaynaklara atıf yapıldığını tespit eder.
    3. Sadece gerçekten atıf yapılan kaynakları içeren yeni bir Kaynakça bölümü
       programatik olarak oluşturur.
    """
    import urllib.parse
    import re
    import unicodedata
    
    def _normalize(s: str) -> str:
        return unicodedata.normalize("NFC", s).lower().strip()
    
    split_pattern = r'(?im)^(?:#{1,4}\s*|\*\*\s*)?kaynak(?:[çcÇC]a|lar|LER)(?:\s*\*\*)?\s*$'
    split_match = re.search(split_pattern, response_text)
    body = response_text[:split_match.start()].rstrip() if split_match else response_text.rstrip()

    cited_map = {}
    for title, source in sources_map.items():
        url = source.get("url", "")
        if title and re.search(rf"\[\s*{re.escape(title)}\s*\]\(", body, re.IGNORECASE):
            cited_map[title] = source
        elif title and re.search(rf"\(\s*{re.escape(title)}\s*\)", body, re.IGNORECASE):
            cited_map[title] = source
        elif url:
            unquoted_url = urllib.parse.unquote(url)
            quoted_url = urllib.parse.quote(unquoted_url, safe=":/")
            if url in body or quoted_url in body or unquoted_url in body:
                cited_map[title] = source
                
    if not cited_map:
        return body, {}
        
    bib_lines = ["\n\n### Kaynakça"]
    for title, src in cited_map.items():
        bib_lines.append(f"* [{title}]({src['url']})")
        
    cleaned_text = body + "\n".join(bib_lines) + "\n"
    return cleaned_text, cited_map

class HasInfoModel(BaseModel):
    has_info: bool = Field(description="Yanıt kullanıcının sorusuna bilgi veriyorsa True, 'bilgi bulunmamaktadır/yanıt verilemiyor' diyorsa False")

def verify_response_has_info(client, response_text: str) -> bool:
    """
    LLM Kontrol Katmanı (Guardrail):
    Structured Output (Pydantic) kullanarak üretilen yanıtın bilgi verip vermediğini kesin olarak doğrular.
    """
    try:
        import re
        split_pattern = r'(?im)^(?:#{1,4}\s*|\*\*\s*)?kaynak(?:[çcÇC]a|lar|LER)(?:\s*\*\*)?\s*$'
        split_match = re.search(split_pattern, response_text)
        body = response_text[:split_match.start()].rstrip() if split_match else response_text.rstrip()

        prompt = f"""Aşağıdaki asistan yanıtını incele:
\"\"\"{body}\"\"\"

Soru: Bu yanıt kullanıcının sorusuna bilgi/cevap veriyor mu, yoksa veritabanında/bağlamda bilgi bulunmadığını mı belirtiyor?
Eğer bilgi veriyorsa has_info=True, bilgi bulunmadığını/yanıt verilemediğini belirtiyorsa has_info=False döndür."""

        res = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=HasInfoModel,
                temperature=0.0
            )
        )
        if res.text:
            data = json.loads(res.text)
            has_info = data.get("has_info", True)
            logger.info(f"LLM Guardrail Pydantic Sonucu: has_info={has_info}")
            return has_info
        return True
    except Exception as e:
        logger.warning(f"LLM Guardrail kontrol hatasi: {e}")
        return True

class RelevanceScoreModel(BaseModel):
    relevance_score: int = Field(description="Topluluk özetinin soruyla alaka puanı (0 ile 100 arasında bir tamsayı)")
    reasoning: str = Field(description="Puanlama gerekçesi (kısa açıklama)")

def ask_graph_rag(query_text: str) -> str:
    """
    Kullanıcı sorusunu yanıtlamak için Yerel (Vector + 1-Hop Graph) ve Küresel (Dinamik Topluluk Seçimi)
    GraphRAG mekanizmasını birleştirerek Gemini ile yanıt üretir.
    
    Args:
        query_text (str): Kullanıcının sorduğu soru.
        
    Returns:
        str: Gemini tarafından üretilen yanıt.
    """
    start_time = time.time()
    logger.info(f"Adım 7 Başladı: GraphRAG Sorgusu İşleniyor -> '{query_text}'")
    
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY bulunamadı!")
        return "Hata: Gemini API anahtarı tanımlanmamış."

    if genai is None:
        logger.error("google-genai kütüphanesi yüklenemedi!")
        return "Hata: google-genai kütüphanesi eksik."

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    db_name = config.NEO4J_DATABASE
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )
    
    try:
        # ==========================================
        # 1. YEREL BAĞLAM (Vector Search + 1-Hop Expansion)
        # ==========================================
        # Sorunun embedding vektörünü al
        q_emb_res = client.models.embed_content(
            model=config.EMBEDDING_MODEL,
            contents=query_text
        )
        q_vector = None
        if hasattr(q_emb_res, 'embedding') and hasattr(q_emb_res.embedding, 'values'):
            q_vector = list(q_emb_res.embedding.values)
        elif hasattr(q_emb_res, 'embeddings') and len(q_emb_res.embeddings) > 0:
            q_vector = list(q_emb_res.embeddings[0].values)
            
        local_chunks = []
        chunk_ids = []
        sources_map = {}
        if q_vector:
            vector_query = """
            CALL db.index.vector.queryNodes('chunk_embeddings', 5, $q_vector)
            YIELD node AS chunk, score
            OPTIONAL MATCH (chunk)-[:PART_OF]->(doc:Document)
            RETURN chunk.chunk_id AS chunk_id, chunk.text AS text, chunk.article_title AS article_title, doc.url AS url, score
            """
            v_records, _, _ = driver.execute_query(vector_query, q_vector=q_vector, database_=db_name)
            for r in v_records:
                title = r.get("article_title") or "Wikipedia"
                url = r.get("url") or ""
                if url:
                    url = urllib.parse.quote(urllib.parse.unquote(url), safe=":/")
                source_meta = f"[Kaynak Makale: {title}]" + (f" (URL: {url})" if url else "")
                local_chunks.append(f"{source_meta}\n{r['text']}")
                chunk_ids.append(r["chunk_id"])
                if title not in sources_map and url:
                    sources_map[title] = {"title": title, "url": url}
                
        # 1-Hop Graph Genişletme (İlgili varlıklar etrafındaki anlamsal ilişkiler)
        graph_triples = []
        if chunk_ids:
            graph_query = """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE c.chunk_id IN $chunk_ids
            OPTIONAL MATCH (e)-[r]-(e2:Entity)
            WHERE NOT type(r) IN ['MENTIONS', 'PART_OF', 'IN_COMMUNITY']
            RETURN DISTINCT e.name AS source, type(r) AS rel_type, e2.name AS target
            LIMIT 30
            """
            g_records, _, _ = driver.execute_query(graph_query, chunk_ids=chunk_ids, database_=db_name)
            for r in g_records:
                if r["source"] and r["target"] and r["rel_type"]:
                    graph_triples.append(f"({r['source']}) -[{r['rel_type']}]-> ({r['target']})")
                    
        logger.debug(f"Yerel Bağlam: {len(local_chunks)} chunk, {len(graph_triples)} graf üçlüsü çekildi.")

        # ==========================================
        # 2. KÜRESEL BAĞLAM (Vektör Benzerliği ile Anında Topluluk Seçimi)
        # ==========================================
        comm_query = "MATCH (c:Community) RETURN c.community_id AS id, c.summary AS summary, c.embedding AS embedding"
        c_records_raw, _, _ = driver.execute_query(comm_query, database_=db_name)
        c_records = [dict(r) for r in c_records_raw]
        
        selected_community_summaries = []
        logger.info(f"Topluluk Alaka Değerlendirmesi Başladı: Toplam {len(c_records)} topluluk vektör benzerliği ile analiz ediliyor.")
        
        # Eğer veritabanındaki topluluklarda embedding eksikse, tek seferde batch embed et
        missing_embs = [r for r in c_records if not r.get("embedding")]
        if missing_embs and q_vector:
            logger.info("Eksik topluluk embedding'leri anlık üretiliyor...")
            try:
                summaries_to_embed = [r["summary"] for r in missing_embs]
                emb_res = client.models.embed_content(
                    model=config.EMBEDDING_MODEL,
                    contents=summaries_to_embed
                )
                emb_list = []
                if hasattr(emb_res, 'embeddings'):
                    emb_list = [list(e.values) for e in emb_res.embeddings]
                elif hasattr(emb_res, 'embedding'):
                    emb_list = [list(emb_res.embedding.values)]
                
                # c_records içi güncelle
                emb_idx = 0
                for r in c_records:
                    if not r.get("embedding") and emb_idx < len(emb_list):
                        r["embedding"] = emb_list[emb_idx]
                        emb_idx += 1
            except Exception as e:
                logger.warning(f"Toplu topluluk embedding üretme hatası: {e}")

        # Vektör Benzerliği (Cosine Similarity) Hesapla
        scored_communities = []
        for c_item in c_records:
            cid = c_item["id"]
            summary = c_item["summary"]
            c_emb = c_item.get("embedding")
            
            score = 0.0
            if q_vector and c_emb and len(q_vector) == len(c_emb):
                dot = sum(a * b for a, b in zip(q_vector, c_emb))
                norm_q = (sum(a * a for a in q_vector)) ** 0.5
                norm_c = (sum(b * b for b in c_emb)) ** 0.5
                if norm_q > 0 and norm_c > 0:
                    score = dot / (norm_q * norm_c)
            
            scored_communities.append({
                "id": cid,
                "summary": summary,
                "score": score
            })
            
        # Skorlara göre büyükten küçüğe sırala
        scored_communities.sort(key=lambda x: x["score"], reverse=True)
        
        # En yüksek benzerliğe sahip ilk 4 topluluğu seç
        TOP_K = 4
        for idx, item in enumerate(scored_communities):
            cid = item["id"]
            summary = item["summary"]
            score = item["score"]
            
            if idx < TOP_K and score > 0.25:
                selected_community_summaries.append(f"[{cid}] {summary}")
                logger.info(f"Topluluk SEÇİLDİ (Vektör Skoru: {score:.3f}): {cid} | Özet: {summary[:80]}...")
            else:
                logger.debug(f"Topluluk elendi ({cid}) | Vektör Skoru: {score:.3f}")
                
        # ==========================================
        # 3. YEREL + KÜRESEL BAĞLAMI BİRLEŞTİRME VE YANIT ÜRETİMİ
        # ==========================================
        context_parts = []
        
        if local_chunks:
            context_parts.append("--- YEREL METİN PARÇALARI VE KAYNAKLARI ---")
            context_parts.extend(local_chunks)
            
        if graph_triples:
            context_parts.append("\n--- İLGİLİ VARLIK VEYA İLİŞKİLER (GRAPH) ---")
            context_parts.extend(graph_triples)
            
        if selected_community_summaries:
            context_parts.append("\n--- KÜRESEL TOPLULUK ÖZETLERİ ---")
            context_parts.extend(selected_community_summaries)
            
        full_context = "\n".join(context_parts)
        
        final_prompt = f"""
Sen Wikipedia verilerinden oluşturulmuş bilgi grafiği ve vektör verilerini kullanan uzman bir GraphRAG asistanısın.
Aşağıda yer alan YEREL (metin parçaları + kaynak URL'leri + graf ilişkileri) ve KÜRESEL (topluluk özetleri) bağlam bilgilerini kullanarak kullanıcının sorusuna detaylı, doğru ve akıcı bir Türkçe yanıt ver.

Bağlam Bilgileri:
{full_context}

Kullanıcı Sorusu:
"{query_text}"

ATIF YÖNERGELERİ (ÇOK ÖNEMLİ):
1. Yanıt içerisinde verdiğin bilgilerin dayandığı ilgili kaynaklara mutlaka metin içi Markdown bağlantısı (link) şeklinde atıf yap.
   - Örnek: "Modern yapay zekanın temelleri 1956 yılındaki Dartmouth Atölyesi'nde atılmıştır ([Yapay zekâ](https://tr.wikipedia.org/wiki/Yapay_zek%C3%A2))."
2. YALNIZCA bilgiyi gerçekten aldığın kaynak makale(ler)e atıf yap. Bağlamda yer alan ama yanıt üretmede kullanmadığın kaynakları kesinlikle ekleme.
3. Yanıtın sonuna "Kaynakça" veya "Kaynaklar" başlığı EKLEME. Kaynakça bölümü sistem tarafından otomatik oluşturulacaktır.
"""
        response_text = "Yanıt üretilemedi."
        res = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=final_prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        if res.text:
            response_text = res.text.strip()
            if response_text and sources_map:
                response_text, _ = clean_bibliography(response_text, sources_map)
            
        elapsed = time.time() - start_time
        logger.info(f"Adım 7 Tamamlandı: Yanıt üretildi ({len(selected_community_summaries)} topluluk bağlama dahil edildi). Süre: {elapsed:.2f} saniye.")
        return response_text
        
    except Exception as e:
        logger.error(f"GraphRAG sorgusu işlenirken hata: {e}")
        return f"Sorgu işlenirken hata oluştu: {e}"
    finally:
        driver.close()

def ask_graph_rag_detailed(query_text: str) -> dict:
    """
    ask_graph_rag ile aynı mantığı kullanır, ancak her aşamanın detay bilgisini
    (süre, bulunan chunk'lar, seçilen topluluklar, graf üçlüleri) yapısal olarak döndürür.
    Web arayüzü için tasarlanmıştır.
    
    Args:
        query_text (str): Kullanıcının sorduğu soru.
        
    Returns:
        dict: answer, stages, sources, total_duration_ms anahtarlarını içeren sonuç.
    """
    import time as _time
    
    result = {
        "answer": "",
        "stages": {},
        "sources": [],
        "total_duration_ms": 0
    }
    
    total_start = _time.time()
    logger.info(f"Detaylı Sorgu Başladı: '{query_text}'")
    
    if not config.GEMINI_API_KEY:
        result["answer"] = "Hata: Gemini API anahtarı tanımlanmamış."
        return result
    
    if genai is None:
        result["answer"] = "Hata: google-genai kütüphanesi eksik."
        return result
    
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    db_name = config.NEO4J_DATABASE
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )
    
    try:
        # ========== AŞAMA 1: Embedding ==========
        stage_start = _time.time()
        q_emb_res = client.models.embed_content(
            model=config.EMBEDDING_MODEL,
            contents=query_text
        )
        q_vector = None
        if hasattr(q_emb_res, 'embedding') and hasattr(q_emb_res.embedding, 'values'):
            q_vector = list(q_emb_res.embedding.values)
        elif hasattr(q_emb_res, 'embeddings') and len(q_emb_res.embeddings) > 0:
            q_vector = list(q_emb_res.embeddings[0].values)
        
        emb_dim = len(q_vector) if q_vector else 0
        result["stages"]["embedding"] = {
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "detail": f"Soru vektörü üretildi ({emb_dim} boyut)"
        }
        
        # ========== AŞAMA 2: Vector Search ==========
        stage_start = _time.time()
        local_chunks = []
        chunk_ids = []
        sources_map = {}
        
        if q_vector:
            vector_query = """
            CALL db.index.vector.queryNodes('chunk_embeddings', 5, $q_vector)
            YIELD node AS chunk, score
            OPTIONAL MATCH (chunk)-[:PART_OF]->(doc:Document)
            RETURN chunk.chunk_id AS chunk_id, chunk.text AS text, chunk.article_title AS article_title, doc.url AS url, score
            """
            v_records, _, _ = driver.execute_query(vector_query, q_vector=q_vector, database_=db_name)
            for r in v_records:
                title = r.get("article_title") or "Wikipedia"
                url = r.get("url") or ""
                if url:
                    url = urllib.parse.quote(urllib.parse.unquote(url), safe=":/")
                score = round(float(r.get("score", 0)), 4)
                chunk_id = r["chunk_id"]
                
                source_meta = f"[Kaynak Makale: {title}]" + (f" (URL: {url})" if url else "")
                local_chunks.append(f"{source_meta}\n{r['text']}")
                chunk_ids.append(chunk_id)
                
                # Kaynak bilgisi
                if title not in sources_map:
                    sources_map[title] = {
                        "title": title,
                        "url": url,
                        "chunk_id": chunk_id,
                        "score": score
                    }
                    
        vs_chunks_detail = []
        for r in (v_records if q_vector else []):
            vs_chunks_detail.append({
                "chunk_id": r["chunk_id"],
                "article_title": r.get("article_title") or "",
                "score": round(float(r.get("score", 0)), 4),
                "text_preview": (r.get("text") or "")[:200] + "..."
            })
        
        result["stages"]["vector_search"] = {
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "chunks_found": len(local_chunks),
            "detail": f"{len(local_chunks)} benzer chunk bulundu",
            "chunks": vs_chunks_detail
        }
        
        # ========== AŞAMA 3: Graph Expansion ==========
        stage_start = _time.time()
        graph_triples = []
        triples_detail = []
        
        if chunk_ids:
            graph_query = """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE c.chunk_id IN $chunk_ids
            OPTIONAL MATCH (e)-[r]-(e2:Entity)
            WHERE NOT type(r) IN ['MENTIONS', 'PART_OF', 'IN_COMMUNITY']
            RETURN DISTINCT e.name AS source, type(r) AS rel_type, e2.name AS target
            LIMIT 30
            """
            g_records, _, _ = driver.execute_query(graph_query, chunk_ids=chunk_ids, database_=db_name)
            for r in g_records:
                if r["source"] and r["target"] and r["rel_type"]:
                    triple_str = f"({r['source']}) -[{r['rel_type']}]-> ({r['target']})"
                    graph_triples.append(triple_str)
                    triples_detail.append({
                        "source": r["source"],
                        "relation": r["rel_type"],
                        "target": r["target"]
                    })
        
        result["stages"]["graph_expansion"] = {
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "triples_found": len(graph_triples),
            "detail": f"{len(graph_triples)} graf üçlüsü genişletildi",
            "triples": triples_detail
        }
        
        # ========== AŞAMA 4: Community Selection ==========
        stage_start = _time.time()
        comm_query = "MATCH (c:Community) RETURN c.community_id AS id, c.summary AS summary, c.embedding AS embedding"
        c_records_raw, _, _ = driver.execute_query(comm_query, database_=db_name)
        c_records = [dict(r) for r in c_records_raw]
        
        selected_community_summaries = []
        communities_detail = []
        
        # Eksik embedding'leri batch embed et
        missing_embs = [r for r in c_records if not r.get("embedding")]
        if missing_embs and q_vector:
            try:
                summaries_to_embed = [r["summary"] for r in missing_embs]
                emb_res = client.models.embed_content(
                    model=config.EMBEDDING_MODEL,
                    contents=summaries_to_embed
                )
                emb_list = []
                if hasattr(emb_res, 'embeddings'):
                    emb_list = [list(e.values) for e in emb_res.embeddings]
                elif hasattr(emb_res, 'embedding'):
                    emb_list = [list(emb_res.embedding.values)]
                emb_idx = 0
                for r in c_records:
                    if not r.get("embedding") and emb_idx < len(emb_list):
                        r["embedding"] = emb_list[emb_idx]
                        emb_idx += 1
            except Exception as e:
                logger.warning(f"Toplu topluluk embedding üretme hatası: {e}")
        
        # Cosine Similarity hesapla
        scored_communities = []
        for c_item in c_records:
            cid = c_item["id"]
            summary = c_item["summary"]
            c_emb = c_item.get("embedding")
            
            score = 0.0
            if q_vector and c_emb and len(q_vector) == len(c_emb):
                dot = sum(a * b for a, b in zip(q_vector, c_emb))
                norm_q = (sum(a * a for a in q_vector)) ** 0.5
                norm_c = (sum(b * b for b in c_emb)) ** 0.5
                if norm_q > 0 and norm_c > 0:
                    score = dot / (norm_q * norm_c)
            
            scored_communities.append({"id": cid, "summary": summary, "score": score})
        
        scored_communities.sort(key=lambda x: x["score"], reverse=True)
        
        TOP_K = 4
        for idx, item in enumerate(scored_communities):
            selected = idx < TOP_K and item["score"] > 0.25
            if selected:
                selected_community_summaries.append(f"[{item['id']}] {item['summary']}")
            communities_detail.append({
                "id": item["id"],
                "summary": item["summary"][:150] + ("..." if len(item["summary"]) > 150 else ""),
                "score": round(item["score"], 4),
                "selected": selected
            })
        
        result["stages"]["community_selection"] = {
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "communities_evaluated": len(c_records),
            "selected": len(selected_community_summaries),
            "detail": f"{len(c_records)} topluluk değerlendirildi, {len(selected_community_summaries)} tanesi seçildi",
            "communities": communities_detail[:10]
        }
        
        # ========== AŞAMA 5: Generation ==========
        stage_start = _time.time()
        
        context_parts = []
        if local_chunks:
            context_parts.append("--- YEREL METİN PARÇALARI VE KAYNAKLARI ---")
            context_parts.extend(local_chunks)
        if graph_triples:
            context_parts.append("\n--- İLGİLİ VARLIK VEYA İLİŞKİLER (GRAPH) ---")
            context_parts.extend(graph_triples)
        if selected_community_summaries:
            context_parts.append("\n--- KÜRESEL TOPLULUK ÖZETLERİ ---")
            context_parts.extend(selected_community_summaries)
        
        full_context = "\n".join(context_parts)
        
        final_prompt = f"""
Sen Wikipedia verilerinden oluşturulmuş bilgi grafiği ve vektör verilerini kullanan uzman bir GraphRAG asistanısın.
Aşağıda yer alan YEREL (metin parçaları + kaynak URL'leri + graf ilişkileri) ve KÜRESEL (topluluk özetleri) bağlam bilgilerini kullanarak kullanıcının sorusuna detaylı, doğru ve akıcı bir Türkçe yanıt ver.

Bağlam Bilgileri:
{full_context}

Kullanıcı Sorusu:
"{query_text}"

ATIF YÖNERGELERİ (ÇOK ÖNEMLİ):
1. Yanıt içerisinde verdiğin bilgilerin dayandığı ilgili kaynaklara mutlaka metin içi Markdown bağlantısı (link) şeklinde atıf yap.
   - Örnek: "Modern yapay zekanın temelleri 1956 yılındaki Dartmouth Atölyesi'nde atılmıştır ([Yapay zekâ](https://tr.wikipedia.org/wiki/Yapay_zek%C3%A2))."
2. YALNIZCA bilgiyi gerçekten aldığın kaynak makale(ler)e atıf yap. Bağlamda yer alan ama yanıt üretmede kullanmadığın kaynakları kesinlikle ekleme.
3. Yanıtın sonuna "Kaynakça" veya "Kaynaklar" başlığı EKLEME. Kaynakça bölümü sistem tarafından otomatik oluşturulacaktır.
"""
        response_text = "Yanıt üretilemedi."
        res = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=final_prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        if res.text:
            response_text = res.text.strip()
        
        result["stages"]["generation"] = {
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "model": config.LLM_MODEL,
            "detail": f"Gemini ({config.LLM_MODEL}) ile yanıt üretildi"
        }
        
        # Gizli LLM Kontrol Katmanı (Guardrail): Yanıtın bilgi içerip içermediğini sorgula
        has_info = verify_response_has_info(client, response_text)
        
        if not has_info:
            # Eğer yanıt "bilgi bulunmamaktadır" diyorsa kaynakçayı ve kaynaklar listesini tamamen SIFIRLA
            import re
            split_pattern = r'(?im)^(?:#{1,4}\s*|\*\*\s*)?kaynak(?:[çcÇC]a|lar|LER)(?:\s*\*\*)?\s*$'
            split_match = re.search(split_pattern, response_text)
            if split_match:
                response_text = response_text[:split_match.start()].rstrip()
            cited_sources = {}
        elif response_text and sources_map:
            response_text, cited_sources = clean_bibliography(response_text, sources_map)
        else:
            cited_sources = {}
            
        result["answer"] = response_text
        result["sources"] = list(cited_sources.values())
        result["total_duration_ms"] = round((_time.time() - total_start) * 1000)
        
        logger.info(f"Detaylı Sorgu Tamamlandı: {result['total_duration_ms']}ms")
        return result
        
    except Exception as e:
        logger.error(f"Detaylı GraphRAG sorgusu işlenirken hata: {e}")
        result["answer"] = f"Sorgu işlenirken hata oluştu: {e}"
        result["total_duration_ms"] = round((_time.time() - total_start) * 1000)
        return result
    finally:
        driver.close()


def ask_graph_rag_stream(query_text: str, conversation_history: list = None):
    """
    Generator fonksiyon: Her RAG aşaması tamamlandığında yield ile SSE event gönderir.
    Sohbet belleği desteği için conversation_history parametresi alır.
    
    Args:
        query_text (str): Kullanıcının sorduğu soru.
        conversation_history (list): Önceki mesajlar [{role, content}, ...]
        
    Yields:
        dict: Her aşamanın sonuç verisi (event tipi ve data).
    """
    import time as _time
    
    total_start = _time.time()
    logger.info(f"Streaming Sorgu Basladi: '{query_text}'")
    
    if not config.GEMINI_API_KEY:
        yield {"event": "error", "data": {"message": "Gemini API anahtari tanimlanmamis."}}
        return
    
    if genai is None:
        yield {"event": "error", "data": {"message": "google-genai kutuphanesi eksik."}}
        return
    
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    db_name = config.NEO4J_DATABASE
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )
    
    sources_map = {}
    local_chunks = []
    graph_triples = []
    selected_community_summaries = []
    collected_stages = []  # Pipeline verilerini topla (sohbete kaydetmek icin)
    
    search_query = query_text
    
    # Sohbet geçmişi varsa sorguyu netleştir (Query Rewriting)
    if conversation_history and len(conversation_history) > 0:
        try:
            hist_summary = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in conversation_history[-4:]])
            rewrite_prompt = f"""Önceki Sohbet Geçmişi:
{hist_summary}

Son Kullanıcı Sorusu: "{query_text}"

GÖREV: Kullanıcının son sorusu "orada kimler vardı", "tarihi nedir" gibi eksik/zamirli ifadeler içeriyorsa, sohbet geçmişini kullanarak bunu bağımsız, net bir arama cümlesine dönüştür. Sadece dönüştürülen tek cümlelik net soruyu yaz, açıklama yapma.
Örnek: "Dartmouth Atölyesi'ne katılan kişiler kimlerdir?" """
            rw_res = client.models.generate_content(
                model=config.LLM_MODEL,
                contents=rewrite_prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            if rw_res.text and rw_res.text.strip():
                search_query = rw_res.text.strip()
                logger.info(f"Sorgu Yeniden Yazıldı: '{query_text}' -> '{search_query}'")
        except Exception as e:
            logger.warning(f"Query rewrite hatasi: {e}")

    try:
        # ========== STAGE 1: Embedding ==========
        stage_start = _time.time()
        q_emb_res = client.models.embed_content(
            model=config.EMBEDDING_MODEL,
            contents=search_query
        )
        q_vector = None
        if hasattr(q_emb_res, 'embedding') and hasattr(q_emb_res.embedding, 'values'):
            q_vector = list(q_emb_res.embedding.values)
        elif hasattr(q_emb_res, 'embeddings') and len(q_emb_res.embeddings) > 0:
            q_vector = list(q_emb_res.embeddings[0].values)
        
        emb_dim = len(q_vector) if q_vector else 0
        stage_data = {
            "stage": "embedding",
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "detail": f"Soru vektoru uretildi ({emb_dim} boyut)"
        }
        collected_stages.append(stage_data)
        yield {"event": "stage", "data": stage_data}
        
        # ========== STAGE 2: Vector Search ==========
        stage_start = _time.time()
        chunk_ids = []
        vs_chunks_detail = []
        
        if q_vector:
            vector_query = """
            CALL db.index.vector.queryNodes('chunk_embeddings', 5, $q_vector)
            YIELD node AS chunk, score
            OPTIONAL MATCH (chunk)-[:PART_OF]->(doc:Document)
            RETURN chunk.chunk_id AS chunk_id, chunk.text AS text, chunk.article_title AS article_title, doc.url AS url, score
            """
            v_records, _, _ = driver.execute_query(vector_query, q_vector=q_vector, database_=db_name)
            for r in v_records:
                title = r.get("article_title") or "Wikipedia"
                url = r.get("url") or ""
                if url:
                    url = urllib.parse.quote(urllib.parse.unquote(url), safe=":/")
                score = round(float(r.get("score", 0)), 4)
                chunk_id = r["chunk_id"]
                
                source_meta = f"[Kaynak Makale: {title}]" + (f" (URL: {url})" if url else "")
                local_chunks.append(f"{source_meta}\n{r['text']}")
                chunk_ids.append(chunk_id)
                
                if title not in sources_map:
                    sources_map[title] = {"title": title, "url": url, "chunk_id": chunk_id, "score": score}
                
                vs_chunks_detail.append({
                    "chunk_id": chunk_id,
                    "article_title": title,
                    "score": score,
                    "text_preview": (r.get("text") or "")[:200] + "..."
                })
        
        stage_data = {
            "stage": "vector_search",
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "chunks_found": len(local_chunks),
            "detail": f"{len(local_chunks)} benzer chunk bulundu",
            "chunks": vs_chunks_detail
        }
        collected_stages.append(stage_data)
        yield {"event": "stage", "data": stage_data}
        
        # ========== STAGE 3: Graph Expansion ==========
        stage_start = _time.time()
        triples_detail = []
        
        if chunk_ids:
            graph_query = """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE c.chunk_id IN $chunk_ids
            OPTIONAL MATCH (e)-[r]-(e2:Entity)
            WHERE NOT type(r) IN ['MENTIONS', 'PART_OF', 'IN_COMMUNITY']
            RETURN DISTINCT e.name AS source, type(r) AS rel_type, e2.name AS target
            LIMIT 30
            """
            g_records, _, _ = driver.execute_query(graph_query, chunk_ids=chunk_ids, database_=db_name)
            for r in g_records:
                if r["source"] and r["target"] and r["rel_type"]:
                    graph_triples.append(f"({r['source']}) -[{r['rel_type']}]-> ({r['target']})")
                    triples_detail.append({"source": r["source"], "relation": r["rel_type"], "target": r["target"]})
        
        stage_data = {
            "stage": "graph_expansion",
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "triples_found": len(graph_triples),
            "detail": f"{len(graph_triples)} graf uclusu genisletildi",
            "triples": triples_detail
        }
        collected_stages.append(stage_data)
        yield {"event": "stage", "data": stage_data}
        
        # ========== STAGE 4: Community Selection ==========
        stage_start = _time.time()
        comm_query = "MATCH (c:Community) RETURN c.community_id AS id, c.summary AS summary, c.embedding AS embedding"
        c_records_raw, _, _ = driver.execute_query(comm_query, database_=db_name)
        c_records = [dict(r) for r in c_records_raw]
        
        communities_detail = []
        
        missing_embs = [r for r in c_records if not r.get("embedding")]
        if missing_embs and q_vector:
            try:
                summaries_to_embed = [r["summary"] for r in missing_embs]
                emb_res = client.models.embed_content(model=config.EMBEDDING_MODEL, contents=summaries_to_embed)
                emb_list = []
                if hasattr(emb_res, 'embeddings'):
                    emb_list = [list(e.values) for e in emb_res.embeddings]
                elif hasattr(emb_res, 'embedding'):
                    emb_list = [list(emb_res.embedding.values)]
                emb_idx = 0
                for r in c_records:
                    if not r.get("embedding") and emb_idx < len(emb_list):
                        r["embedding"] = emb_list[emb_idx]
                        emb_idx += 1
            except Exception as e:
                logger.warning(f"Topluluk embedding hatasi: {e}")
        
        scored_communities = []
        for c_item in c_records:
            cid = c_item["id"]
            summary = c_item["summary"]
            c_emb = c_item.get("embedding")
            score = 0.0
            if q_vector and c_emb and len(q_vector) == len(c_emb):
                dot = sum(a * b for a, b in zip(q_vector, c_emb))
                norm_q = (sum(a * a for a in q_vector)) ** 0.5
                norm_c = (sum(b * b for b in c_emb)) ** 0.5
                if norm_q > 0 and norm_c > 0:
                    score = dot / (norm_q * norm_c)
            scored_communities.append({"id": cid, "summary": summary, "score": score})
        
        scored_communities.sort(key=lambda x: x["score"], reverse=True)
        TOP_K = 4
        for idx, item in enumerate(scored_communities):
            selected = idx < TOP_K and item["score"] > 0.25
            if selected:
                selected_community_summaries.append(f"[{item['id']}] {item['summary']}")
            communities_detail.append({
                "id": item["id"],
                "summary": item["summary"][:150] + ("..." if len(item["summary"]) > 150 else ""),
                "score": round(item["score"], 4),
                "selected": selected
            })
        
        stage_data = {
            "stage": "community_selection",
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "communities_evaluated": len(c_records),
            "selected": len(selected_community_summaries),
            "detail": f"{len(c_records)} topluluk degerlendirildi, {len(selected_community_summaries)} secildi",
            "communities": communities_detail[:10]
        }
        collected_stages.append(stage_data)
        yield {"event": "stage", "data": stage_data}
        
        # ========== STAGE 5: Generation (with memory) ==========
        stage_start = _time.time()
        
        context_parts = []
        if local_chunks:
            context_parts.append("--- YEREL METIN PARCALARI VE KAYNAKLARI ---")
            context_parts.extend(local_chunks)
        if graph_triples:
            context_parts.append("\n--- ILGILI VARLIK VEYA ILISKILER (GRAPH) ---")
            context_parts.extend(graph_triples)
        if selected_community_summaries:
            context_parts.append("\n--- KURESEL TOPLULUK OZETLERI ---")
            context_parts.extend(selected_community_summaries)
        
        full_context = "\n".join(context_parts)
        
        # Sohbet bellegi olustur
        history_text = ""
        if conversation_history and len(conversation_history) > 0:
            history_parts = []
            for msg in conversation_history[-6:]:  # Son 6 mesaj
                role_label = "Kullanici" if msg.get("role") == "user" else "Asistan"
                history_parts.append(f"{role_label}: {msg.get('content', '')}")
            history_text = "\n".join(history_parts)
        
        memory_section = ""
        if history_text:
            memory_section = f"""
ONCEKI KONUSMA GECMISI (BELLEK):
Asagida kullanici ile daha once yapilan konusma yer almaktadir. Yeni soruyu yanitlarken bu baglamdan yararlan.
{history_text}
---
"""
        
        final_prompt = f"""Sen Wikipedia verilerinden olusturulmus bilgi grafigi ve vektor verilerini kullanan uzman bir GraphRAG asistanisin.
Asagida yer alan YEREL (metin parcalari + kaynak URL'leri + graf iliskileri) ve KURESEL (topluluk ozetleri) baglam bilgilerini kullanarak kullanicinin sorusuna detayli, dogru ve akici bir Turkce yanit ver.

{memory_section}Baglam Bilgileri:
{full_context}

Kullanici Sorusu:
"{query_text}"

ATIF YONERGELERI (COK ONEMLI):
1. Yanit icerisinde verdigin bilgilerin dayandigi ilgili kaynaklara mutlaka metin ici Markdown baglantisi (link) seklinde atif yap.
   - Ornek: "Modern yapay zekanin temelleri 1956 yilindaki Dartmouth Atolyesi'nde atilmistir ([Yapay zeka](https://tr.wikipedia.org/wiki/Yapay_zek%C3%A2))."
2. YALNIZCA bilgiyi gercekten aldigin kaynak makale(ler)e atif yap. Baglamda yer alan ama yanit uretmede kullanmadigin kaynaklari kesinlikle ekleme.
3. Yanitin sonuna "Kaynakca" veya "Kaynaklar" basligi EKLEME. Kaynakca bolumu sistem tarafindan otomatik olusturulacaktir.
"""
        response_text = "Yanit uretilemedi."
        res = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=final_prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        if res.text:
            response_text = res.text.strip()
        
        gen_stage_data = {
            "stage": "generation",
            "status": "done",
            "duration_ms": round((_time.time() - stage_start) * 1000),
            "model": config.LLM_MODEL,
            "detail": f"Gemini ({config.LLM_MODEL}) ile yanit uretildi"
        }
        collected_stages.append(gen_stage_data)
        yield {"event": "stage", "data": gen_stage_data}
        
        # Gizli LLM Kontrol Katmanı (Guardrail): Yanıtın bilgi içerip içermediğini sorgula
        has_info = verify_response_has_info(client, response_text)
        
        if not has_info:
            # Eğer yanıt "bilgi bulunmamaktadır" diyorsa kaynakçayı ve kaynaklar listesini tamamen SIFIRLA
            import re
            split_pattern = r'(?im)^(?:#{1,4}\s*|\*\*\s*)?kaynak(?:[çcÇC]a|lar|LER)(?:\s*\*\*)?\s*$'
            split_match = re.search(split_pattern, response_text)
            if split_match:
                response_text = response_text[:split_match.start()].rstrip()
            cited_sources = {}
        elif response_text and sources_map:
            response_text, cited_sources = clean_bibliography(response_text, sources_map)
        else:
            cited_sources = {}
        
        total_duration_ms = round((_time.time() - total_start) * 1000)
            
        # Yanit, kaynaklar ve pipeline verileri
        yield {
            "event": "answer",
            "data": {
                "answer": response_text,
                "sources": list(cited_sources.values()),
                "pipeline_stages": collected_stages,
                "total_duration_ms": total_duration_ms
            }
        }
        
        # Tamamlandi
        yield {
            "event": "done",
            "data": {
                "total_duration_ms": total_duration_ms
            }
        }
        
    except Exception as e:
        logger.error(f"Streaming sorgu hatasi: {e}")
        err_msg = str(e)
        if "getaddrinfo failed" in err_msg or "NameResolutionError" in err_msg:
            err_msg = "İnternet bağlantısı hatası: Gemini API veya Neo4j sunucusuna ulaşılamadı. Lütfen internet bağlantınızı kontrol edip tekrar deneyin."
        yield {"event": "error", "data": {"message": err_msg}}
    finally:
        try:
            driver.close()
        except Exception:
            pass


if __name__ == "__main__":
    config.setup_logging("INFO")
    test_query = "Yapay zekanin temel alanlari ve tarihsel gelisimi hakkinda bilgi ver."
    answer = ask_graph_rag(test_query)
    print("\n=== YANIT ===")
    print(answer)

