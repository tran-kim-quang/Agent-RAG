---
doc_id: ml_ingest_test_dump_001
title: "Machine Learning Knowledge Dump for Agentic RAG Ingest Test"
language: "vi-en-mixed"
domain: "machine-learning"
version: "v1.0"
created_at: "2026-06-09"
updated_at: "2026-06-09"
status: "test-data"
source_type: "synthetic-markdown"
tags:
  - machine-learning
  - rag-test
  - graph-index
  - vector-search
  - obsidian-compatible
permissions: "internal-test"
---

# Machine Learning Knowledge Dump

> Purpose: This markdown file is designed to test document ingestion, cleaning, chunking, metadata extraction, entity extraction, graph indexing, and retrieval quality in an agentic-RAG system.

[[Machine Learning]] [[Artificial Intelligence]] [[Deep Learning]] [[Agentic RAG]]

CONFIDENTIAL - INTERNAL TEST DATA - DO NOT USE AS REAL SOURCE  
CONFIDENTIAL - INTERNAL TEST DATA - DO NOT USE AS REAL SOURCE

---

## 1. Executive Summary

Machine Learning, often abbreviated as **ML**, is a field of artificial intelligence focused on systems that learn patterns from data and improve performance without being explicitly programmed for every rule.

A basic ML system usually includes:

1. Data collection
2. Data cleaning
3. Feature engineering
4. Model training
5. Model evaluation
6. Deployment
7. Monitoring and retraining

### Key Claim

> Claim: Machine learning performance depends more on data quality and problem framing than on model choice alone.

### Useful Entity Candidates

- Entity: Machine Learning
- Entity: Supervised Learning
- Entity: Unsupervised Learning
- Entity: Reinforcement Learning
- Entity: Neural Network
- Entity: Gradient Descent
- Entity: Overfitting
- Entity: Feature Engineering
- Entity: Model Evaluation
- Entity: Agentic RAG

---

## 2. Definitions

### 2.1 Machine Learning

**Machine Learning** is the process of building algorithms that learn from data. Instead of writing explicit rules, engineers provide examples and let the algorithm infer patterns.

Example:

```text
Input: customer history, transaction amount, location
Output: fraud probability
```

### 2.2 Model

A **model** is a learned function that maps input data to predictions.

```text
f(x) -> y
```

Where:

- `x` = input features
- `y` = predicted output
- `f` = learned model function

### 2.3 Feature

A **feature** is an input variable used by the model.

Examples:

| Feature Name | Type | Example Value | Notes |
|---|---|---:|---|
| age | numeric | 32 | May require normalization |
| city | categorical | Hanoi | Should be encoded |
| purchase_count | numeric | 12 | Useful for customer prediction |
| last_login_days | numeric | 7 | May indicate engagement |

### 2.4 Label

A **label** is the target output the model tries to predict.

Examples:

- Spam or not spam
- Churn or not churn
- House price
- Customer lifetime value
- Disease risk score

---

## 3. Main Types of Machine Learning

### 3.1 Supervised Learning

Supervised learning uses labeled data.

Typical tasks:

- Classification
- Regression
- Ranking
- Forecasting

Common algorithms:

| Algorithm | Task Type | Strength | Weakness |
|---|---|---|---|
| Linear Regression | Regression | Simple, interpretable | Cannot model complex nonlinear patterns |
| Logistic Regression | Classification | Strong baseline | Limited nonlinear capacity |
| Random Forest | Classification/Regression | Robust, handles mixed features | Less interpretable than linear models |
| XGBoost | Classification/Regression | Very strong on tabular data | Needs tuning |
| Neural Network | Many tasks | Flexible, scalable | Needs data and compute |

#### Example: Classification

```python
from sklearn.linear_model import LogisticRegression

model = LogisticRegression()
model.fit(X_train, y_train)
predictions = model.predict(X_test)
```

#### Claim

> Claim: For structured tabular data, gradient boosting models often outperform basic neural networks unless the dataset is very large or highly complex.

---

### 3.2 Unsupervised Learning

Unsupervised learning finds patterns in unlabeled data.

Typical tasks:

- Clustering
- Dimensionality reduction
- Anomaly detection
- Topic discovery

Common algorithms:

| Algorithm | Purpose | Typical Use |
|---|---|---|
| K-Means | Clustering | Customer segmentation |
| DBSCAN | Density-based clustering | Outlier-aware clustering |
| PCA | Dimensionality reduction | Compression and visualization |
| t-SNE | Visualization | High-dimensional data inspection |
| UMAP | Visualization / manifold learning | Fast visualization and embedding exploration |

#### Example: K-Means

```python
from sklearn.cluster import KMeans

model = KMeans(n_clusters=5)
clusters = model.fit_predict(X)
```

#### Retrieval Note

Unsupervised learning is often useful before supervised learning because it can reveal hidden structure in data.

---

### 3.3 Reinforcement Learning

Reinforcement Learning, or **RL**, trains an agent to make sequential decisions by interacting with an environment.

Core concepts:

- Agent
- Environment
- State
- Action
- Reward
- Policy
- Value function

Example:

```text
Agent: game-playing model
Environment: game world
Action: move left, move right, jump
Reward: score increase or penalty
```

#### Claim

> Claim: Reinforcement learning is powerful for sequential decision-making, but it is often harder to train and debug than supervised learning.

---

## 4. ML Pipeline

### 4.1 Data Collection

Data can come from:

- Databases
- APIs
- Event logs
- CRM systems
- Sensors
- User-generated content
- Documents
- Spreadsheets

Bad input data creates bad model behavior.

```text
garbage in -> garbage out
```

### 4.2 Data Cleaning

Common cleaning steps:

- Remove duplicates
- Handle missing values
- Fix inconsistent formatting
- Normalize text
- Remove outliers
- Validate labels
- Detect data leakage
- Remove corrupted records

#### Dirty Example

```csv
customer_id,age,city,churn
001,32,Hanoi,0
002,,Ha Noi,1
002,,Ha Noi,1
003,999,Ho Chi Minh,0
004,twenty five,Da Nang,?
```

#### Cleaned Interpretation

- Customer `002` is duplicated.
- Customer `003` has unrealistic age.
- Customer `004` has invalid age and unknown label.
- City names need normalization: `Hanoi` vs `Ha Noi`.

### 4.3 Feature Engineering

Feature engineering transforms raw data into useful model inputs.

Examples:

| Raw Data | Engineered Feature |
|---|---|
| signup_date | account_age_days |
| transaction_history | average_transaction_value |
| user_events | session_count_7d |
| product_description | text_embedding |
| location | region_cluster |

#### Claim

> Claim: Strong feature engineering can outperform a larger model trained on weak features.

### 4.4 Training

Training is the process of adjusting model parameters to minimize a loss function.

For supervised learning:

```text
model learns by comparing prediction with true label
```

### 4.5 Evaluation

Evaluation measures how well a model performs.

Metrics:

| Metric | Best For | Warning |
|---|---|---|
| Accuracy | Balanced classification | Misleading on imbalanced data |
| Precision | Reducing false positives | May reduce recall |
| Recall | Reducing false negatives | May reduce precision |
| F1 Score | Balance of precision and recall | Hides tradeoff |
| ROC-AUC | Binary classification ranking | Can be optimistic |
| MAE | Regression | Easy to interpret |
| RMSE | Regression | Penalizes large errors |

#### Confusion Matrix

| | Predicted Positive | Predicted Negative |
|---|---:|---:|
| Actual Positive | True Positive | False Negative |
| Actual Negative | False Positive | True Negative |

### 4.6 Deployment

Deployment means making the model available for real use.

Deployment patterns:

- Batch prediction
- Real-time API
- Edge deployment
- Embedded model
- Human-in-the-loop system

### 4.7 Monitoring

After deployment, monitor:

- Prediction quality
- Data drift
- Concept drift
- Latency
- Error rate
- Cost
- User feedback

#### Claim

> Claim: A model that performs well offline can fail in production if the data distribution changes.

---

## 5. Core Concepts

### 5.1 Overfitting

Overfitting happens when a model performs well on training data but poorly on unseen data.

Signs:

- Training accuracy is high.
- Validation accuracy is low.
- Model memorizes noise.
- Performance drops in production.

Prevention:

