# Internship Tasks

This repository contains the **data science**, **data visualization**, **SQL**, and **GraphRAG**-based projects and tasks I completed during my internship.

---

## 📂 Repository Content and Tasks

### 1. 5 ML Projects

This section covers **5 different machine learning problems** with their **Knime & Python (Jupyter Notebook)** solutions:

- **Project 1: Classification**
  - *Note:* The dataset for this project was too large, so the generated Knime workflow file (`5 ML Project 1 Classification.knwf`, ~1.75 GB) could not be added to the repository due to GitHub file size limits and is kept locally. However, the classification model was **trained successfully**, and the Python/Knime reports are included in the folder.
- **Project 2: Clustering**
- **Project 3: Regression**
- **Project 4: Association Rule Mining**
- **Project 5: Anomaly Detection**

### 2. Data Visualization Task

Includes the data analysis performed on the **bird migration dataset** (`bird_migration_data.csv`), the visualization steps (using **Knime** and **Python**), and detailed reports of these analyses.

### 3. SQL Task

Includes **SQL queries** on the **SQLite Sakila** database and data processing steps (DataFrame operations) performed using the **Python Pandas** library, along with notebook files.

### 4. GraphRAG Task

An advanced **Flask web and terminal-based GraphRAG** system that builds a **knowledge graph** and **vector indexes** from **Turkish Wikipedia** articles, stores them in **Neo4j**, and answers both **local** and **global** questions with **Google Gemini API** support.

---

## 🛠️ General Overview and Content Structure

The tasks in this repository are organized as **independent workspaces (directories)**. Each folder contains the **datasets**, **source code**, **analysis notebooks**, and **detailed technical reports** for its task:

* **[5 ML Projects](./5%20ML%20Projects)**:
  Contains **Python (Jupyter Notebook)** and **Knime** workflow files along with analysis result reports for 5 core ML projects: **Classification, Clustering, Regression, Association Rule Mining, and Anomaly Detection**.

* **[Data Visualization Task](./Data%20Visualization%20Task)**:
  Covers **time series** and **spatial data visualization** steps on the bird migration dataset, chart outputs, and a technical report explaining the visualization steps.

* **[SQL Task](./SQL%20Task)**:
  Presents **complex SQL queries** on the SQLite Sakila sample database schema and **DataFrame** data processing steps with **Python Pandas** (notebook & PDF outputs).

* **[GraphRAG Task](./GraphRAG%20Task)**:
  Contains a **Flask-based GraphRAG** application that builds a **Knowledge Graph (Neo4j)** and **vector database** integration from Turkish Wikipedia data, with a **Google Gemini-powered local/global hybrid search** mechanism. For detailed technical architecture, data processing steps, test findings, and project documentation, see the [GraphRAG Rapor.pdf](./GraphRAG%20Task/GraphRAG%20Rapor.pdf) file.
