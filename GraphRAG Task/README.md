# Wikipedia + Neo4j + Gemini ile Terminal Tabanlı GraphRAG

Bu proje, Türkçe Wikipedia makalelerinden bilgi grafiği (Knowledge Graph) ve vektör indeksleri oluşturup bunları Neo4j üzerinde saklayan, Google Gemini API desteğiyle hem yerel (spesifik varlıklar ve doğrudan ilişkiler) hem küresel (genel tema ve korpus özeti) sorulara yanıt verebilen terminal tabanlı bir GraphRAG sistemidir.

---

## 💡 Topluluk Tespiti ve Dinamik Topluluk Seçimi Nedir?

Geleneksel RAG sistemleri yalnızca sorguyla doğrudan benzer metin parçalarını (vektör araması) bulabilirken; büyük korpusların "ana temaları nelerdir?", "bu belgelerin genel özeti nedir?" gibi **küresel (global)** sorularında yetersiz kalır. GraphRAG mimarisinde, Neo4j üzerindeki varlıklar arasındaki ilişkilerden bir graf ağı inşa edilir ve Python NetworkX (Louvain kümeleme) algoritmasıyla birbirleriyle sıkı ilişkili varlıklar **topluluklar (communities)** olarak gruplanır. Her topluluğun içerdiği kavramlar ve metinler Google Gemini 3.6 Flash ile 2-3 cümlelik özlü tematik özetlere dönüştürülür.

Sorgu aşamasında **Dinamik Topluluk Seçimi (Dynamic k)** mekanizması devreye girer. Kullanıcının sorusu tüm topluluk özetlerine karşı değerlendirilerek Gemini tarafından 0 ile 100 arasında bir alaka puanına tabi tutulur. Sabit sayıda topluluk seçmek yerine, sadece eşik değeri (örn. >=50) geçen alakalı topluluk özetleri sorgu bağlamına dahil edilir. Bu sayede hem spesifik detaylar yerel vektör ve graf genişletmesiyle yakalanır hem de korpusun yüksek seviyeli tematik özeti dinamik olarak yanıt bağlamına eklenir.

---

## 🛠️ Kurulum

### 1. Gereksinimleri Yükleme
Python 3.11+ ortamında bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenlerini Hazırlama
`.env.example` dosyasını kopyalayarak `.env` dosyası oluşturun ve Neo4j ile Gemini API bilgilerinizi doldurun:
```bash
cp .env.example .env
```

`.env` dosya içeriği örneği:
```env
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password
NEO4J_DATABASE=neo4j
GEMINI_API_KEY=your-gemini-api-key
```

---

## 🚀 Çalıştırma

### 1. Varsayılan Pipeline Çalıştırma
"Yapay Zeka" konusunda 15 makaleyi çeker, parçalar, varlık/ilişki çıkarımı yapar, Neo4j'ye yükler, embed eder ve topluluk özetlerini oluşturur:
```bash
python main.py
```

### 2. Belirli Bir Konu ve Makale Sayısıyla Çalıştırma
```bash
python main.py --topic "Yapay zeka" --articles 15
```

### 3. Topluluk Adımını Atlayarak Hızlı Test
```bash
python main.py --skip-communities
```

### 4. GraphRAG ile Soru Sorma (Yerel + Küresel Bağlamlı)
```bash
python main.py --ask "Yapay zekanın tarihsel gelişimi ve ana temaları nelerdir?"
```

### 5. Detaylı (DEBUG) Log Seviyesi ile Soru Sorma
```bash
python main.py --ask "Alan Turing yapay zekaya nasıl katkıda bulunmuştur?" --log-level DEBUG
```

---

## 📁 Proje Dosya Yapısı

```
GraphRAG Task/
├── README.md                      -> Proje kılavuzu ve teknik açıklamalar
├── requirements.txt               -> Python kütüphane bağımlılıkları
├── .env.example                   -> Örnek ortam değişkenleri şablonu
├── config.py                      -> Yapılandırma sabitleri, yollar ve logging ayarları
├── main.py                        -> CLI arayüzü (argparse) ve orkestrasyon
└── pipeline/
    ├── step1_fetch_wikipedia.py   -> MediaWiki REST/Action API ile makale çekimi
    ├── step2_chunk.py             -> Paragraf korumalı, örtüşmeli metin bölme
    ├── step3_extract_kg.py        -> Gemini 3.6 Flash ile Pydantic bazlı varlık ve ilişki çıkarımı
    ├── step4_resolve_entities.py  -> Entity resolution (normalizasyon + fuzzy eşleşme)
    ├── step5_load_neo4j.py        -> Parametreli Cypher sorguları ile Neo4j'ye MERGE etme
    ├── step6_embed.py             -> Chunk metinlerini embed etme ve Neo4j Native Vector Index
    ├── step6b_communities.py      -> NetworkX Louvain topluluk tespiti + Gemini özetleme
    └── step7_query.py             -> Yerel (Vector + 1-hop Graph) ve Küresel (Dinamik Topluluk) GraphRAG sorgusu
```
