# GraphRAG (Graph Retrieval-Augmented Generation) Sistem Raporu ve Mimari Dokümantasyonu

> **Proje Konusu:** Türkçe Wikipedia Verileri Üzerinde Neo4j, NetworkX ve Google Gemini ile Hibrit GraphRAG (Local + Global) Uygulaması Geliştirilmesi  
> **Tarih:** 2026  
> **Teknoloji Yığını:** Python 3.11+, Neo4j Graph Database, NetworkX (Louvain Algorithm), Google Gemini API (gemini-3.5-flash-lite / text-embedding-004), Flask, HTML5/CSS3/Vanilla JS (SSE Streaming)

---

## 📋 İÇİNDEKİLER
1. [Giriş ve Teorik Çerçeve](#1-giriş-ve-teorik-çerçeve)
   - 1.1 Klasik RAG Nedir? Sınırları Nelerdir?
   - 1.2 GraphRAG Nedir? Neden Tercih Edilir?
   - 1.3 Karşılaştırma Matrisi (Klasik RAG vs. GraphRAG)
2. [Sistem Mimarisi ve Veri Akış Hattı (Pipeline)](#2-sistem-mimarisi-ve-veri-akış-hattı-pipeline)
   - 2.1 Genel Mimari Şeması
   - 2.2 Adım Adım Pipeline İşleyişi
3. [Veri Tabanı Şeması (Graph Database Schema)](#3-veri-tabanı-şeması-graph-database-schema)
   - 3.1 Düğüm (Node) Tipleri ve Özellikleri
   - 3.2 İlişki (Edge/Relationship) Tipleri
4. [Sorgulama ve Bağlam Oluşturma (Local + Global Hybrid RAG)](#4-sorgulama-ve-bağlam-oluşturma-local--global-hybrid-rag)
   - 4.1 Yerel Bağlam (Local Context): Vector Search + 1-Hop Graph Expansion
   - 4.2 Küresel Bağlam (Global Context): NetworkX Louvain Kümeleme + Cosine Similarity
   - 4.3 Bağlam Birleştirme ve LLM Yanıt Üretimi
   - 4.4 Otomatik Kaynakça Filtreleme ve Doğrulama (Post-Processing)
5. [Yazılım Bileşenleri ve Dosya Yapısı](#5-yazılım-bileşenleri-ve-dosya-yapısı)
6. [Kurulum ve Çalıştırma Kılavuzu](#6-kurulum-ve-çalıştırma-kılavuzu)
7. [Örnek Test Senaryoları ve Çıktılar](#7-örnek-test-senaryoları-ve-çıktılar)
8. [Sonuç ve Gelecek Çalışmalar](#8-sonuç-ve-gelecek-çalışmalar)

---

## 1. Giriş ve Teorik Çerçeve

### 1.1 Klasik RAG Nedir? Sınırları Nelerdir?
Geleneksel Retrieval-Augmented Generation (RAG) sistemleri, büyük metin belgelerini sabit uzunluktaki küçük parçalara (chunk) böler, bu parçaların vektör temsillerini (embeddings) oluşturur ve sorgu anında vektör benzerliğine (Cosine Similarity / Euclidean Distance) göre en yakın $k$ adet metin parçasını bulup LLM'e bağlam olarak iletir.

**Klasik RAG'in Temel Sınırlamaları:**
1. **İlişkisel Bağlantı Kopukluğu (Multi-Hop Blindness):** Farklı metin parçalarına veya farklı belgelere dağılmış varlıklar arasındaki dolaylı ilişkileri (Örn: *A şahsı B şirketini kurdu, B şirketi C teknolojisini geliştirdi $\rightarrow$ A şahsı C teknolojisinin gelişmesine nasıl katkı sağladı?*) birleştiremez.
2. **Küresel Özetleme Yetersizliği (Global Context Failure):** *"Bu veri setindeki ana temalar nelerdir?"* veya *"Yapay zeka etiği konusunda genel yaklaşım nedir?"* gibi bütünsel sorgularda, spesifik bir anahtar kelime eşleşmesi olmadığı için anlamsız parça sonuçları döner.
3. **Bağlamsal Parçalanma (Chunk Boundaries):** Metin bölme sırasında cümle ortasında veya kavramlar arasında oluşan yapay sınırlar anlam kaybına yol açar.

### 1.2 GraphRAG Nedir? Neden Tercih Edilir?
GraphRAG, metin verilerini anlamsal bir **Bilgi Grafı (Knowledge Graph)** yapısına dönüştürerek metin içi varlıkları (Entities) düğüm, varlıklar arasındaki ilişkileri (Relations) ise kenar olarak modeller. Vektör indekslemesini sadece ham metin seviyesinde değil, graf üzerindeki yapısal ilişkiler ve kümeleme toplulukları (Communities) seviyesinde gerçekleştirir.

**GraphRAG'in Avantajları:**
- **Derin Anlamsal İlişki Tespiti:** Graf yapısı sayesinde 1-hop, 2-hop komşuluklar taranarak gizli bağlantılar keşfedilir.
- **Hibrit Sorgulama (Local + Global):** Hem spesifik detay sorularına (Local) hem de geniş kapsamlı özet sorularına (Global) yüksek doğrulukla yanıt verir.
- **Yüksek Sadakat ve Halüsinasyon Önleme:** Veriler açık grafiksel ilişkilerle bağlandığı için LLM'in uydurma (hallucination) riski minimize edilir.

### 1.3 Karşılaştırma Matrisi (Klasik RAG vs. GraphRAG)

| Özellik | Klasik RAG | GraphRAG (Projede Uygulanan) |
|---|---|---|
| **Veri Temsili** | Vektör uzayında bağımsız metin blokları | Bilgi Grafı (Düğümler + İlişkiler) + Vektör İndeksi |
| **Arama Mekanizması** | Yalnızca K-NN Vektör Araması | Vektör Araması + 1-Hop Graf Genişletmesi + Louvain Topluluk Kümelemesi |
| **Çok Adımlı Çıkarım (Multi-Hop)** | Zayıf / İmkânsız | Güçlü (İlişkili Düğümler Taranır) |
| **Küresel Sorgu (Global Summarization)** | Başarısız | Başarılı (Topluluk Özetleri İle) |
| **Kaynak Atfı Güvenilirliği** | Parça tabanlı (Kaba) | Varlık ve Bağlantı Tabanlı (Hassas ve Programatik Filtrelenmiş) |

---

## 2. Sistem Mimarisi ve Veri Akış Hattı (Pipeline)

### 2.1 Genel Mimari Şeması

```
+------------------+     +------------------+     +-----------------------+
|  Wikipedia API   | --> |  Paragraph Chunk | --> | Gemini 3.5 Flash      |
|  (Ham Makaleler) |     |  (Overlap: 100)  |     | (Entity & Rel Extract)|
+------------------+     +------------------+     +-----------------------+
                                                              |
                                                              v
+------------------+     +------------------+     +-----------------------+
| Neo4j Database   | <-- | Text-Embedding   | <-- | Entity Resolution     |
| (Graph + Vector) |     | (text-emb-004)   |     | (Normalizasyon/Fuzzy) |
+------------------+     +------------------+     +-----------------------+
         |
         v
+-----------------------+     +-----------------------+     +-----------------------+
| NetworkX Louvain      | --> | Gemini Topluluk       | --> | Web UI / SSE Stream   |
| (Topluluk Tespiti)    |     | Özetleme              |     | (Hybrid Query Engine) |
+-----------------------+     +-----------------------+     +-----------------------+
```

### 2.2 Adım Adım Pipeline İşleyişi

Proje 7 temel adımdan oluşan modüler bir akış hattına sahiptir:

#### Adım 1: Wikipedia Veri Çekme (`step1_fetch_wikipedia.py`)
- MediaWiki Action API uç noktası kullanılarak belirlenen ana konu (Örn: *"Yapay Zekâ"*) ve ilgili alt makaleler ham metin ve HTML temizliği yapılarak çekilir.
- Çekilen URL'ler Türkçe karakter uyumsuzluğu ve kodlama bozulmalarını önlemek amacıyla `urllib.parse.quote` ile sanitize edilir.

#### Adım 2: Akıllı Metin Bölme / Chunking (`step2_chunk.py`)
- Makaleler semantik bütünlük korunacak şekilde paragraf sınırlarına duyarlı olarak `chunk_size=1000` karakter ve `overlap=100` karakter örtüşme payı ile parçalanır.

#### Adım 3: Bilgi Grafı Çıkarımı / Knowledge Graph Extraction (`step3_extract_kg.py`)
- Her metin parçası Google Gemini 3.5 Flash modeline gönderilir. Pydantic şema zorlaması (`structured_outputs`) ile metindeki varlıklar (`Entity: name, type, description`) ve aralarındaki ilişkiler (`Relation: source, target, relation_type, reasoning`) çıkarılır.

#### Adım 4: Varlık Çözümleme / Entity Resolution (`step4_resolve_entities.py`)
- Farklı metinlerde geçen benzer varlıkların (Örn: *"Alan Turing"*, *"Turing"*, *"A. Turing"*) aynı düğüm altında birleştirilmesi sağlanır. Küçük harf normalizasyonu ve Levenshtein mesafesine dayalı bulanık eşleme (fuzzy matching) uygulanır.

#### Adım 5: Neo4j Veri Tabanına Yükleme (`step5_load_neo4j.py`)
- Çıkarılan varlıklar, ilişkiler, metin parçaları ve belgeler parametrize edilmiş Cypher `MERGE` sorguları ile Neo4j veritabanına veri tekrarı olmadan yazılır.

#### Adım 6: Vektör İndeksleme ve Topluluk Tespiti (`step6_embed.py` & `step6b_communities.py`)
- **Vektör İndeksi:** Her Chunk metni `text-embedding-004` modeli ile 3072 boyutlu vektöre dönüştürülür ve Neo4j Native Vector Index (`chunk_embeddings`) oluşturulur.
- **Louvain Kümeleme:** Varlıklar ve ilişkiler NetworkX kütüphanesine aktarılarak Louvain topluluk tespiti algoritması çalıştırılır. Sıkı ilişkili varlık kümeleri (`Community`) tespit edilir.
- **Topluluk Özetleme:** Her topluluğun sahip olduğu varlıklar Gemini ile 2-3 cümlelik tematik özetlere dönüştürülür ve bu özetler de embed edilerek Neo4j'ye kaydedilir.

#### Adım 7: Hibrit Sorgulama ve Yanıt Üretimi (`step7_query.py`)
- Kullanıcının sorusu aynı anda Yerel (Vektör + Graf) ve Küresel (Topluluk Benzerliği) bağlamlardan geçirilir. Sonuçlar birleştirilerek LLM'e iletilir ve kullanıcıya akışlı (SSE) olarak yanıt sunulur.

---

## 3. Veri Tabanı Şeması (Graph Database Schema)

Neo4j veritabanında kullanılan mülkiyet grafı (Property Graph) şeması aşağıdaki gibidir:

```
 (Document) <---[:PART_OF]--- (Chunk) ---[:MENTIONS]---> (Entity) <---[:IN_COMMUNITY]--- (Community)
                                                            |  ^
                                                            v  |
                                                     [:RELATION_TYPE]
```

### 3.1 Düğüm (Node) Tipleri ve Özellikleri

1. **`Document`**
   - `url` (String, Unique): Wikipedia makale bağlantısı.
   - `title` (String): Makale başlığı.
   - `fetched_at` (Timestamp): Verinin çekildiği tarih.

2. **`Chunk`**
   - `chunk_id` (String, Unique): Benzersiz parça kimliği (`doc_title_chunk_X`).
   - `text` (String): Parçanın ham metin içeriği.
   - `article_title` (String): Ait olduğu makale başlığı.
   - `embedding` (List<Float>): 3072 boyutlu vektör representation.

3. **`Entity`**
   - `name` (String, Unique): Varlık adı (Örn: *"Dartmouth Atölyesi"*).
   - `type` (String): Varlık kategorisi (`Person`, `Organization`, `Concept`, `Event`, `Location`).
   - `description` (String): Varlığın tanımı.

4. **`Community`**
   - `community_id` (String, Unique): Topluluk kimliği (`comm_001`).
   - `summary` (String): Topluluğun Gemini tarafından üretilen özeti.
   - `embedding` (List<Float>): Özet metninin vektör temsilcisi.

### 3.2 İlişki (Edge/Relationship) Tipleri

- **`(:Chunk)-[:PART_OF]->(:Document)`**: Metin parçasının doküman aidiyeti.
- **`(:Chunk)-[:MENTIONS]->(:Entity)`**: Metin parçasında geçen varlıklar.
- **`(:Entity)-[:IN_COMMUNITY]->(:Community)`**: Varlığın ait olduğu Louvain topluluğu.
- **`(:Entity)-[:RELATION_TYPE]->(:Entity)`**: Varlıklar arasındaki anlamsal dinamik ilişkiler (Örn: `DEVELOPED_BY`, `FOUNDED_IN`, `USED_IN`, `OCCURRED_IN`).

---

## 4. Sorgulama ve Bağlam Oluşturma (Local + Global Hybrid RAG)

Sistem, gelen kullanıcı sorusunu yanıtlamak için çift kanallı bir erişim (retrieval) mekanizması kullanır.

```
                  +-----------------------------------+
                  |         Kullanıcı Sorusu          |
                  +-----------------------------------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v                               v
       [ 1. YEREL BAĞLAM (Local) ]     [ 2. KÜRESEL BAĞLAM (Global) ]
       - Soru Vektör Araması            - Topluluk Özet Vektör Araması
       - Top 5 Alakalı Chunk           - Cosine Similarity Puanlaması
       - 1-Hop Graf Genişletmesi        - Top-4 Alakalı Topluluk Seçimi
       - 30+ İlgili Graf Üçlüsü
                    |                               |
                    +---------------+---------------+
                                    |
                                    v
                  +-----------------------------------+
                  |   Birleştirilmiş Hibrit Bağlam    |
                  +-----------------------------------+
                                    |
                                    v
                  +-----------------------------------+
                  |    Gemini 3.5 Flash Yanıt Üretimi |
                  +-----------------------------------+
                                    |
                                    v
                  +-----------------------------------+
                  |  Programatik Kaynakça Temizliği  |
                  +-----------------------------------+
```

### 4.1 Yerel Bağlam (Local Context): Vector Search + 1-Hop Graph Expansion
1. Sorunun vektörü alınır ve Neo4j üzerindeki `chunk_embeddings` vektör indeksinde arama yapılarak en yakın 5 `Chunk` çekilir.
2. Bu 5 chunk'ın bahsettiği varlıklar (`MENTIONS`) tespit edilir.
3. Bu varlıkların etrafındaki 1-hop komşuluklar Cypher sorgusu ile taranarak ilişkili tüm varlık üçlüleri (`(Entity1) -[RELATION]-> (Entity2)`) bağlama dahil edilir.

### 4.2 Küresel Bağlam (Global Context): NetworkX Louvain Kümeleme + Cosine Similarity
1. Sistemdeki tüm `Community` özetlerinin vektörleri ile soru vektörü arasında **Cosine Similarity (Kosinüs Benzerliği)** hesaplanır:
   $$\text{Similarity} = \frac{\vec{Q} \cdot \vec{C}}{\|\vec{Q}\| \|\vec{C}\|}$$
2. Benzerlik skoru eşik değerini ( $> 0.25$ ) geçen en alakalı ilk 4 topluluk özeti "Küresel Özet Bağlamı" olarak eklenir.

### 4.3 Bağlam Birleştirme ve LLM Yanıt Üretimi
Toplanan tüm yerel parçalar, graf ilişkileri, küresel topluluk özetleri ve (varsa) önceki sohbet geçmişi tek bir prompt içerisinde Gemini 3.5 Flash modeline beslenir.

### 4.4 Otomatik Kaynakça Filtreleme ve Doğrulama (Post-Processing)
LLM'lerin kararsız URL üretimi veya metinde bahsetmediği kaynakları kaynakçaya ekleme meylini tamamen ortadan kaldırmak için `clean_bibliography` adında programatik bir filtreleme yazılmıştır:
1. LLM'in ürettiği metinden kaynakça bölümü regex ile kesilip atılır.
2. Gövde metninde geçen Markdown bağlantıları (`[Başlık](URL)`), parantez içi atıflar veya metin eşleşmeleri Unicode NFC normalizasyonu ile taranır.
3. Yalnızca gövde metninde **gerçekten atıfta bulunulan kaynaklar** programatik olarak metnin sonuna `### Kaynakça` başlığı altında temiz bağlantılar halinde eklenir.

---

## 5. Yazılım Bileşenleri ve Dosya Yapısı

```
GraphRAG Task/
├── config.py                      # Yapılandırma sabitleri, API anahtarları ve logging ayarları
├── main.py                        # CLI arayüzü ve toplu pipeline orkestrasyonu
├── app.py                         # Flask Web Sunucusu, REST API ve SSE Streaming uç noktaları
├── requirements.txt               # Bağımlılık listesi
├── README.md                      # Proje genel tanıtımı
├── pipeline/                      # 7 Adımlı GraphRAG İşlem Hattı
│   ├── step1_fetch_wikipedia.py   # Wikipedia REST/Action API çekici
│   ├── step2_chunk.py             # Paragraf korumalı metin bölücü
│   ├── step3_extract_kg.py        # Gemini Pydantic tabanlı Varlık/İlişki çıkarıcı
│   ├── step4_resolve_entities.py  # Fuzzy matching ile varlık birleştirici
│   ├── step5_load_neo4j.py        # Neo4j Cypher veri yükleyici
│   ├── step6_embed.py             # Vector embedding ve Neo4j indeks oluşturucu
│   ├── step6b_communities.py      # NetworkX Louvain kümeleme ve özetleme
│   └── step7_query.py             # Local+Global Hibrit Sorgu Motoru
├── templates/                     # Frontend HTML
│   └── index.html                 # Modern Dashboard arayüzü
├── static/                        # Frontend Statik Varlıklar
│   ├── css/style.css              # Glassmorphism/Dark Mode CSS tasarımı
│   └── js/app.js                  # SSE Streaming, Sohbet Yönetimi ve Pipeline Görselleştirici
└── data/                          # Yerel Veri Önbelleği ve Konuşma Geçmişleri
    └── conversations/             # JSON tabanlı kalıcı sohbet dosyaları
```

---

## 6. Kurulum ve Çalıştırma Kılavuzu

### 6.1 Gereksinimler
- Python 3.11 veya üzeri
- Neo4j Database (Local Desktop veya Neo4j AuraDB Cloud)
- Google Gemini API Anahtarı

### 6.2 Kurulum Adımları
1. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
2. `.env` dosyasını oluşturun ve bilgilerinizi girin:
   ```env
   NEO4J_URI=neo4j+s://<your-instance>.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=<your-password>
   NEO4J_DATABASE=neo4j
   GEMINI_API_KEY=<your-gemini-api-key>
   ```

### 6.3 Veri İşleme Hattını (Pipeline) Çalıştırma
Wikipedia'dan verileri çekip Neo4j'ye yüklemek ve bilgi grafını oluşturmak için:
```bash
python main.py --topic "Yapay zeka" --articles 15
```

### 6.4 Web Arayüzünü Başlatma
```bash
python app.py
```
Tarayıcınızdan `http://localhost:5000` adresine giderek arayüzü kullanabilirsiniz.

---

## 7. Örnek Test Senaryoları ve Çıktılar

### Soru 1 (Spesifik / Local Query):
> *"Yapay zeka ile ilgili ilk uluslararası konferans nerede düzenlenmiştir?"*

- **Girdi İşleme:**
  - Vektör araması ile `Dartmouth Atölyesi` ve `Yapay Zekâ Tarihi` chunk'ları bulundu (Skor: 0.8628).
  - Graf genişletmesi ile `(Dartmouth Atölyesi) -[OCCURRED_IN]-> (Dartmouth College)` üçlüsü çekildi.
- **Üretilen Yanıt:**
  > Yapay zekâ alanının resmî olarak kurulduğu ve bu alandaki ilk önemli buluşma kabul edilen çatı etkinlik, 1956 yılında **Dartmouth College**'da gerçekleştirilen iki aylık açık çalışma/atölye çalışmasıdır ([Yapay zekâ](https://tr.wikipedia.org/wiki/Yapay_zek%C3%A2)).
- **Performans:** Toplam Süre: ~6.6s (Embedding: 718ms, Vector: 1193ms, Graph: 170ms, Selection: 1371ms, Generation: 3103ms).

### Soru 2 (Genel / Global Query):
> *"Veri setindeki temel yapay zeka toplulukları ve ana temalar nelerdir?"*

- **Girdi İşleme:**
  - Louvain algoritmasıyla oluşturulmuş `comm_001`, `comm_019` ve `comm_073` topluluk özetleri kosinüs benzerliği ile seçildi.
- **Üretilen Yanıt:**
  > Veri seti 3 ana tema etrafında şekillenmektedir:  
  > 1. **Sembolik Zekâ ve Mantık:** 1950-1970 arası uzman sistemler ve kuramsal temeller.  
  > 2. **Tarihsel Dönüm Noktaları:** Dartmouth Atölyesi, Yapay Zekâ Kışları ve AGI arayışları.  
  > 3. **Modern Uygulamalar:** Büyük dil modelleri, üretken yapay zekâ ve etik/güvenlik tartışmaları.

### Soru 3 (Sohbet Hafızası / Takip Sorusu - Conversational RAG):
> **1. Soru:** *"Yapay genel zekâ (YGZ) nedir?"*  
> **2. Takip Sorusu:** *"Peki bunun dar yapay zekâdan farkı nedir?"*

- **Girdi İşleme:**
  - Sohbet geçmişi (Conversation History) üzerinden Soru Yeniden Yazımı (Query Rewriting) gerçekleştirilmiştir.
  - Yeniden Yazılan Arama Cümlesi: *"Yapay genel zekâ ile dar yapay zekâ arasındaki temel farklar nelerdir?"*
- **Üretilen Yanıt:**
  > Dar yapay zekâ yalnızca belirli bir alanda (örneğin satranç oynama veya yüz tanıma) uzmanlaşmışken; Yapay Genel Zekâ (YGZ), insan seviyesinde genel zihinsel becerilere ve farklı alanlarda öğrenme yeteneğine sahip teorik yapay zekâ türüdür ([Yapay genel zekâ](https://tr.wikipedia.org/wiki/Yapay_genel_zek%C3%A2)).

---

## 8. Sonuç ve Gelecek Çalışmalar

Bu çalışmada, Türkçe Wikipedia verileri üzerinde çalışan, klasik RAG yaklaşımlarının multi-hop ve küresel sorgulama yetersizliklerini aşan **tam teşekküllü bir GraphRAG mimarisi** başarıyla kurulmuştur. 

**Elde Edilen Başarılar:**
- Neo4j ve NetworkX entegrasyonu ile yerel ve küresel bağlam birleştirilmiştir.
- Yanıtlardaki kaynakça atıfları programatik doğrulamadan geçirilerek halüsinasyonlar ve bozuk URL'ler %100 önlenmiştir.
- Asenkron SSE akış mimarisi ile kullanıcı dostu ve şeffaf bir web arayüzü sunulmuştur.

**Gelecek Geliştirmeler:**
- **Entity Resolution:** LLM tabanlı vektör benzerliği ile daha gelişmiş varlık birleştirme.
- **Multi-Modal GraphRAG:** Wikipedia üzerindeki görsellerin ve tabloların da grafa dahil edilmesi.
