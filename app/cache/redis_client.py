import redis
from app.contract import REDIS_URL
import json
import logging
from typing import final , Any

log = logging.getLogger(__name__)


@final
class RedisClient : 
    
    
    def __init__(self , url : str = REDIS_URL):
        
        self.re = redis.Redis.from_url(
            
            url ,
            decode_responses=True,
            socket_connect_timeout=1, # fail fast if redis is down
            socket_timeout=1
            
        )
        
        
        

# REDIS CRUD Operations : GET , DELETE , SET

    def get(self , key : str)-> str | None:
        
        try : 
            
            return self.re.get(key)
        
        except redis.RedisError as e :
            
            log.warning("redis get failed: %s", e)
            return None
        
        
        
        
    def set(self , key : str , value : str , ttl : int | None = None)-> bool : 
        
        try : 
            
            return bool(self.re.set(key, value, ex=ttl))
        
        except redis.RedisError as e :
            
            log.warning("redis set failed: %s", e)
            return False
        
        


    def delete(self , key : str)-> bool : 
        
        try : 
            
            return bool(self.re.delete(key))
        
        except redis.RedisError as e :
            
            log.warning("reidis delete failed: %s" , e)
            return False
        
        
        

## Version Number inside the key : Counter (corpus:version) -> represent the current state of knowledge base

    def incr(self , key : str)-> int | None: 
        
        try : 
            
            return self.re.incr(key)
        
        except redis.RedisError as e :
            
            log.warning("redis increment issue : %s" , e)
            return None
        
        
        

## 2 Helper Methods to get & set structured json from redis "string" Value .

    def get_json(self , key : str) -> Any | None:
        
        data = self.get(key)
        
        if data is None : 
            return None
        
        try : 
            
            return json.loads(data) 
        
        except json.JSONDecodeError :
            log.warning("Invalid JSON stored for key: %s", key)
            return None
        
        
    
    def set_json(self , key : str , value : str, ttl : int | None = None)-> bool : 
        
        try:
            serialized = json.dumps(value)
            return self.set(key, serialized, ttl)

        except (TypeError, ValueError):
            log.exception("JSON serialization failed for key: %s", key)
            return False
    
    
    

# helper methods to check health of Cache & exists of key

    def ping(self) -> bool:
       try:
           return bool(self.re.ping()) 
       
       except redis.RedisError:
           log.exception("Redis health check failed")
           return False
       
       
    def exists(self, key: str) -> bool:

        try:
            return bool(self.re.exists(key))

        except redis.RedisError:
            log.exception("Redis EXISTS failed")
            return False
        
        
# Close Function
    def close(self) -> None:
        self.re.close()
        
        
        
# create one shared redis object instead of new client every time
redis_client = RedisClient()