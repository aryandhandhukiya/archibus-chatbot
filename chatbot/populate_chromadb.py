import chromadb
client = chromadb.PersistentClient(path="D:\\ARCHIBUSV2\\Extractor\\s3_upload\\chromadb")
collection = client.get_collection(name="image_mapping_metadata")
result = collection.get(include=["metadatas", "documents"])
print("Collection contents:", result)