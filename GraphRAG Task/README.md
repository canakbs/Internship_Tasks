# Wikipedia + Neo4j + Gemini ile Flask Tabanlı GraphRAG

Bu proje, Türkçe Wikipedia makalelerinden bilgi grafiği (Knowledge Graph) ve vektör indeksleri oluşturup bunları Neo4j üzerinde saklayan, Google Gemini API desteğiyle hem yerel (spesifik varlıklar ve doğrudan ilişkiler) hem küresel (genel tema ve korpus özeti) sorulara yanıt verebilen, modern bir **Flask Web Arayüzü** ile desteklenmiş GraphRAG sistemidir.

📑 **Detaylı Teknik Rapor:** Projenin detaylı mimarisi, veri işleme aşamaları, algoritma adımları, veri tabanı şeması ve test bulguları [GRAPHRAG_REPORT.md](./GRAPHRAG_REPORT.md) dosyasında kapsamlı olarak sunulmuştur.

---

## 🎯 Projenin Amacı ve Ne İşe Yarar?

Geleneksel Vektör Tabanlı RAG (Retrieval-Augmented Generation) sistemleri yalnızca metin benzerliğine dayanır ve karmaşık ilişkileri ya da belgelerin genel temalarını yakalamakta yetersiz kalır. Bu GraphRAG projesi, aşağıdaki yetenekleri sağlayarak bu kısıtlamaları aşar:

* **Otomatik Bilgi Grafiği (Knowledge Graph) Oluşturma**: Türkçe Wikipedia makalelerini çekerek LLM (Google Gemini) desteğiyle varlıkları (Entity) ve aralarındaki ilişkileri (Relation) otomatik tespit eder ve Neo4j graf veri tabanına kaydeder.
* **Hibrit Yerel (Local) Arama**: Vektör araması (Vector Search) ile Neo4j üzerindeki 1-hop graf komşuluğunu birleştirerek spesifik varlıklar hakkındaki sorulara eksiksiz yanıt sunar.
* **Topluluk Tespiti ile Küresel (Global) Arama**: Louvain kümeleme algoritması kullanarak veri tabanındaki ilişkili varlıkları "Topluluklar" halinde gruplar. Gemini ile bu topluluklara tematik özetler oluşturarak korpusun genel anlamını ve temalarını kapsayan küresel soruları yanıtlar.
* **Dinamik Topluluk Seçimi (Dynamic k)**: Sabit sayıda topluluk seçmek yerine kullanıcı sorgusuna en uygun tematik özetleri alaka puanına göre dinamik olarak filtreler.
* **İnteraktif Web Arayüzü & Dashboard**: Flask, Server-Sent Events (SSE) ve arayüz bileşenleri ile geliştirilen uygulama sayesinde kullanıcılar canlı yanıt akışı, işlem logları ve Neo4j graf istatistiklerini anlık takip edebilir.

---

## 💡 Topluluk Tespiti ve Dinamik Topluluk Seçimi Nedir?

Geleneksel RAG sistemleri yalnızca sorguyla doğrudan benzer metin parçalarını (vektör araması) bulabilirken; büyük korpusların "ana temaları nelerdir?", "bu belgelerin genel özeti nedir?" gibi **küresel (global)** sorularında yetersiz kalır. GraphRAG mimarisinde, Neo4j üzerindeki varlıklar arasındaki ilişkilerden bir graf ağı inşa edilir ve Python NetworkX (Louvain kümeleme) algoritmasıyla birbirleriyle sıkı ilişkili varlıklar **topluluklar (communities)** olarak gruplanır. Her topluluğun içerdiği kavramlar ve metinler Google Gemini ile özlü tematik özetlere dönüştürülür.

Sorgu aşamasında **Dinamik Topluluk Seçimi (Dynamic k)** mekanizması devreye girer. Kullanıcının sorusu tüm topluluk özetlerine karşı değerlendirilerek Gemini tarafından alaka puanına tabi tutulur. Sabit sayıda topluluk seçmek yerine, sadece eşik değeri geçen alakalı topluluk özetleri sorgu bağlamına dahil edilir. Bu sayede hem spesifik detaylar yerel vektör ve graf genişletmesiyle yakalanır hem de korpusun yüksek seviyeli tematik özeti dinamik olarak yanıt bağlamına eklenir.

---

## 🛠️ Hızlı Bakış (Çalıştırma Özeti)

Gereksinimler yüklendikten ve `.env` yapılandırması sağlandıktan sonra proje hem web arayüzü hem de CLI pipeline üzerinden çalıştırılabilir:

* **Web Arayüzünü Başlatma**: `python app.py` (Tarayıcı: `http://localhost:5000`)
* **Veri Pipeline Çalıştırma**: `python main.py --topic "Yapay zeka" --articles 15`
* **CLI Soru-Cevap**: `python main.py --ask "Yapay zekanın gelişimi ve ana temaları nelerdir?"`

---

## 📁 Proje Dosya Yapısı

```
GraphRAG Task/
├── GRAPHRAG_REPORT.md              -> Detaylı proje raporu ve teknik analizler
├── README.md                       -> Proje özeti ve temel bilgilendirme
├── requirements.txt                -> Python kütüphane bağımlılıkları
├── .env.example                    -> Örnek ortam değişkenleri şablonu
├── config.py                       -> Yapılandırma sabitleri ve ayarlar
├── main.py                         -> CLI pipeline orkestrasyonu ve soru-cevap hattı
├── app.py                          -> Flask web uygulaması sunucusu
├── templates/                      -> HTML arayüz şablonları
├── static/                         -> CSS ve JavaScript dosyaları
└── pipeline/                       -> Veri çekme, KG çıkarma, Neo4j yükleme ve sorgulama adımları
```
