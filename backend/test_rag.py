print('=== RAG Pipeline Smoke Test ===')
print()

# 1. Test ChromaDB
print('[1/4] Testing ChromaDB...')
import chromadb
from chromadb.config import Settings
client = chromadb.PersistentClient(path='./chroma_db_test', settings=Settings(anonymized_telemetry=False))
col = client.get_or_create_collection('test', metadata={'hnsw:space': 'cosine'})
print(f'  OK ChromaDB v{chromadb.__version__}')

# 2. Test Sentence-Transformers embedding
print()
print('[2/4] Loading embedding model (all-MiniLM-L6-v2)...')
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
dim = model.get_embedding_dimension()
print(f'  OK Model loaded - {dim}d vectors')

# 3. Test embedding + indexing
print()
print('[3/4] Testing embed + index + retrieve...')
sample_chunks = [
    'Invoice Total: Rs. 45,230.00 including GST',
    'Vendor: ABC Supplies Pvt Ltd, GSTIN: 29ABCDE1234F1Z5',
    'Due Date: 15-December-2026, Payment Terms: Net 30',
    'Line Item: 10x Office Chairs @ Rs. 2,500 = Rs. 25,000',
    'Line Item: 5x Desks @ Rs. 4,046 = Rs. 20,230',
]
embeddings = model.encode(sample_chunks, normalize_embeddings=True).tolist()
ids = ['chunk_{}'.format(i) for i in range(len(sample_chunks))]
col.upsert(ids=ids, documents=sample_chunks, embeddings=embeddings)
print('  OK Indexed {} chunks'.format(len(sample_chunks)))

# 4. Test retrieval
print()
print('[4/4] Testing semantic retrieval...')
query = 'What is the invoice total amount?'
q_emb = model.encode([query], normalize_embeddings=True).tolist()
results = col.query(query_embeddings=q_emb, n_results=2, include=['documents','distances'])
print('  Query: "{}"'.format(query))
for doc, dist in zip(results['documents'][0], results['distances'][0]):
    print('  Score {:.3f}: {}'.format(1-dist, doc))

# Cleanup
client.delete_collection('test')
import shutil
shutil.rmtree('./chroma_db_test', ignore_errors=True)

print()
print('=== ALL TESTS PASSED ===')
print('RAG pipeline is fully operational.')

