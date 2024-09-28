from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from llm import get_image_query, get_fal_ai_image, small_llm, setup_logger
from fastapi.middleware.cors import CORSMiddleware  # Add this import
import uvicorn
import os

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class PostContent(BaseModel):
    content: str

@app.post("/generate-image")
async def generate_image(post_content: PostContent):
    try:
        # Generate image query
        image_query = get_image_query(post_content.content, small_llm)
        logging.info(f"Image query: {image_query}")

        # Generate image
        image_url = get_fal_ai_image(image_query)
        
        if not image_url:
            raise HTTPException(status_code=500, detail="Failed to generate image")
        
        return {"image_url": image_url}
    except Exception as e:
        logging.error(f"Error generating image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
async def test():
    return {"message": "API is working"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
