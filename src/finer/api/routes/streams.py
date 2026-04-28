from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from finer.paths import REPO_ROOT, DATA_ROOT

router = APIRouter()

@router.get("/download")
async def stream_file(path: str = Query(...)):
    """
    Securely serves a file from within the DATA_ROOT directory.
    Uses path traversal safeguards.
    """
    try:
        # Resolve the requested path
        requested_path = Path(path).resolve()
        
        # Security check: ensure the requested path is within DATA_ROOT
        # If it's not absolute or not starting with DATA_ROOT, try joining with DATA_ROOT
        if not str(requested_path).startswith(str(DATA_ROOT.resolve())):
            # Try as relative to DATA_ROOT
            requested_path = (DATA_ROOT / path.lstrip("/")).resolve()
            
        # Final security check
        if not str(requested_path).startswith(str(DATA_ROOT.resolve())):
            raise HTTPException(status_code=403, detail="Path traversal detected or access outside data directory")
            
        if not requested_path.exists() or not requested_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
            
        # Determine media type for direct browser rendering
        ext = requested_path.suffix.lower()
        media_type = "application/octet-stream"
        
        if ext in ['.png']: media_type = "image/png"
        elif ext in ['.jpg', '.jpeg']: media_type = "image/jpeg"
        elif ext in ['.webp']: media_type = "image/webp"
        elif ext in ['.gif']: media_type = "image/gif"
        elif ext in ['.pdf']: media_type = "application/pdf"
        elif ext in ['.md', '.txt']: media_type = "text/plain"
        
        # For inline preview headers so browser doesn't force download
        from urllib.parse import quote
        encoded_filename = quote(requested_path.name)
        # Use RFC 5987 / RFC 8187 encoding for non-ASCII filenames
        headers = {
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"
        }
        
        return FileResponse(
            path=str(requested_path),
            media_type=media_type,
            headers=headers
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
