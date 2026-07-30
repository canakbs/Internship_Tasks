import json
import time
import logging
import hashlib
import sys
from pathlib import Path

# Proje dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger("GraphRAG.Step2")

def chunk_text(text: str, target_size: int = 1000, overlap_size: int = 150) -> list[str]:
    """
    Metni paragrafları bölmeyerek hedef boyuta ulaşacak şekilde ve örtüşmeli olarak parçalar.
    
    Args:
        text (str): Parçalanacak metin.
        target_size (int): Parça başına hedef karakter sayısı.
        overlap_size (int): Örtüşme (overlap) karakter sayısı.
        
    Returns:
        list[str]: Oluşturulan metin parçalarının listesi.
    """
    # Paragraflara ayır
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []
        
    chunks = []
    current_chunk = []
    current_length = 0
    
    for p in paragraphs:
        # Eğer paragrafın kendisi hedef boyuttan çok büyükse, onu cümle bazında ayır
        if len(p) > target_size * 1.5:
            sentences = [s.strip() + "." for s in p.split(". ") if s.strip()]
            for s in sentences:
                if current_length + len(s) > target_size and current_chunk:
                    chunks.append("\n".join(current_chunk))
                    # Overlap oluştur
                    overlap_text = "\n".join(current_chunk)
                    if len(overlap_text) > overlap_size:
                        overlap_text = overlap_text[-overlap_size:]
                    current_chunk = [overlap_text, s] if overlap_text else [s]
                    current_length = sum(len(x) for x in current_chunk)
                else:
                    current_chunk.append(s)
                    current_length += len(s)
        else:
            if current_length + len(p) > target_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                # Overlap oluştur
                overlap_text = "\n".join(current_chunk)
                if len(overlap_text) > overlap_size:
                    overlap_text = overlap_text[-overlap_size:]
                current_chunk = [overlap_text, p] if overlap_text else [p]
                current_length = sum(len(x) for x in current_chunk)
            else:
                current_chunk.append(p)
                current_length += len(p)
                
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks

def create_chunks(articles: list[dict] = None) -> list[dict]:
    """
    Makaleleri okur, parçalar ve data/chunks.json dosyasına kaydeder.
    
    Args:
        articles (list[dict], optional): Makale listesi. Verilmezse data/articles.json dosyasından okunur.
        
    Returns:
        list[dict]: Oluşturulan chunk nesnelerinin listesi.
    """
    start_time = time.time()
    logger.info("Adım 2 Başladı: Makaleler paragraf korumalı chunk'lara bölünüyor.")
    
    if articles is None:
        if not config.ARTICLES_FILE.exists():
            logger.error(f"Makale dosyası bulunamadı: {config.ARTICLES_FILE}")
            return []
        with open(config.ARTICLES_FILE, "r", encoding="utf-8") as f:
            articles = json.load(f)
            
    all_chunks = []
    for article in articles:
        title = article.get("title", "")
        content = article.get("content", "")
        
        raw_chunks = chunk_text(content, target_size=1000, overlap_size=150)
        
        for idx, chunk_str in enumerate(raw_chunks):
            # Tekil chunk_id üretimi
            hash_id = hashlib.md5(f"{title}_{idx}_{chunk_str[:30]}".encode('utf-8')).hexdigest()[:8]
            chunk_id = f"chunk_{hash_id}"
            
            chunk_obj = {
                "chunk_id": chunk_id,
                "article_title": title,
                "text": chunk_str
            }
            all_chunks.append(chunk_obj)
            logger.debug(f"Chunk oluşturuldu: {chunk_id} | Makale: '{title}' | Karakter: {len(chunk_str)}")
            
    # Sonuçları JSON dosyasına kaydet
    with open(config.CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        
    elapsed = time.time() - start_time
    avg_len = sum(len(c["text"]) for c in all_chunks) / len(all_chunks) if all_chunks else 0
    logger.info(f"Adım 2 Tamamlandı: {len(articles)} makaleden toplam {len(all_chunks)} chunk üretildi (Ortalama uzunluk: {avg_len:.0f} karakter). Süre: {elapsed:.2f} saniye.")
    
    return all_chunks

if __name__ == "__main__":
    config.setup_logging("DEBUG")
    create_chunks()
