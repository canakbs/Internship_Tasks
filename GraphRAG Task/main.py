import argparse
import logging
import sys
from pathlib import Path

import config
from pipeline.step1_fetch_wikipedia import fetch_wikipedia_articles
from pipeline.step2_chunk import create_chunks
from pipeline.step3_extract_kg import extract_knowledge_graph
from pipeline.step4_resolve_entities import resolve_entities
from pipeline.step5_load_neo4j import load_to_neo4j, clear_neo4j_database
from pipeline.step6_embed import embed_chunks
from pipeline.step6b_communities import detect_and_summarize_communities
from pipeline.step7_query import ask_graph_rag

def main():
    parser = argparse.ArgumentParser(
        description="Wikipedia + Neo4j + Gemini ile Terminal Tabanlı GraphRAG Sistemi"
    )
    
    parser.add_argument(
        "--topic",
        type=str,
        default=config.DEFAULT_TOPIC,
        help=f"Wikipedia'dan çekilecek konu başlığı (varsayılan: {config.DEFAULT_TOPIC})"
    )
    parser.add_argument(
        "--articles",
        type=int,
        default=config.DEFAULT_ARTICLES_COUNT,
        help=f"Çekilecek makale sayısı (varsayılan: {config.DEFAULT_ARTICLES_COUNT})"
    )
    parser.add_argument(
        "--skip-communities",
        action="store_true",
        help="Hızlı test için topluluk tespiti ve özetleme adımını atla"
    )
    parser.add_argument(
        "--clear-db",
        action="store_true",
        help="Pipeline çalıştırmadan önce Neo4j veritabanını tamamen temizler (MATCH (n) DETACH DELETE n)"
    )
    parser.add_argument(
        "--ask",
        type=str,
        default=None,
        help="Veritabanına GraphRAG üzerinden soru sormak için kullanılır"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Loglama seviyesi (varsayılan: INFO)"
    )
    
    args = parser.parse_args()
    
    # Loglama sistemini kur
    logger = config.setup_logging(args.log_level)
    logger.info("=== GraphRAG Başlatılıyor ===")
    
    # Eğer --clear-db istendiyse veritabanını temizle
    if args.clear_db:
        clear_neo4j_database()

    # 1. Eğer sadece soru sorulduysa sorgu adımını çalıştır
    if args.ask:
        logger.info(f"Soru sorma modu aktif: '{args.ask}'")
        answer = ask_graph_rag(args.ask)
        logger.info("=== GraphRAG Yanıtı ===")
        logger.info(f"\n{answer}")
        return

    # 2. Tam Pipeline Çalıştırma
    logger.info(f"Pipeline Çalıştırılıyor | Konu: '{args.topic}' | Makale Sayısı: {args.articles}")
    
    # Adım 1: Wikipedia Makalelerini Çek
    articles = fetch_wikipedia_articles(topic=args.topic, num_articles=args.articles)
    if not articles:
        logger.error("Makaleler çekilemedi. Pipeline durduruldu.")
        sys.exit(1)
        
    # Adım 2: Paragraf Koruyarak Chunk'lara Böl
    chunks = create_chunks(articles=articles)
    if not chunks:
        logger.error("Chunk oluşturulamadı. Pipeline durduruldu.")
        sys.exit(1)
        
    # Adım 3: Gemini ile Entity + Relation Çıkarımı Yap
    extracted = extract_knowledge_graph(chunks=chunks)
    if not extracted:
        logger.error("Bilgi grafı çıkarılamadı. Pipeline durduruldu.")
        sys.exit(1)
        
    # Adım 4: Entity Resolution (Normalizasyon + Birleştirme)
    resolved_graph = resolve_entities(extracted_data=extracted)
    if not resolved_graph["entities"]:
        logger.error("Varlıklar birleştirilemedi. Pipeline durduruldu.")
        sys.exit(1)
        
    # Adım 5: Neo4j Veritabanına Aktar (MERGE - Idempotent)
    success = load_to_neo4j()
    if not success:
        logger.error("Neo4j aktarımı başarısız oldu. Pipeline durduruldu.")
        sys.exit(1)
        
    # Adım 6: Embed ve Neo4j Native Vector Index Oluştur
    success = embed_chunks()
    if not success:
        logger.error("Embedding işlemi başarısız oldu. Pipeline durduruldu.")
        sys.exit(1)
        
    # Adım 6b: Topluluk Tespiti (NetworkX Louvain) ve Özetleme
    if not args.skip_communities:
        success = detect_and_summarize_communities()
        if not success:
            logger.warning("Topluluk tespiti sırasında sorun oluştu, ancak pipeline devam ediyor.")
    else:
        logger.info("Topluluk tespiti adımı --skip-communities argümanı nedeniyle atlandı.")
        
    logger.info("=== GraphRAG Pipeline Başarıyla Tamamlandı! ===")
    logger.info("Soru sormak için: python main.py --ask \"sorunuzu buraya yazın\"")

if __name__ == "__main__":
    main()
