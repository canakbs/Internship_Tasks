import json
import time
import logging
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter
from difflib import SequenceMatcher

# Proje dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger("GraphRAG.Step4")

def tr_normalize(text: str) -> str:
    """
    Türkçe karakter ve büyük/küçük harf duyarlılığını dikkate alarak metni normalize eder.
    """
    text = text.strip()
    # Parantez içi ek açıklamaları temizle (Örn: "Yapay Zeka (YZ)" -> "Yapay Zeka")
    text = re.sub(r'\s*\([^)]*\)', '', text)
    
    # Türkçe harf dönüşümleri
    tr_map = str.maketrans({
        'I': 'ı', 'İ': 'i', 'Ç': 'ç', 'Ş': 'ş', 'Ğ': 'ğ', 'Ü': 'ü', 'Ö': 'ö',
        'Â': 'a', 'â': 'a', 'Î': 'i', 'î': 'i', 'Û': 'u', 'û': 'u'
    })
    return text.translate(tr_map).lower().strip()

def tr_title(text: str) -> str:
    """Metni düzgün Başlık Düzenine getirir."""
    text = text.strip()
    words = text.split()
    capitalized = []
    for w in words:
        if not w:
            continue
        first = w[0]
        rest = w[1:]
        if first == 'i':
            first = 'İ'
        elif first == 'ı':
            first = 'I'
        else:
            first = first.upper()
        capitalized.append(first + rest.lower())
    return " ".join(capitalized)

def sanitize_cypher_name(name: str) -> str:
    """Cypher etiket veya ilişki ismi için sadece harf, rakam ve alt çizgi karakterlerini tutar."""
    cleaned = re.sub(r'[^A-Za-z0-9_]', '_', name.strip())
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned.upper() if cleaned else "RELATED_TO"

