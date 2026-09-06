import os
os.environ["HF_HOME"] = "/tmp/hf_cache"
from transformers import pipeline
print("Pipeline imported")
