
import os
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

async def render_mermaid(
    mermaid_code: str,
    output_path: Optional[str] = None,
    theme: str = "default",
    background_color: str = "white"
) -> Dict[str, Any]:
    """
    Ported logic from mcp-mermaid/src/utils/render.ts
    Uses mmdc (Mermaid CLI) instead of mermaid-isomorphic directly, 
    but follows the same pattern of creating a temp CSS file and rendering.
    """
    
    # sanitize code (stripped markdown blocks) - ensure this is done before passing here
    mermaid_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
    
    # Create temp CSS file
    # const cssContent = `svg { background: ${backgroundColor}; }`;
    css_content = f"svg {{ background: {background_color}; }}"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.css', delete=False, encoding='utf-8') as css_file:
        css_file.write(css_content)
        css_path = css_file.name
        
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False, encoding='utf-8') as mmd_file:
        mmd_file.write(mermaid_code)
        mmd_path = mmd_file.name

    try:
        # Determine output path
        if not output_path:
            # Create temp output
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as out:
                output_path = out.name
                
        # Run mmdc
        # Logic matches mcp-mermaid render call: 
        # renderer([mermaid], { screenshot: true, css: cssTmpPath, mermaidConfig: { theme: theme } })
        
        # We assume npx is available or mmdc is in path
        # In a real "clone" scenario, we might use the node_modules from the cloned repo,
        # but calling npx is safer for environment portability if not installed.
        # However, to be strict about "using their tools", we should use the mmdc from their package.json deps?
        # mcp-mermaid has "mermaid-isomorphic" in deps.
        # We will simulates the tool's behavior using 'npx -y @mermaid-js/mermaid-cli'
        
        # Determine npx command based on OS
        npx_cmd = "npx.cmd" if os.name == 'nt' else "npx"
        
        cmd = [
            npx_cmd, "-y", "@mermaid-js/mermaid-cli",
            "-i", mmd_path,
            "-o", output_path,
            "-t", theme,
            "-C", css_path,
            "-b", background_color
        ]
        
        # Depending on OS/Shell, npx might need shell=True or full path. Windows often needs shell=True for npx.
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Mermaid rendering failed: {stderr.decode('utf-8')}")
            
        return {
            "output_path": output_path,
            "stdout": stdout.decode('utf-8'),
            "success": True
        }
        
    finally:
        # Cleanup temp files
        if os.path.exists(css_path):
            os.remove(css_path)
        if os.path.exists(mmd_path):
            os.remove(mmd_path)
