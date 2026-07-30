import json
import time
import logging
import sys
from pathlib import Path
from neo4j import GraphDatabase

# Proje dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger("GraphRAG.Step5")

def get_neo4j_driver():
    """Neo4j veritabanı sürücüsü oluşturur."""
    return GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )

def clear_neo4j_database() -> bool:
    """
    Neo4j veritabanındaki tüm düğümleri ve ilişkileri siler (MATCH (n) DETACH DELETE n).
    """
    logger.info("Neo4j veritabanı temizleniyor (MATCH (n) DETACH DELETE n)...")
    driver = get_neo4j_driver()
    db_name = config.NEO4J_DATABASE
    try:
        driver.execute_query("MATCH (n) DETACH DELETE n", database_=db_name)
        logger.info("Neo4j veritabanı başarıyla temizlendi.")
        return True
    except Exception as e:
        logger.error(f"Neo4j veritabanı temizleme hatası: {e}")
        return False
    finally:
        driver.close()

def load_to_neo4j() -> bool:
    """
    articles.json, chunks.json ve resolved_graph.json verilerini Neo4j'ye MERGE eder.
    
    Returns:
        bool: İşlemin başarı durumu.
    """
    start_time = time.time()
    logger.info("Adım 5 Başladı: Veriler Neo4j veritabanına aktarılıyor (Idempotent MERGE).")
    
    # 1. Dosyaları kontrol et ve oku
    if not (config.ARTICLES_FILE.exists() and config.CHUNKS_FILE.exists() and config.RESOLVED_GRAPH_FILE.exists()):
        logger.error("Gerekli veri dosyalarından biri veya birkaçı bulunamadı!")
        return False
        
    with open(config.ARTICLES_FILE, "r", encoding="utf-8") as f:
        articles = json.load(f)
    with open(config.CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    with open(config.RESOLVED_GRAPH_FILE, "r", encoding="utf-8") as f:
        graph_data = json.load(f)
        
    entities = graph_data.get("entities", [])
    relations = graph_data.get("relations", [])
    
    # Chunk - Entity anma (MENTIONS) bağlantılarını hazırla
    mentions = []
    if config.EXTRACTED_FILE.exists():
        with open(config.EXTRACTED_FILE, "r", encoding="utf-8") as f:
            extracted = json.load(f)
        for ext in extracted:
            c_id = ext["chunk_id"]
            for e in ext.get("entities", []):
                mentions.append({
                    "chunk_id": c_id,
                    "entity_name": e["name"]
                })
                
    db_name = config.NEO4J_DATABASE
    driver = get_neo4j_driver()
    
    try:
        # A. Document düğümlerini yükle
        doc_query = """
        UNWIND $documents AS doc
        MERGE (d:Document {title: doc.title})
        SET d.url = doc.url
        """
        driver.execute_query(doc_query, documents=articles, database_=db_name)
        logger.debug(f"{len(articles)} Document düğümü MERGE edildi.")
        
        # B. Chunk düğümlerini ve PART_OF ilişkilerini yükle
        chunk_query = """
        UNWIND $chunks AS chunk
        MERGE (c:Chunk {chunk_id: chunk.chunk_id})
        SET c.text = chunk.text, c.article_title = chunk.article_title
        WITH c, chunk
        MATCH (d:Document {title: chunk.article_title})
        MERGE (c)-[:PART_OF]->(d)
        """
        driver.execute_query(chunk_query, chunks=chunks, database_=db_name)
        logger.debug(f"{len(chunks)} Chunk düğümü ve PART_OF ilişkisi MERGE edildi.")
        
        # C. Entity düğümlerini dinamik etiketlerle (Person, Event, Concept vb.) yükle
        from collections import defaultdict
        import re
        
        entities_by_type = defaultdict(list)
        for ent in entities:
            raw_type = ent.get("type", "Concept")
            safe_label = re.sub(r'[^A-Za-z0-9]', '', raw_type.title()) or "Concept"
            entities_by_type[safe_label].append(ent)

        for label, ent_list in entities_by_type.items():
            entity_query = f"""
            UNWIND $entities AS ent
            MERGE (e:Entity:`{label}` {{name: ent.name}})
            SET e.type = ent.type
            """
            driver.execute_query(entity_query, entities=ent_list, database_=db_name)
        logger.debug(f"{len(entities)} Entity düğümü ({len(entities_by_type)} farklı etiket türünde) MERGE edildi.")
        
        # D. Chunk MENTIONS Entity ilişkilerini yükle
        if mentions:
            mentions_query = """
            UNWIND $mentions AS m
            MATCH (c:Chunk {chunk_id: m.chunk_id})
            MATCH (e:Entity {name: m.entity_name})
            MERGE (c)-[:MENTIONS]->(e)
            """
            driver.execute_query(mentions_query, mentions=mentions, database_=db_name)
            logger.debug(f"{len(mentions)} MENTIONS ilişkisi MERGE edildi.")
            
        # E. Entity dinamik anlamsal ilişkilerini (DEVELOPED_BY, PART_OF, OCCURRED_IN vb.) yükle
        if relations:
            relations_by_type = defaultdict(list)
            for rel in relations:
                raw_rel = rel.get("type", "RELATED_TO")
                safe_rel_type = re.sub(r'[^A-Za-z0-9_]', '_', str(raw_rel).upper())
                safe_rel_type = re.sub(r'_+', '_', safe_rel_type).strip('_') or "RELATED_TO"
                relations_by_type[safe_rel_type].append(rel)

            for rel_type, rel_list in relations_by_type.items():
                relations_query = f"""
                UNWIND $relations AS rel
                MATCH (source:Entity {{name: rel.source}})
                MATCH (target:Entity {{name: rel.target}})
                MERGE (source)-[r:`{rel_type}`]->(target)
                SET r.chunk_ids = rel.chunk_ids, r.type = rel.type
                """
                driver.execute_query(relations_query, relations=rel_list, database_=db_name)
            logger.debug(f"{len(relations)} ilişki ({len(relations_by_type)} dinamik Cypher ilişki türünde) MERGE edildi.")
            
        elapsed = time.time() - start_time
        logger.info(f"Adım 5 Tamamlandı: Neo4j aktarımı başarılı. ({len(articles)} Doc, {len(chunks)} Chunk, {len(entities)} Entity, {len(relations)} Relation). Süre: {elapsed:.2f} saniye.")
        return True
        
    except Exception as e:
        logger.error(f"Neo4j aktarımı sırasında hata oluştu: {e}")
        return False
    finally:
        driver.close()

if __name__ == "__main__":
    config.setup_logging("DEBUG")
    load_to_neo4j()
