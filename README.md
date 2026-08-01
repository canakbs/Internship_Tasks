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
Türkçe Wikipedia makalelerinden bilgi grafiği (Knowledge Graph) ve vektör indeksleri oluşturup bunları Neo4j üzerinde saklayan, Google Gemini API desteğiyle hem yerel hem küresel sorulara yanıt verebilen, gelişmiş bir **Flask Web ve terminal tabanlı GraphRAG** sistemidir.

---

## 🛠️ Proje Genel Genel Bakışı ve İçerik Yapısı

Bu depodaki görevler bağımsız çalışma alanları (dizinler) şeklinde yapılandırılmıştır. Her bir klasör ilgili göreve ait veri setlerini, kaynak kodları, analiz notebook'larını ve detaylı teknik raporları barındırmaktadır:

* **[5 ML Projects](./5%20ML%20Projects)**: 
  Sınıflandırma, Kümeleme, Regresyon, Birliktelik Kuralları Çıkarımı ve Anomali Tespiti olmak üzere 5 temel ML projesine ait Python (Jupyter Notebook) ve Knime çalışma dosyaları ile analiz sonuç raporlarını içerir.

* **[Data Visualization Task](./Data%20Visualization%20Task)**: 
  Kuş göçü veri seti üzerinden gerçekleştirilen zaman serisi ve mekânsal veri görselleştirme adımlarını, grafik çıktılarını ve görselleştirme adımlarını açıklayan teknik raporu kapsar.

* **[SQL Task](./SQL%20Task)**: 
  SQLite Sakila örnek veri tabanı mimarisi üzerinde yürütülen Karmaşık SQL sorgulamaları ve Python Pandas kütüphanesi ile DataFrame veri işleme adımlarını (Notebook & PDF çıktıları) sunar.

* **[GraphRAG Task](./GraphRAG%20Task)**: 
  Türkçe Wikipedia verileriyle Knowledge Graph (Neo4j) ve Vektör Veri Tabanı entegrasyonu kuran, Google Gemini destekli yerel/küresel hibrit arama mekanizmasına sahip Flask tabanlı GraphRAG uygulamasını barındırır. Detaylı teknik mimari, veri işleme adımları, test bulguları ve proje açıklamaları için [GraphRAG Rapor.pdf](./GraphRAG%20Task/GraphRAG%20Rapor.pdf) dosyasını inceleyebilirsiniz.