- Use validation data.
- Use regularization.
- Use simpler models.
- Collect more data.
- Use cross-validation.
- Use early stopping.

### 5.2 Underfitting

Underfitting happens when the model is too simple to capture the pattern.

Signs:

- Training error is high.
- Validation error is high.
- Model misses obvious relationships.

### 5.3 Bias-Variance Tradeoff

High bias:

- Model is too simple.
- Underfits data.

High variance:

- Model is too sensitive to training data.
- Overfits data.

Goal:

```text
find the right level of complexity
```

### 5.4 Data Leakage

Data leakage happens when information from the future or target variable accidentally enters training features.

Example:

```text
Feature: cancellation_date
Target: churn
Problem: cancellation_date is only known after churn happens
```

Data leakage often creates unrealistically high validation scores.

---

## 6. Deep Learning

### 6.1 Neural Networks

A neural network is composed of layers of connected units.

Basic structure:

```text
Input Layer -> Hidden Layers -> Output Layer
```

Each layer transforms the data.

### 6.2 Activation Functions

Common activation functions:

| Activation | Use | Notes |
|---|---|---|
| ReLU | Hidden layers | Simple and effective |
| Sigmoid | Binary output | Can saturate |
| Tanh | Hidden layers | Zero-centered |
| Softmax | Multi-class output | Outputs class probabilities |

### 6.3 Gradient Descent

Gradient descent is an optimization method that updates parameters to reduce loss.

```text
new_weight = old_weight - learning_rate * gradient
```

### 6.4 Backpropagation

Backpropagation calculates gradients through the network so the optimizer can update weights.

### 6.5 Transformers

Transformers are neural network architectures based on attention mechanisms.

They are widely used in:

- Language models
- Translation
- Summarization
- Code generation
- Image generation
- Multimodal models

#### Entity Candidates

- Transformer
- Attention
- Large Language Model
- Embedding
- Token
- Context Window

---

## 7. Embeddings and Vector Search

### 7.1 Embedding

An embedding is a numerical vector representation of data.

Examples:

```text
"machine learning" -> [0.12, -0.04, 0.87, ...]
```

Embeddings can represent:

- Words
- Sentences
- Documents
- Images
- Audio
- Users
- Products

### 7.2 Vector Search

Vector search retrieves items with similar embeddings.

Common similarity metrics:

| Metric | Description |
|---|---|
| Cosine similarity | Measures angle between vectors |
| Dot product | Measures alignment and magnitude |
| Euclidean distance | Measures geometric distance |

### 7.3 Approximate Nearest Neighbor

Approximate nearest neighbor search, or ANN, speeds up vector search.

Common ANN index families:

- HNSW
- IVF
- PQ
- ScaNN
- DiskANN

#### Important Note

HNSW uses a graph internally to speed up nearest-neighbor search. This is not the same as a knowledge graph or property graph.

---

## 8. RAG and Agentic RAG

### 8.1 Retrieval-Augmented Generation

RAG combines retrieval with generation.

Flow:

```text
User Query
→ Retrieve relevant documents
→ Insert context into prompt
→ Generate answer
```

### 8.2 Why RAG Fails

Common failure modes:

- Bad chunking
- Missing metadata
- Duplicate documents
- Outdated documents
- Weak retrieval query
- No reranking
- No citation checking
- Too much irrelevant context
- No temporal reasoning

### 8.3 Agentic RAG

Agentic RAG adds planning, tool use, query rewriting, multi-step retrieval, verification, and memory updates.

Possible agent steps:

1. Understand question
2. Extract entities
3. Rewrite query
4. Search vector index
5. Search keyword index
6. Traverse graph index
7. Rerank results
8. Check contradictions
9. Generate answer
10. Save new memory if useful

### 8.4 Graph RAG

Graph RAG uses graph structure to improve retrieval.

Graph can represent:

- Document hierarchy
- Entity relationships
- Claims and evidence
- Decisions over time
- Tasks and owners
- Project/client context

Example:

```text
(Project: VPBank)
  -[:HAS_DOCUMENT]-> (Document: meeting_note)
  -[:HAS_DECISION]-> (Decision: reduce futuristic tone)
```

---

## 9. Graph Indexing Concepts

### 9.1 Property Graph

A property graph stores:

