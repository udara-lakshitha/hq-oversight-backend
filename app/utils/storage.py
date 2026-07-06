import os
from supabase import create_client, Client
from fastapi import HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv("SUPABASE_BUCKET_NAME", "exam-assets")

def get_supabase_client() -> Client:
    """Initializes and returns a Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(
            status_code=500, 
            detail="Supabase credentials are missing from environment variables."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_file_to_supabase(file_bytes: bytes, file_name: str, folder: str) -> str:
    """
    Uploads a file directly to the specified Supabase storage bucket.
    Returns the unique storage path on success.
    """
    supabase = get_supabase_client()
    storage_path = f"{folder}/{file_name}"
    
    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        return storage_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase upload failed: {str(e)}")

def get_signed_download_url(storage_path: str, expires_in: int = 3600) -> str:
    """
    Generates a secure, temporary download link for a file path.
    """
    supabase = get_supabase_client()
    try:
        response = supabase.storage.from_(BUCKET_NAME).create_signed_url(storage_path, expires_in)
        return response.get("signedURL")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download link: {str(e)}")

def get_file_from_supabase(storage_path: str) -> bytes:
    """
    Downloads binary file content directly from Supabase.
    """
    supabase = get_supabase_client()
    try:
        return supabase.storage.from_(BUCKET_NAME).download(storage_path)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found in storage: {str(e)}")