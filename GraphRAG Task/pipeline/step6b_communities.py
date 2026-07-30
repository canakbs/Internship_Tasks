import json
import time
import logging
import sys
from pathlib import Path
import networkx as nx
from neo4j import GraphDatabase

# Proje dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger("GraphRAG.Step6b")

def detect_and_summarize_communities() -> bool:
    """
    Neo4j'deki varlık grafını Python NetworkX kütüphanesine çeker, Louvain algoritmasıyla
    toplulukları tespit eder, her topluluğu Gemini ile özetleyip Neo4j'ye kaydeder.
    
    Returns:
        bool: İşlemin başarı durumu.
    """
    start_time = time.time()
    logger.info("Adım 6b Başladı: NetworkX Louvain ile topluluk tespiti ve Gemini özetleme yapılıyor.")
    
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY bulunamadı!")
        return False

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    db_name = config.NEO4J_DATABASE
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )
    
    try:
        # 1. Neo4j'den tüm anlamsal ilişkileri çekip NetworkX Grafı oluştur
        rel_query = """
        MATCH (e1:Entity)-[r]->(e2:Entity)
        WHERE NOT (e1:Chunk) AND NOT (e2:Chunk) AND NOT type(r) IN ['MENTIONS', 'PART_OF', 'IN_COMMUNITY']
        RETURN e1.name AS source, e2.name AS target
        """
        records, _, _ = driver.execute_query(rel_query, database_=db_name)
        
        G = nx.Graph()
        for rec in records:
            G.add_edge(rec["source"], rec["target"])
            
        if G.number_of_nodes() == 0:
            logger.warning("Graf üzerinde ilişki/düğüm bulunamadı. Topluluk tespiti atlanıyor.")
            return True
            
        # 2. Louvain topluluk tespiti çalıştır
        communities_set = nx.community.louvain_communities(G, seed=42)
        # 1 elemanlı mikro toplulukları gürültü önlemek için filtrele (en az 2 varlık)
        filtered_communities = [list(c) for c in communities_set if len(c) >= 2]
        communities = filtered_communities if filtered_communities else [list(c) for c in communities_set]
        
        logger.info(f"{G.number_of_nodes()} varlık üzerinden {len(communities)} anlamlı topluluk tespit edildi.")
        
        # 3. Her topluluk için metin bağlamını topla ve Gemini ile özetle
        comm_records = []
        for idx, entity_list in enumerate(communities):
            comm_id = f"comm_{idx + 1:03d}"
            
            # Bu topluluktaki varlıkların geçtiği chunk metinlerini çek
            chunks_query = """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE e.name IN $entities
            RETURN DISTINCT c.text AS text
            LIMIT 5
            """
            c_records, _, _ = driver.execute_query(chunks_query, entities=entity_list, database_=db_name)
            context_texts = [r["text"] for r in c_records]
            
            prompt = f"""
Aşağıda aynı konu kümesinde (toplulukta) yer alan varlıklar ve bu varlıklarla ilgili örnek metinler verilmiştir.
Bu topluluğun temsil ettiği ana temayı, varlıkların birbiriyle ilişkilerini ve odak noktasını içeren 2-3 cümlelik özlü bir Türkçe özet oluştur.

Topluluk Varlıkları: {', '.join(entity_list[:15])}
Örnek Bağlam Metinleri:
{" --- ".join(context_texts[:3])}
"""
            summary = "Bu topluluk yapay zeka ile ilgili genel kavramları içerir."
            try:
                res = client.models.generate_content(
                    model=config.LLM_MODEL,
                    contents=prompt
                )
                if res.text:
                    summary = res.text.strip()
            except Exception as e:
                logger.warning(f"Topluluk özeti üretilemedi ({comm_id}): {e}")
                
            comm_records.append({
                "community_id": comm_id,
                "summary": summary,
                "entities": entity_list,
                "embedding": []
            })
            logger.debug(f"Topluluk {comm_id} özetlendi ({len(entity_list)} varlık): {summary[:80]}...")
            
            # Free tier rate limit koruması
            if idx < len(communities) - 1:
                time.sleep(13)

        # 3b. Topluluk özetleri için toplu (batch) embedding üret
        summaries = [c["summary"] for c in comm_records]
        if summaries:
            logger.info("Topluluk özetleri için vektör embedding'leri üretiliyor...")
            try:
                emb_res = client.models.embed_content(
                    model=config.EMBEDDING_MODEL,
                    contents=summaries
                )
                if hasattr(emb_res, 'embeddings'):
                    for idx, emb in enumerate(emb_res.embeddings):
                        comm_records[idx]["embedding"] = list(emb.values)
                elif hasattr(emb_res, 'embedding'):
                    comm_records[0]["embedding"] = list(emb.embedding.values)
                logger.info("Topluluk embedding'leri başarıyla oluşturuldu.")
            except Exception as e:
                logger.warning(f"Topluluk embedding'leri üretilirken hata: {e}")

        # 4. Topluluk düğümlerini ve (:Entity)-[:IN_COMMUNITY]->(:Community) ilişkilerini Neo4j'ye MERGE et
        create_comm_query = """
        UNWIND $communities AS comm
        MERGE (c:Community {community_id: comm.community_id})
        SET c.summary = comm.summary, c.embedding = comm.embedding
        WITH c, comm
        UNWIND comm.entities AS ent_name
        MATCH (e:Entity {name: ent_name})
        MERGE (e)-[:IN_COMMUNITY]->(c)
        """
        driver.execute_query(create_comm_query, communities=comm_records, database_=db_name)
        
        elapsed = time.time() - start_time
        avg_size = sum(len(c) for c in communities) / len(communities) if communities else 0
        logger.info(f"Adım 6b Tamamlandı: {len(communities)} topluluk özetlenip Neo4j'ye kaydedildi (Ortalama küme boyutu: {avg_size:.1f} varlık). Süre: {elapsed:.2f} saniye.")
        return True
        
    except Exception as e:
        logger.error(f"Topluluk tespiti/özetleme sırasında hata: {e}")
        return False
    finally:
        driver.close()

if __name__ == "__main__":
    config.setup_logging("DEBUG")
    detect_and_summarize_communities()