- Nodes
- Relationships
- Labels
- Properties

Example:

```cypher
(:Project {name: "ML Education"})
  -[:HAS_DOCUMENT]->
(:Document {title: "ML Knowledge Dump"})
```

### 9.2 Useful Graph Nodes for RAG

| Node | Purpose |
|---|---|
| Document | Represents source file |
| Section | Represents heading or logical section |
| Chunk | Represents retrievable text block |
| Entity | Represents person, organization, concept, tool |
| Claim | Represents atomic factual statement |
| Decision | Represents chosen direction |
| Task | Represents actionable item |

### 9.3 Useful Graph Relationships for RAG

| Relationship | Meaning |
|---|---|
| HAS_SECTION | Document contains section |
| HAS_CHUNK | Section contains chunk |
| NEXT | Chunk order |
| MENTIONS | Chunk mentions entity |
| SUPPORTS | Chunk supports claim |
| SUPERSEDES | New decision replaces old decision |
| RELATED_TO | General semantic relation |
| OWNS | Person owns task |

---

## 10. Mini Knowledge Graph Example

```cypher
MERGE (ml:Entity {name: "Machine Learning", type: "Concept"})
MERGE (dl:Entity {name: "Deep Learning", type: "Concept"})
MERGE (nn:Entity {name: "Neural Network", type: "Concept"})
MERGE (tf:Entity {name: "Transformer", type: "Model Architecture"})

MERGE (dl)-[:SUBFIELD_OF]->(ml)
MERGE (nn)-[:USED_IN]->(dl)
MERGE (tf)-[:TYPE_OF]->(nn)
```

Expected graph search:

```text
Transformer -> TYPE_OF -> Neural Network -> USED_IN -> Deep Learning -> SUBFIELD_OF -> Machine Learning
```

---

## 11. Evaluation Cheat Sheet

### 11.1 Classification Metrics

Use classification metrics when the output is a class.

Examples:

- Fraud / not fraud
- Spam / not spam
- Disease / no disease
- Churn / no churn

Important:

```text
Accuracy is not enough when classes are imbalanced.
```

Example:

If only 1% of users churn, a model that always predicts "not churn" gets 99% accuracy but is useless.

### 11.2 Regression Metrics

Use regression metrics when the output is a continuous number.

Examples:

- Price
- Temperature
- Revenue
- Demand
- Time-to-completion

### 11.3 Ranking Metrics

Use ranking metrics when order matters.

Examples:

- Search results
- Recommendation systems
- Candidate ranking
- Product ranking

Metrics:

- MRR
- NDCG
- MAP
- Recall@K
- Precision@K

---

## 12. Common ML Anti-Patterns

### 12.1 Training Before Framing

Bad pattern:

```text
"We have data. Let's train a model."
```

Better pattern:

```text
"What decision will this model improve?"
"What is the cost of a wrong prediction?"
"Who will use the prediction?"
```

### 12.2 Optimizing Offline Metric Only

A model can have high validation score but low business impact.

Need to check:

- Does it reduce cost?
- Does it increase revenue?
- Does it save time?
- Does it improve user experience?
- Does it create risk?

### 12.3 Ignoring Label Quality

Bad labels create bad models.

Label issues:

- Ambiguous class definitions
- Human annotator disagreement
- Outdated labels
- Inconsistent labeling policy
- Label leakage

### 12.4 No Monitoring

A model without monitoring is a temporary experiment, not a production system.

---

## 13. Machine Learning Project Template

### Problem Statement

```text
We want to predict [target] for [user/entity] so that [business decision] can be improved.
```

### Example

```text
We want to predict customer churn for active subscribers so that the retention team can prioritize outreach.
```

### Data Requirements

- Historical customer records
- Event logs
- Purchase history
- Support tickets
- Subscription status
- Churn label

### Model Choice

Start simple:

1. Logistic Regression
2. Random Forest
3. XGBoost
4. Neural Network only if justified

### Evaluation Plan

- Train/validation/test split
- Cross-validation
- Precision/recall tradeoff
- Business metric simulation
- Error analysis
- A/B test if deployed

### Deployment Plan

- Batch scoring once per day
- Store predictions in database
- Dashboard for retention team
- Monitor churn rate, prediction distribution, and feedback

