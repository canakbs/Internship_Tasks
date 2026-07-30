import json
import time
import logging
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

# Proje dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

logger = logging.getLogger("GraphRAG.Step3")

# Yapılandırılmış Çıktı için Pydantic Modelleri
class EntityModel(BaseModel):
    name: str = Field(description="Varlığın metindeki açık ve resmi adı (Örn: Alan Turing, Turing Testi, II. Dünya Savaşı, 1950, Bletchley Park)")
    type: str = Field(description="Varlık türü: Person, Organization, Location, Event, Concept, Technology, TimePeriod, Field")

class RelationModel(BaseModel):
    source: str = Field(description="İlişkideki kaynak varlığın adı")
    target: str = Field(description="İlişkideki hedef varlığın adı")
    type: str = Field(description="İlişki türü (Örn: DEVELOPED_BY, PART_OF, SUBFIELD_OF, OCCURRED_IN, PARTICIPATED_IN, HELD_IN, CREATED_BY, USED_IN)")

class KGExtractionResult(BaseModel):
    entities: List[EntityModel]
    relations: List[RelationModel]

def call_gemini_with_retry(client, prompt: str, schema, max_retries: int = 5) -> Optional[KGExtractionResult]:
    """
    Gemini API çağrısını üstel geri çekilme (exponential backoff) ile güvenli şekilde gerçekleştirir.
    Rate limit (429) hatalarında API'nin önerdiği süreyi bekler.
    """
    delay = 15.0
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=config.LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.1
                )
            )
            # Yapılandırılmış veriyi al veya text'ten json parse et
            if hasattr(response, 'parsed') and response.parsed is not None:
                return response.parsed
            elif response.text:
                data = json.loads(response.text)
                return KGExtractionResult(**data)
        except Exception as e:
            error_str = str(e)
            logger.warning(f"Gemini API çağrısı deneme {attempt + 1}/{max_retries} başarısız: {e}")
            if attempt == max_retries - 1:
                logger.error("Maksimum yeniden deneme sayısına ulaşıldı. Bu chunk atlanıyor.")
                return None
            # Rate limit (429) hatası ise API'nin önerdiği süreyi bekle
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait_time = max(delay, 45.0)
                logger.info(f"Rate limit aşıldı. {wait_time:.0f} saniye bekleniyor...")
                time.sleep(wait_time)
            else:
                time.sleep(delay)
            delay = min(delay * 2, 120.0)
    return None

def extract_knowledge_graph(chunks: list[dict] = None) -> list[dict]:
    """
    Her metin parçası (chunk) için Gemini 3.6 Flash ile varlık ve ilişki çıkarımı yapar.
    
    Args:
        chunks (list[dict], optional): Chunk listesi. Verilmezse data/chunks.json okunur.
        
    Returns:
        list[dict]: Çıkarılan varlık ve ilişkileri içeren liste.
    """
    start_time = time.time()
    logger.info("Adım 3 Başladı: Gemini 3.6 Flash ile Bilgi Grafı (Entity & Relation) çıkarılıyor.")
    
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY ortam değişkeni bulunamadı! İşlem durduruluyor.")
        return []
        
    if genai is None:
        logger.error("google-genai kütüphanesi yüklenemedi!")
        return []

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    
    if chunks is None:
        if not config.CHUNKS_FILE.exists():
            logger.error(f"Chunk dosyası bulunamadı: {config.CHUNKS_FILE}")
            return []
        with open(config.CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            
    extracted_data = []
    total_entities_count = 0
    total_relations_count = 0
    
    prompt_template = """
Aşağıdaki metni analiz et ve metinde geçen belirgin varlıkları (Entity) ve bu varlıklar arasındaki anlamlı ilişkileri (Relation) çıkar.

Metin:
"{text}"

Yönergeler:
- Varlık isimlerini açık, kısa ve resmi biçimde tanımla (Örn: "Alan Turing", "II. Dünya Savaşı", "Enigma Şifresi", "Bletchley Park", "1950").
- Sadece genel kavramları değil; metindeki Olaylar (Event), Kişiler (Person), Tarihler/Zamanlar (TimePeriod), Kurumlar (Organization), Konumlar (Location) ve Teknolojileri de belirgin varlık düğümleri olarak çıkar.
- Varlık türlerini (type) şu listeden seç: [Person, Organization, Location, Event, Concept, Technology, TimePeriod, Field]
- İlişki kaynak (source) ve hedef (target) isimlerinin varlık listesindeki isimlerle birebir aynı olmasını sağla.
- İlişki türlerini (type) büyük harfli ve alt çizgili biçimde yaz (Örn: DEVELOPED_BY, PART_OF, SUBFIELD_OF, OCCURRED_IN, PARTICIPATED_IN, HELD_IN, CREATED_BY, USED_IN).
"""

    for idx, chunk in enumerate(chunks):
        chunk_id = chunk["chunk_id"]
        text = chunk["text"]
        title = chunk["article_title"]
        
        prompt = prompt_template.format(text=text)
        result = call_gemini_with_retry(client, prompt, KGExtractionResult)
        
        chunk_entities = []
        chunk_relations = []
        
        if result:
            chunk_entities = [e.model_dump() for e in result.entities]
            chunk_relations = [r.model_dump() for r in result.relations]
            
        total_entities_count += len(chunk_entities)
        total_relations_count += len(chunk_relations)
        
        extracted_data.append({
            "chunk_id": chunk_id,
            "article_title": title,
            "entities": chunk_entities,
            "relations": chunk_relations
        })
        
        logger.debug(f"Chunk processed ({idx+1}/{len(chunks)}): {chunk_id} -> {len(chunk_entities)} varlık, {len(chunk_relations)} ilişki çıkarıldı.")
        
        # Free tier rate limit: dakikada 5 istek. Her istek arası ~13 sn bekle.
        if idx < len(chunks) - 1:
            logger.debug(f"Rate limit koruması: 13 saniye bekleniyor ({idx+1}/{len(chunks)})...")
            time.sleep(13)

    # Çıktıyı kaydet
    with open(config.EXTRACTED_FILE, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=2)
        
    elapsed = time.time() - start_time
    logger.info(f"Adım 3 Tamamlandı: {len(chunks)} chunk işlendi. Toplam {total_entities_count} varlık ve {total_relations_count} ilişki çıkarıldı. Süre: {elapsed:.2f} saniye.")
    
    return extracted_data

if __name__ == "__main__":
    config.setup_logging("DEBUG")
    extract_knowledge_graph()
