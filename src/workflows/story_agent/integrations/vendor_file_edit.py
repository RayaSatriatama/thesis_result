
import os
import re
import stat
import shutil
import base64
import mimetypes
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, AsyncIterator, Tuple
from datetime import datetime

# --- From file_operations.py ---

class FileOperationsInterface:
    """Abstract interface for file operations."""
    async def exists(self, path: Path) -> bool: pass
    async def is_file(self, path: Path) -> bool: pass
    async def is_dir(self, path: Path) -> bool: pass
    async def read_file(self, path: Path, encoding: str = 'utf-8') -> str: pass
    async def write_file(self, path: Path, content: Union[str, bytes], encoding: str = 'utf-8') -> None: pass
    async def listdir(self, path: Path) -> List[str]: pass

class LocalFileOperations(FileOperationsInterface):
    """Local filesystem operations implementation."""
    
    async def exists(self, path: Path) -> bool:
        return path.exists()
    
    async def is_file(self, path: Path) -> bool:
        return path.is_file()
    
    async def is_dir(self, path: Path) -> bool:
        return path.is_dir()
    
    async def read_file(self, path: Path, encoding: str = 'utf-8') -> str:
        return path.read_text(encoding=encoding)
    
    async def write_file(self, path: Path, content: Union[str, bytes], encoding: str = 'utf-8') -> None:
        if isinstance(content, str):
            path.write_text(content, encoding=encoding)
        else:
            path.write_bytes(content)

    async def listdir(self, path: Path) -> List[str]:
        return list(os.listdir(path))

# --- From server.py (Helpers) ---

TEXT_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.rst', '.log', '.csv', '.tsv',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.xml', '.html', '.htm', '.xhtml', '.css', '.scss', '.sass',
    '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
    '.py', '.pyw', '.pyx', '.pyi', '.pyc',
    '.java', '.kt', '.scala', '.groovy',
    '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx', '.c++',
    '.cs', '.fs', '.vb', '.swift', '.m', '.mm',
    '.go', '.rs', '.zig', '.nim', '.d',
    '.rb', '.php', '.pl', '.pm', '.lua',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.sql', '.r', '.R', '.jl', '.m', '.mat',
    '.tex', '.bib', '.cls', '.sty',
    '.Dockerfile', '.dockerignore', '.gitignore', '.env'
}

BINARY_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.webp', '.svg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
    '.exe', '.dll', '.so', '.dylib', '.a', '.o',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
    '.ttf', '.otf', '.woff', '.woff2', '.eot'
}

FILE_OPS = LocalFileOperations()

def get_file_type(path: Path) -> str:
    """Determine file type"""
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS or path.name in TEXT_EXTENSIONS:
        return "text"
    elif suffix in BINARY_EXTENSIONS:
        return "binary"
    else:
        # Try to detect using mimetypes
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            if mime_type.startswith('text/'):
                return "text"
            elif mime_type.startswith(('image/', 'audio/', 'video/', 'application/')):
                return "binary"
        return "unknown"

def resolve_path(path: str) -> Path:
    return Path(path).resolve()

# --- From server.py (Tools) ---

async def replace_in_files(
    search: str,
    replace: str,
    path: str = ".",
    file_pattern: str = "*",
    recursive: bool = True,
    max_depth: Optional[int] = None,
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Replace text in files with timeout and depth control.
    Extracted from mcp-file-edit/server.py
    """
    search_path = resolve_path(path)
    
    # Simple regex compilation
    try:
        regex = re.compile(search)
    except re.error as e:
        return {"error": f"Invalid regex: {e}", "completed": False}

    results = []
    files_processed = 0
    timeout_occurred = False
    error = None
    
    async def _replace():
        nonlocal files_processed
        
        if not await FILE_OPS.exists(search_path):
             # In original code this raises ValueError, but here we return error dict structure
             raise ValueError(f"Path does not exist: {path}")
        
        files_to_process = []
        
        if await FILE_OPS.is_file(search_path):
            files_to_process = [search_path]
        else:
            # Simplified directory listing (non-recursive for now if simple)
            # Or assume we are passed a file usually. 
            # Im implementing simple listdir as per original snippet logic
            import fnmatch
            try:
                if recursive:
                    # Recursive walk (simplified implementation of walk_with_depth_async)
                    for root, dirs, files in os.walk(search_path):
                        for file in files:
                            if fnmatch.fnmatch(file, file_pattern):
                                files_to_process.append(Path(root) / file)
                else:
                    entries = await FILE_OPS.listdir(search_path)
                    for entry_name in entries:
                        if fnmatch.fnmatch(entry_name, file_pattern):
                            entry_path = search_path / entry_name
                            if await FILE_OPS.is_file(entry_path):
                                files_to_process.append(entry_path)
            except Exception as e:
                pass

        for file_path in files_to_process:
            if files_processed % 50 == 0:
                await asyncio.sleep(0)
                
            file_type = get_file_type(file_path)
            if file_type != "text":
                continue
                
            try:
                # Read file content
                content = await FILE_OPS.read_file(file_path, encoding='utf-8')
                
                # Perform replacements
                new_content, count = regex.subn(replace, content)
                
                if count > 0:
                    # Write back the modified content
                    await FILE_OPS.write_file(file_path, new_content, encoding='utf-8')
                    
                    file_result = {"file": str(file_path), "replacements": count}
                    results.append(file_result)
                    
                files_processed += 1
            except Exception:
                continue
    
    try:
        await asyncio.wait_for(_replace(), timeout=timeout)
        completed = True
    except asyncio.TimeoutError:
        timeout_occurred = True
        completed = False
        error = f"Replace operation timed out after {timeout} seconds. Partial results returned."
    except Exception as e:
        completed = False
        error = str(e)
    
    return {
        "results": results,
        "completed": completed,
        "files_processed": files_processed,
        "timeout_occurred": timeout_occurred,
        "error": error
    }