---

## 14. Contradiction Test Section

This section intentionally includes conflicting statements for ingestion and contradiction detection.

### Statement A

> Decision: The project should use only logistic regression because it is always the best model for tabular data.

### Statement B

> Decision: The project should start with logistic regression as a baseline, then compare against tree-based models and gradient boosting.

### Preferred Resolution

Statement B should supersede Statement A because it is more nuanced and realistic.

```yaml
claim_resolution:
  old_claim: "Logistic regression is always the best model for tabular data."
  new_claim: "Logistic regression should be used as a baseline, then compared against stronger candidates."
  relation: "SUPERSEDES"
  confidence: 0.93
```

---

## 15. Duplicate / Boilerplate Test Section

CONFIDENTIAL - INTERNAL TEST DATA - DO NOT USE AS REAL SOURCE  
CONFIDENTIAL - INTERNAL TEST DATA - DO NOT USE AS REAL SOURCE  
CONFIDENTIAL - INTERNAL TEST DATA - DO NOT USE AS REAL SOURCE

This repeated line should be detected as boilerplate and either removed or down-weighted during ingestion.

---

## 16. Obsidian-Style Links and Tags

Related notes:

- [[Supervised Learning]]
- [[Unsupervised Learning]]
- [[Reinforcement Learning]]
- [[Neural Networks]]
- [[Graph RAG]]
- [[Neo4j]]
- [[Qdrant]]
- [[Feature Engineering]]

Tags:

#machine-learning #rag #graph-index #deep-learning #evaluation #agent-memory

---

## 17. Tasks and Action Items

- [ ] Build markdown parser.
- [ ] Preserve YAML frontmatter.
- [ ] Extract headings as Section nodes.
- [ ] Create Chunk nodes with stable IDs.
- [ ] Extract Entity nodes.
- [ ] Create MENTIONS relationships.
- [ ] Create vector index on Chunk embeddings.
- [ ] Create full-text index on Chunk text.
- [ ] Test graph_hops = 1.
- [ ] Test graph_hops = 2.
- [ ] Test duplicate detection.
- [ ] Test contradiction handling.
- [ ] Test citation output.

---

## 18. Example Queries for Testing Retrieval

### Semantic Search Queries

```text
What causes overfitting?
How do embeddings help retrieval?
Why does RAG fail?
What is the difference between supervised and unsupervised learning?
```

### Keyword Search Queries

```text
XGBoost
Qdrant
Neo4j
HNSW
F1 Score
VPBank does not exist here
```

### Graph Search Queries

```text
Which chunks mention Transformer?
What concepts are related to Deep Learning?
Which claim is supported by the section about feature engineering?
Which decision supersedes the old logistic regression decision?
```

### Temporal / Contradiction Queries

```text
What is the preferred model-selection decision?
Which statement is outdated?
Which claim should be considered current?
```

---

## 19. Sample Extracted Triples

```json
[
  {
    "subject": "Deep Learning",
    "predicate": "SUBFIELD_OF",
    "object": "Machine Learning"
  },
  {
    "subject": "Transformer",
    "predicate": "TYPE_OF",
    "object": "Neural Network"
  },
  {
    "subject": "Chunk",
    "predicate": "MENTIONS",
    "object": "Entity"
  },
  {
    "subject": "Statement B",
    "predicate": "SUPERSEDES",
    "object": "Statement A"
  }
]
```

---

## 20. Appendix: Small Glossary

| Term | Definition |
|---|---|
| ML | Machine Learning |
| AI | Artificial Intelligence |
| DL | Deep Learning |
| RL | Reinforcement Learning |
| RAG | Retrieval-Augmented Generation |
| ANN | Approximate Nearest Neighbor |
| HNSW | Hierarchical Navigable Small World |
| KG | Knowledge Graph |
| LPG | Labeled Property Graph |
| BM25 | Keyword ranking function |
| RRF | Reciprocal Rank Fusion |

---

## 21. Footer Noise

Page 1 / 9  
Page 2 / 9  
Page 3 / 9  

CONFIDENTIAL - INTERNAL TEST DATA - DO NOT USE AS REAL SOURCE

---

# End of Machine Learning Knowledge Dump
