import os
from dotenv import load_dotenv
from huggingface_hub import snapshot_download

load_dotenv()

token = os.getenv("HF_TOKENS")
data_source = os.getenv("DATA_SOURCE")

snapshot_download(
    repo_id=data_source,
    repo_type="dataset",
    token=token,
    local_dir=f"data/{data_source.split('/')[-1]}",
)
