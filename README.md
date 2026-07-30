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

## 🛠️ Kurulum ve Çalıştırma

Bu depodaki görevler bağımsız çalışma alanları (dizinler) şeklinde yapılandırılmıştır. Her bir projenin kendine has araçları, bağımlılıkları ve çalıştırma yöntemleri mevcuttur:

- **GraphRAG Task (Flask Web & Pipeline)**:
  1. `GraphRAG Task` dizinine gidin.
  2. Gerekli kütüphaneleri yükleyin: `pip install -r requirements.txt`
  3. `.env.example` dosyasından bir `.env` dosyası oluşturup API ve veri tabanı kimlik bilgilerinizi girin.
  4. Web arayüzünü başlatmak için `python app.py` komutunu çalıştırıp tarayıcınızdan `http://localhost:5000` adresine gidin. Detaylı bilgi için [GraphRAG README](file:///GraphRAG%20Task/README.md) dosyasını inceleyebilirsiniz.
  
- **Veri Analizi ve Veri Tabanı Görevleri (Jupyter Notebooks)**:
  * **5 ML Projects**, **Data Visualization Task** ve **SQL Task** dizinlerindeki Jupyter Notebook (`.ipynb`) dosyalarını ve analiz raporlarını incelemek ya da çalıştırmak için bilgisayarınızda Jupyter Notebook / JupyterLab ortamının veya VS Code Jupyter eklentisinin kurulu olması gerekmektedir. İlgili dizinlerdeki notebook dosyalarını açarak hücreleri sırayla çalıştırabilirsiniz.