def resolve_entities(extracted_data: list[dict] = None) -> dict:
    """
    Çıkarılan varlık ve ilişkileri normalize eder, benzer varlıkları birleştirir (entity resolution).
    
    Args:
        extracted_data (list[dict], optional): Step 3 çıktısı. Verilmezse data/extracted.json okunur.
        
    Returns:
        dict: "entities" ve "relations" listelerini içeren temizlenmiş bilgi grafı.
    """
    start_time = time.time()
    logger.info("Adım 4 Başladı: Varlık birleştirme ve normalizasyon (Entity Resolution) yapılıyor.")
    
    if extracted_data is None:
        if not config.EXTRACTED_FILE.exists():
            logger.error(f"Çıkarım dosyası bulunamadı: {config.EXTRACTED_FILE}")
            return {"entities": [], "relations": []}
        with open(config.EXTRACTED_FILE, "r", encoding="utf-8") as f:
            extracted_data = json.load(f)
            
    raw_entities = []
    canonical_map = {}  # normalized_name -> canonical_name
    entity_types = defaultdict(Counter)  # canonical_name -> Counter(types)
    
    # 1. Tüm varlıkları topla ve ilk normalizasyonu yap
    for item in extracted_data:
        for entity in item.get("entities", []):
            name = entity["name"].strip()
            etype = entity.get("type", "Concept").strip()
            if not name:
                continue
            norm_name = tr_normalize(name)
            raw_entities.append(name)
            
            # Varsayılan kanonik isim olarak title-cased halini belirle
            if norm_name not in canonical_map:
                canonical_map[norm_name] = tr_title(name)
            entity_types[canonical_map[norm_name]][etype] += 1

    # 2. Fuzzy Matching ile benzeyen varlık adlarını tek bir kanonik ada eşle
    unique_norm_names = list(canonical_map.keys())
    merged_count = 0
    
    for i in range(len(unique_norm_names)):
        norm1 = unique_norm_names[i]
        if norm1 not in canonical_map:
            continue
        canon1 = canonical_map[norm1]
        
        for j in range(i + 1, len(unique_norm_names)):
            norm2 = unique_norm_names[j]
            if norm2 not in canonical_map:
                continue
                
            # Metin benzerlik oranı
            ratio = SequenceMatcher(None, norm1, norm2).ratio()
            # Eğer benzerlik yüksekse (örn: >0.88) veya bir diğerinin alt kümesiyse birleştir
            if ratio >= 0.88 or (len(norm1) > 4 and len(norm2) > 4 and (norm1 in norm2 or norm2 in norm1)):
                canon2 = canonical_map[norm2]
                # Daha uzun/detaylı olanı veya daha sık geçeni kanonik seç
                chosen_canon = canon1 if len(canon1) >= len(canon2) else canon2
                canonical_map[norm1] = chosen_canon
                canonical_map[norm2] = chosen_canon
                merged_count += 1
                logger.debug(f"Varlıklar birleştirildi: '{canon1}' & '{canon2}' -> '{chosen_canon}'")

    # 3. Kanonik varlık listesini ve baskın tiplerini oluştur
    resolved_entities_dict = {}
    for norm_name, canon_name in canonical_map.items():
        if canon_name not in resolved_entities_dict:
            # En çok tekrar eden varlık tipini seç
            most_common_type = entity_types[canon_name].most_common(1)[0][0] if entity_types[canon_name] else "Concept"
            resolved_entities_dict[canon_name] = {
                "name": canon_name,
                "type": most_common_type
            }
            
    # 4. İlişkileri güncelle ve tekilleştir (chunk_ids listesi ekle)
    resolved_relations_dict = {}
    
    for item in extracted_data:
        chunk_id = item["chunk_id"]
        for rel in item.get("relations", []):
            src = rel.get("source", "").strip()
            tgt = rel.get("target", "").strip()
            rtype = sanitize_cypher_name(rel.get("type", "RELATED_TO"))
            
            if not src or not tgt:
                continue
                
            norm_src = tr_normalize(src)
            norm_tgt = tr_normalize(tgt)
            
            canon_src = canonical_map.get(norm_src, tr_title(src))
            canon_tgt = canonical_map.get(norm_tgt, tr_title(tgt))
            
            # Kendi kendine olan ilişkileri atla
            if canon_src == canon_tgt:
                continue
                
            rel_key = (canon_src, canon_tgt, rtype)
            if rel_key not in resolved_relations_dict:
                resolved_relations_dict[rel_key] = {
                    "source": canon_src,
                    "target": canon_tgt,
                    "type": rtype,
                    "chunk_ids": set()
                }
            resolved_relations_dict[rel_key]["chunk_ids"].add(chunk_id)
            
            # Bağlı varlıkların varlık listesinde olduğundan emin ol
            if canon_src not in resolved_entities_dict:
                resolved_entities_dict[canon_src] = {"name": canon_src, "type": "Concept"}
            if canon_tgt not in resolved_entities_dict:
                resolved_entities_dict[canon_tgt] = {"name": canon_tgt, "type": "Concept"}

    final_entities = list(resolved_entities_dict.values())
    final_relations = []
    for rel_val in resolved_relations_dict.values():
        rel_val["chunk_ids"] = list(rel_val["chunk_ids"])
        final_relations.append(rel_val)
        
    resolved_graph = {
        "entities": final_entities,
        "relations": final_relations
    }
    
    # Sonucu kaydet
    with open(config.RESOLVED_GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(resolved_graph, f, ensure_ascii=False, indent=2)
        
    elapsed = time.time() - start_time
    logger.info(f"Adım 4 Tamamlandı: {len(raw_entities)} ham varlık -> {len(final_entities)} tekil varlığa dönüştürüldü ({merged_count} birleştirme yapıldı). Toplam tekil ilişki: {len(final_relations)}. Süre: {elapsed:.2f} saniye.")
    
    return resolved_graph

if __name__ == "__main__":
    config.setup_logging("DEBUG")
    resolve_entities()
