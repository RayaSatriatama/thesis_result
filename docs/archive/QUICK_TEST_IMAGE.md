# Quick Test - Image Display Fix

## Changes Made

### Problem
Image tidak muncul di Gradio UI meskipun sudah di-generate.

### Solution
Gunakan `gr.update()` untuk update image component, lebih reliable untuk streaming di Gradio 6.x.

### Code Changes

**Before** (menggunakan direct path):
```python
yield history, canvas_text, status_html, image_path  # image_path = string atau None
```

**After** (menggunakan gr.update()):
```python
if image_path:
    yield history, canvas_text, status_html, gr.update(value=image_path, visible=True)
else:
    yield history, canvas_text, status_html, gr.update(visible=False)
```

### Why gr.update()?
- Gradio 6.x streaming lebih stabil dengan `gr.update()`
- Bisa control `visible` property sekaligus
- Bisa update `value` secara explicit
- Debug log ditambahkan untuk tracking

## Testing

### Test 1: Simple App (Port 7861)
```bash
python test_simple_image.py
```
Test minimal dengan generate image sederhana.

### Test 2: Real Story Generation (Port 7862)
```bash
python test_image_quick.py
```

**Steps**:
1. Buka http://localhost:7862
2. Input: "buat cerita pendek tentang docker"
3. **Watch terminal untuk [DEBUG] messages**
4. Check apakah image muncul setelah "✅ Parallel tasks complete"

### Expected Output

Terminal akan menampilkan:
```
INFO:story_agent.agents.image_generator:✓ Image 1 generated: generated_images\story_illustration_*.png
✅ Parallel tasks complete: Images: 1/1 generated

[DEBUG] Yielding image during streaming: D:\...\generated_images\story_illustration_*.png
```

UI akan menampilkan:
- Image muncul di panel kanan setelah parallel tasks
- Image tetap visible selama revisions
- Status "🎨 Story Illustration" dengan gambar yang terlihat

## Debug Checklist

Jika image masih tidak muncul:

1. ✅ Check terminal untuk "[DEBUG]" messages
2. ✅ Verify file exists: `ls generated_images/`
3. ✅ Check path is absolute
4. ✅ Check Gradio version: `pip show gradio`
5. ✅ Try different browser (Chrome/Firefox)
6. ✅ Check browser console for errors (F12)

## Files Modified

- `story_agent_app.py`:
  - All yields now use `gr.update()` for image component
  - Added debug logging for image paths
  - Lines: 460, 464, 501, 622, 652, 751-754, 798-801, 816
