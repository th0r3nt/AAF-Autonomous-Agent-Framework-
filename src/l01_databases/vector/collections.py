from src.l01_databases.vector.db import VectorDB


class VectorCollection:
    def __init__(self, db: VectorDB, collection_name: str):
        self.db = db
        self.collection_name = collection_name
        self._collection = None

    def get_collection(self):
        if self._collection is None:
            self._collection = self.db.client.get_or_create_collection(
                name=self.collection_name, embedding_function=self.db.embedding_model
            )
        return self._collection
