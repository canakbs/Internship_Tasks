import json
import time
import logging
import requests
import sys
from pathlib import Path

# Proje dizinini sys.path'e ekle (standalone çalıştırılabilmesi için)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger("GraphRAG.Step1")

def fetch_wikipedia_articles(topic: str = config.DEFAULT_TOPIC, num_articles: int = config.DEFAULT_ARTICLES_COUNT) -> list[dict]:
    """
    MediaWiki REST/Action API kullanarak verilen konuyla ilgili Wikipedia makalelerini çeker.
    
    Args:
        topic (str): Aranacak konu başlığı.
        num_articles (int): Çekilecek maksimum makale sayısı.
        
    Returns:
        list[dict]: Makale başlığı, URL ve içerik bilgilerini içeren liste.
    """
    start_time = time.time()
    logger.info(f"Adım 1 Başladı: Wikipedia'dan '{topic}' konusunda {num_articles} makale çekiliyor.")
    
    api_url = "https://tr.wikipedia.org/w/api.php"
    headers = {
        "User-Agent": "GraphRAG-Project/1.0 (Contact: local-developer)"
    }
    
    # 1. Konu araması yaparak ilgili makale başlıklarını al
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": topic,
        "srlimit": num_articles,
        "format": "json"
    }
    
    try:
        response = requests.get(api_url, params=search_params, headers=headers, timeout=15)
        response.raise_for_status()
        search_results = response.json().get("query", {}).get("search", [])
    except Exception as e:
        logger.error(f"Wikipedia arama sorgusu başarısız oldu: {e}")
        return []
        
    page_ids = [str(item["pageid"]) for item in search_results]
    if not page_ids:
        logger.warning(f"'{topic}' konusunda makale bulunamadı.")
        return []
        
    # 2. Sayfa içeriklerini (düz metin) ve URL bilgilerini çek
    #    exlimit ile birden fazla sayfanın extract'ını tek istekte al
    #    Sayfalama (continue) desteği ve 429 retry ile tüm sayfaları çek
    pages = {}
    continue_params = {}
    
    while True:
        content_params = {
            "action": "query",
            "prop": "extracts|info",
            "explaintext": 1,
            "exlimit": 20,
            "inprop": "url",
            "pageids": "|".join(page_ids),
            "format": "json",
            **continue_params
        }
        
        # Wikipedia 429 hatası için retry mekanizması
        wiki_success = False
        for wiki_attempt in range(3):
            try:
                response = requests.get(api_url, params=content_params, headers=headers, timeout=30)
                if response.status_code == 429:
                    wait = 5 * (wiki_attempt + 1)
                    logger.warning(f"Wikipedia 429 rate limit. {wait} saniye bekleniyor (deneme {wiki_attempt+1}/3)...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                wiki_success = True
                break
            except requests.exceptions.HTTPError as e:
                if "429" in str(e):
                    wait = 5 * (wiki_attempt + 1)
                    logger.warning(f"Wikipedia 429 rate limit. {wait} saniye bekleniyor (deneme {wiki_attempt+1}/3)...")
                    time.sleep(wait)
                else:
                    logger.error(f"Wikipedia içerik çekme sorgusu başarısız oldu: {e}")
                    return []
            except Exception as e:
                logger.error(f"Wikipedia içerik çekme sorgusu başarısız oldu: {e}")
                return []
        
        if not wiki_success:
            logger.error("Wikipedia rate limit aşılamadı. Mevcut verilerle devam ediliyor.")
            break
            
        data = response.json()
        batch_pages = data.get("query", {}).get("pages", {})
        # Sayfa verilerini birleştir
        for pid, pdata in batch_pages.items():
            if pid not in pages or (not pages[pid].get("extract") and pdata.get("extract")):
                pages[pid] = pdata
            elif pdata.get("extract") and pid in pages:
                pages[pid] = pdata
                
        # Devam parametresi varsa sonraki sayfaya geç
        if "continue" in data:
            continue_params = data["continue"]
            time.sleep(2)  # Sayfalar arası bekleme
        else:
            break
        
    articles = []
    for page_id, page_data in pages.items():
        title = page_data.get("title", "")
        content = page_data.get("extract", "").strip()
        url = page_data.get("fullurl", f"https://tr.wikipedia.org/wiki/{title.replace(' ', '_')}")
        if url:
            import urllib.parse
            url = urllib.parse.quote(urllib.parse.unquote(url), safe=":/")
        
        # İçeriği boş veya çok kısa olan sayfaları atla
        if content and len(content) > 100:
            articles.append({
                "title": title,
                "url": url,
                "content": content
            })
            logger.debug(f"Makale çekildi: '{title}' ({len(content)} karakter) - {url}")
            
    # Sonuçları JSON dosyasına kaydet
    config.ARTICLES_FILE.parent.mkdir(exist_ok=True)
    with open(config.ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
        
    elapsed = time.time() - start_time
    logger.info(f"Adım 1 Tamamlandı: {len(articles)} makale başarıyla çekildi ve '{config.ARTICLES_FILE}' dosyasına kaydedildi. Süre: {elapsed:.2f} saniye.")
    
    return articles

if __name__ == "__main__":
    config.setup_logging("DEBUG")
    fetch_wikipedia_articles()
