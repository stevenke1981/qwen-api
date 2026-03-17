import os
from dotenv import load_dotenv
from llama_cpp.server.app import create_app
from llama_cpp.server.settings import Settings

load_dotenv()

settings = Settings(
    model=os.getenv("MODEL_PATH"),
    n_gpu_layers=int(os.getenv("N_GPU_LAYERS", -1)),  # -1 = 全部放 GPU
    n_ctx=int(os.getenv("N_CTX", 8192)),
    n_batch=int(os.getenv("N_BATCH", 512)),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", 8000)),
    chat_format="chatml",
    verbose=False,
)

app = create_app(settings=settings)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )
