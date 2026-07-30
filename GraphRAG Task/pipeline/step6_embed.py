import json
import time
import logging
import sys
from pathlib import Path
from neo4j import GraphDatabase

# Proje dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger("GraphRAG.Step6")

def embed_chunks() -> bool:
    """
    Chunk metinlerini Gemini Embedding modeli ile vektörleştirir ve Neo4j'de native vector index oluşturur.
    
    Returns:
        bool: İşlemin başarı durumu.
    """
    start_time = time.time()
    logger.info("Adım 6 Başladı: Chunk metinleri embed ediliyor ve Neo4j Vector Index oluşturuluyor.")
    
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY bulunamadı!")
        return False
        
    if genai is None:
        logger.error("google-genai kütüphanesi yüklenemedi!")
        return False

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    
    if not config.CHUNKS_FILE.exists():
        logger.error(f"Chunk dosyası bulunamadı: {config.CHUNKS_FILE}")
        return False
        
    with open(config.CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    db_name = config.NEO4J_DATABASE
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    )
    
    embedded_count = 0
    dimensions = None
    
    try:
        for idx, chunk in enumerate(chunks):
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            
            # Embedding çağrısı (Exponential backoff)
            embedding_values = None
            delay = 1.5
            for attempt in range(3):
                try:
                    res = client.models.embed_content(
                        model=config.EMBEDDING_MODEL,
                        contents=text
                    )
                    if hasattr(res, 'embedding') and hasattr(res.embedding, 'values'):
                        embedding_values = list(res.embedding.values)
                    elif hasattr(res, 'embeddings') and len(res.embeddings) > 0:
                        embedding_values = list(res.embeddings[0].values)
                    if embedding_values:
                        break
                except Exception as e:
                    logger.warning(f"Embedding çağrısı deneme {attempt+1} başarısız ({chunk_id}): {e}")
                    time.sleep(delay)
                    delay *= 2
                    
            if not embedding_values:
                logger.error(f"Chunk {chunk_id} embed edilemedi, atlanıyor.")
                continue
                
            if dimensions is None:
                dimensions = len(embedding_values)
                
            # Neo4j'de chunk düğümüne embedding özelliğini yaz
            query = """
            MATCH (c:Chunk {chunk_id: $chunk_id})
            SET c.embedding = $embedding
            """
            driver.execute_query(query, chunk_id=chunk_id, embedding=embedding_values, database_=db_name)
            embedded_count += 1
            logger.debug(f"Chunk embed edildi ({idx+1}/{len(chunks)}): {chunk_id} -> {len(embedding_values)} boyutlu vektör.")

        # Native Neo4j Vector Index oluştur
        if dimensions:
            vector_index_query = f"""
            CREATE VECTOR INDEX `chunk_embeddings` IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {{
              indexConfig: {{
                `vector.similarity_function`: 'cosine',
                `vector.dimensions`: {dimensions}
              }}
            }}
            """
            driver.execute_query(vector_index_query, database_=db_name)
            logger.info(f"Neo4j Native Vector Index (`chunk_embeddings`, boyut: {dimensions}) oluşturuldu.")
            
        elapsed = time.time() - start_time
        logger.info(f"Adım 6 Tamamlandı: {embedded_count}/{len(chunks)} chunk embed edildi ve vektör indeksi güncellendi. Süre: {elapsed:.2f} saniye.")
        return True
        
    except Exception as e:
        logger.error(f"Embedding işlemi sırasında hata oluştu: {e}")
        return False
    finally:
        driver.close()

if __name__ == "__main__":
    config.setup_logging("DEBUG")
    embed_chunks()
