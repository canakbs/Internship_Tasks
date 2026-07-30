import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# Proje dizin yolları
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Çıktı dosya yolları
ARTICLES_FILE = DATA_DIR / "articles.json"
CHUNKS_FILE = DATA_DIR / "chunks.json"
EXTRACTED_FILE = DATA_DIR / "extracted.json"
RESOLVED_GRAPH_FILE = DATA_DIR / "resolved_graph.json"

# Konfigürasyon ve Varsayılan Değerler
DEFAULT_TOPIC = "Yapay Zeka"
DEFAULT_ARTICLES_COUNT = 15

# Gemini Model Tanımları
LLM_MODEL = "gemini-3.5-flash-lite"
EMBEDDING_MODEL = "gemini-embedding-001"

# Neo4j Bağlantı Ayarları
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Proje genelinde kullanılacak standart loglama ayarlarını yapılandırır."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Kök loglayıcıyı temizle ve yapılandır
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format
    )
    
    logger = logging.getLogger("GraphRAG")
    logger.setLevel(numeric_level)
    return logger
