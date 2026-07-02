# Living Record

> **Transforming isolated medical reports into a living clinical record.**

Healthcare is a continuous journey, yet most AI systems treat medical reports as isolated documents. **Living Record** builds an evolving clinical memory where every new report enriches the patient's history instead of becoming another disconnected file.

Built as a hackathon project to demonstrate how persistent memory can improve longitudinal understanding of patient health.

---

## Why Living Record?

Traditional document-based AI systems answer questions by searching uploaded documents every time.

Living Record takes a different approach.

Instead of repeatedly searching documents, it **remembers**.

Every uploaded report becomes part of an evolving clinical memory that understands:

* Disease progression
* Medication history
* Laboratory trends
* Clinical observations
* Treatment evolution
* Relationships between medical events

---

## The Problem

Healthcare information is fragmented.

```
Report 1
Report 2
Report 3
Report 4
Report 5
Report 6
```

Each report contains only a snapshot of the patient's condition.

Understanding the complete story requires connecting information across months or years.

Most AI systems retrieve document chunks.

They **do not build memory**.

---

## Our Solution

Living Record converts medical reports into an evolving knowledge graph that acts as a persistent clinical memory.

```mermaid
flowchart TD

    A[Medical Reports]
    B[Medical Ontology]
    C[Persistent Clinical Memory]
    D[Knowledge Graph]
    E[Recall]
    F[Evidence-backed Answers]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```

---

## Core Memory Formation

Every uploaded report becomes another memory.

```mermaid
flowchart LR

    R1[Report 1]
    R2[Report 2]
    R3[Report 3]
    R4[Report 4]
    R5[Report 5]
    R6[Report 6]

    MEMORY[(Living Clinical Memory)]

    R1 --> MEMORY
    R2 --> MEMORY
    R3 --> MEMORY
    R4 --> MEMORY
    R5 --> MEMORY
    R6 --> MEMORY

    MEMORY --> GRAPH[Growing Knowledge Graph]
```

Instead of creating isolated embeddings, every report enriches the existing patient memory.

---

## Behind the Scenes

```mermaid
flowchart TD

    A[Upload PDF]
    B[Store Report]
    C[Remember]
    D[Medical Ontology]
    E[Entity & Relationship Extraction]
    F[Persistent Clinical Memory]
    G[Knowledge Graph Updated]
    H[Ask Question]
    I[Recall]
    J[Evidence-backed Answer]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G

    H --> I
    I --> F
    F --> J
```

---

## Memory Evolution

As new reports arrive, memory evolves instead of restarting.

```mermaid
graph LR

    subgraph Report 1
        P1[Patient]
        D1[Type 2 Diabetes]
        P1 --> D1
    end

    subgraph Report 2
        M1[Metformin]
        L1[HbA1c 8.2%]
        D1 --> M1
        D1 --> L1
    end

    subgraph Report 4
        I1[Basal Insulin]
        L2[HbA1c 6.9%]
        D1 --> I1
        D1 --> L2
    end

    subgraph Report 6
        F1[Annual Review]
        S1[Stable Condition]
        P1 --> F1
        D1 --> S1
    end
```

The graph continuously becomes richer as more clinical information is remembered.

---

## Example Questions

* How has John's diabetes progressed?
* When was insulin introduced?
* Show all HbA1c values over time.
* Which medications are currently active?
* Summarize the patient's clinical journey.
* What changed since the first visit?

---

## System Architecture

```mermaid
flowchart TB

    subgraph Frontend
        UI[Frontend Application]
    end

    subgraph Backend
        API[FastAPI]

        UPLOAD[Upload Service]
        MEMORY[Memory Service]
        GRAPH[Graph Service]
        CHAT[Recall Service]
    end

    subgraph Storage
        FILES[(Medical Reports)]
        GRAPHS[(Graph Snapshots)]
    end

    subgraph Memory
        CLINICAL[(Living Clinical Memory)]
    end

    UI --> API

    API --> UPLOAD
    API --> MEMORY
    API --> GRAPH
    API --> CHAT

    UPLOAD --> FILES

    MEMORY --> CLINICAL

    GRAPH --> GRAPHS

    CHAT --> CLINICAL
```

---

## 📂 Repository Structure

```text
living-record/

├── backend/
│   ├── api/
│   ├── services/
│   ├── storage/
│   └── main.py
│
├── frontend/
│
├── ontology/
│   └── medical_memory_ontology.owl
│
├── reports/
│   ├── John_Doe_01.pdf
│   ├── ...
│
├── graphs/
│
└── README.md
```

---

## Features

* 📄 Medical report ingestion
* 🧠 Persistent clinical memory
* 🩺 Medical ontology
* 🕸️ Knowledge graph generation
* 📈 Longitudinal patient timeline
* 🔍 Evidence-backed recall
* 📚 Incremental memory growth
* 🔗 Semantic relationships

---

## Vision

Healthcare is not a collection of documents.

It is a continuously evolving story.

**Living Record** transforms isolated medical reports into a living clinical record that grows with every patient encounter, enabling contextual, explainable, and longitudinal understanding of patient care.
