# Internship Tasks (Staj Görevleri)

Bu depo, staj sürecim boyunca tamamladığım veri bilimi, veri görselleştirme, SQL ve GraphRAG tabanlı projeleri ve görevleri içermektedir.

---

## 📂 Depo İçeriği ve Görevler

### 1. 5 ML Projects (5 ML Projesi)
Bu bölüm 5 farklı makine öğrenmesi problemini ve bunların Knime & Python (Jupyter Notebook) çözümlerini içerir:
- **Proje 1: Classification (Sınıflandırma)**
  - *Not:* Bu projenin veri seti çok büyük olduğu için oluşturulan Knime iş akışı dosyası (`5 ML Project 1 Classification.knwf`, ~1.75 GB) GitHub dosya boyutu limitlerinden ötürü depoya eklenmemiş, yerel olarak tutulmuştur. Ancak sınıflandırma modeli başarıyla eğitilmiş ve Python/Knime raporları klasör altında sunulmuştur.
- **Proje 2: Clustering (Kümeleme)**
- **Proje 3: Regression (Regresyon)**
- **Proje 4: Association Rule Mining (Birliktelik Kuralları Çıkarımı)**
- **Proje 5: Anomaly Detection (Anomali Tespiti)**

### 2. Data Visualization Task (Veri Görselleştirme Görevi)
Kuş göçü veri seti (`bird_migration_data.csv`) üzerinde gerçekleştirilen veri analizini, görselleştirme adımlarını (Knime ve Python kullanarak) ve bu analizlere ait detaylı raporları içerir.

### 3. SQL Task (SQL Görevi)
SQLite Sakila veri tabanı üzerinde SQL sorguları ve Python Pandas kütüphanesi kullanılarak gerçekleştirilen veri işleme (DataFrame işlemleri) adımlarını ve notebook dosyalarını içerir.

### 4. GraphRAG Task (GraphRAG Görevi)
Türkçe Wikipedia makalelerinden bilgi grafiği (Knowledge Graph) ve vektör indeksleri oluşturup bunları Neo4j üzerinde saklayan, Google Gemini API desteğiyle hem yerel hem küresel sorulara yanıt verebilen terminal tabanlı gelişmiş bir GraphRAG sistemidir.

---

## 🛠️ Kurulum ve Çalıştırma

Gerekli Python bağımlılıklarını kurmak için ilgili proje dizinlerindeki veya ana dizindeki adımları izleyebilirsiniz.

Örnek olarak GraphRAG projesini çalıştırmak için:
1. `GraphRAG Task` dizinine gidin.
2. Gerekli kütüphaneleri yükleyin: `pip install -r requirements.txt`
3. `.env.example` dosyasından bir `.env` dosyası türetip Neo4j ve Gemini API anahtarlarınızı girin.
4. `python main.py` komutuyla pipeline'ı başlatın.
