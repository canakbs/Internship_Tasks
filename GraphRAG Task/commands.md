# GraphRAG Terminal Komutları Rehberi

Bu dosya, projeyi kurmak, pipeline'ı çalıştırmak, tekil adımları test etmek ve GraphRAG sistemine soru sormak için kullanabileceğiniz tüm terminal komutlarını içerir.

---

## 1. ⚙️ Kurulum Komutları

```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# (Varsa) .env.example dosyasından .env oluşturma
copy .env.example .env
```

---

## 2. 🚀 Ana Pipeline Çalıştırma Komutları

```bash
# 1. Varsayılan Pipeline (Konu: "Yapay Zeka", 15 Makale, Tüm Adımlar)
python main.py

# 2. Neo4j Veritabanını Temizleyerek Sıfırdan Çalıştırma
python main.py --clear-db

# 3. Özel Konu ve Makale Sayısı İle Pipeline Çalıştırma
python main.py --topic "Yapay zeka" --articles 15

# 3. Farklı Bir Konu Çalıştırma (Örn: Derin Öğrenme)
python main.py --topic "Derin öğrenme" --articles 10

# 4. Hızlı Test (Topluluk Tespiti Adımını Atlayarak)
python main.py --skip-communities

# 5. Detaylı (DEBUG) Log Seviyesi İle Tüm Pipeline'ı Çalıştırma
python main.py --log-level DEBUG
```

---

## 3. ❓ GraphRAG Soru Sorma Komutları

```bash
# 1. Genel Soru Sorma
python main.py --ask "Yapay zekanın tarihsel gelişimi ve ana temaları nelerdir?"

# 2. Spesifik Varlık/Kavram Sorusu
python main.py --ask "Alan Turing yapay zekaya nasıl katkıda bulunmuştur?"

# 3. Detaylı Loglar (INFO) İle Soru Sorma (Seçilen Toplulukları Görmek İçin)
python main.py --ask "Makine öğrenimi ve derin öğrenme arasındaki farklar nelerdir?" --log-level INFO

# 4. Hata Ayıklama (DEBUG) Logları İle Soru Sorma
python main.py --ask "Yapay zekanın kullanım alanları nelerdir?" --log-level DEBUG
```

---

## 4. 🧩 Adım Adım (Tekil Script) Çalıştırma Komutları

Pipeline içindeki her adım bağımsız bir script olarak da çalıştırılabilir:

```bash
# Adım 1: Wikipedia Makalelerini Çek (data/articles.json)
python pipeline/step1_fetch_wikipedia.py

# Adım 2: Paragraf Koruyarak Chunk'lara Böl (data/chunks.json)
python pipeline/step2_chunk.py

# Adım 3: Gemini 3.6 Flash ile Varlık/İlişki Çıkarımı (data/extracted.json)
python pipeline/step3_extract_kg.py

# Adım 4: Entity Resolution / Normalizasyon (data/resolved_graph.json)
python pipeline/step4_resolve_entities.py

# Adım 5: Neo4j Veritabanına Yükle (Cypher MERGE)
python pipeline/step5_load_neo4j.py

# Adım 6: Metinleri Embed Et ve Neo4j Vector Index Oluştur
python pipeline/step6_embed.py

# Adım 6b: NetworkX Louvain Topluluk Tespiti ve Özetleme
python pipeline/step6b_communities.py

# Adım 7: GraphRAG Sorgusu Çalıştır ve Yanıt Üret
python pipeline/step7_query.py
```

---

## 5. 🛠️ Kod Kontrol ve Doğrulama Komutları

```bash
# Tüm Python dosyalarının sözdizimini (syntax) doğrulama
python -m py_compile config.py main.py pipeline/*.py
```
