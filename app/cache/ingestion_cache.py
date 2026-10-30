from .redis_client import redis_client
import logging
import hashlib

logger = logging.getLogger(__name__)



class IngestionCache :
    
    
    def __init__(self , ttl : int = 86400) : # 86400 = 1 day expiration
        
        self.redis = redis_client
        self.ttl = ttl
        
        

# get unique key by hasing file content .
#### Hash Key pattern -> : ingestion:{file_hash}
    @staticmethod
    def generate_key(file_content: bytes) -> str:
        """Generate a unique cache key based on file content."""

        file_hash = hashlib.sha256(file_content).hexdigest()

        return f"ingestion:{file_hash}"
    
    


    def exists(self, file_content: bytes) -> bool:
        """Check whether a document has already been ingested or not."""

        key = self.generate_key(file_content)

        return bool(self.redis.exists(key))



# REDIS CRUD OPs
    def get(self, file_content: bytes)-> str | None: # here is return string , because we use decode=True in redis client , so return string not bytes .
        """Retrieve cached ingestion result."""

        key = self.generate_key(file_content)

        result = self.redis.get(key)

        if result is None:
            return None

        logger.debug("Ingestion cache hit: %s", key)

        return result



    def set(self, file_content: bytes, value: str) -> bool:
        """Save ingestion result in Redis."""

        key = self.generate_key(file_content)

        success = self.redis.set(
            key,
            value,
            ttl=self.ttl,
        )

        if success:
            logger.info("Ingestion result cached: %s", key)

        return success



    def delete(self, file_content: bytes) -> None:
        """Delete cached ingestion result."""

        key = self.generate_key(file_content)

        self.redis.delete(key)

        logger.info("Ingestion cache deleted: %s", key)
