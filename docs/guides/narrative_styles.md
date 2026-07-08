# Narrative Style Support - Story Agent

## Overview
Story Agent mendukung berbagai gaya naratif untuk pembelajaran berbasis cerita, termasuk style khusus untuk studi kasus IT/teknis yang biasanya menggunakan narasi non-dialog.

## Supported Narrative Styles

### 1. `campuran` (Default)
- **Deskripsi**: Seimbang antara narasi dan dialog
- **Use Case**: Cerita anak-anak, adventure stories
- **Karakteristik**: Natural balance, engaging untuk semua usia

### 2. `dialog_dominan`
- **Deskripsi**: Lebih banyak dialog antar karakter, minimal narasi
- **Use Case**: Drama, interpersonal stories
- **Karakteristik**: Story unfolds through conversations

### 3. `monolog_dominan`
- **Deskripsi**: Lebih banyak narasi dan deskripsi, minimal dialog
- **Use Case**: Descriptive storytelling, scenic narratives
- **Karakteristik**: Focus on descriptive prose

### 4. `monolog_internal`
- **Deskripsi**: Fokus pada pikiran dan perasaan internal karakter
- **Use Case**: Psychological stories, character development
- **Karakteristik**: Inner monologue extensively used

### 5. `dialog_murni`
- **Deskripsi**: Hampir seluruhnya dialog, seperti script drama
- **Use Case**: Play scripts, pure dialogue stories
- **Karakteristik**: Minimal narrative description

### 6. `non_dialog` ⭐ **RECOMMENDED FOR IT CASE STUDIES**
- **Deskripsi**: HANYA narasi dan deskripsi, TANPA DIALOG SAMA SEKALI
- **Use Case**: 
  - Technical case studies
  - IT tutorials dalam bentuk cerita
  - Professional learning scenarios
  - Documentation-style narratives
- **Karakteristik**: 
  - No quotation marks
  - No character speech
  - Describes actions, settings, thoughts
  - Professional tone

### 7. `deskriptif`
- **Deskripsi**: Pure descriptive prose tanpa dialog atau direct speech
- **Use Case**: Visual scene descriptions, atmospheric writing
- **Karakteristik**: Like reading a visual scene

## Implementation

### In Code (state.py)
```python
narrative_style: str  # campuran, dialog_dominan, monolog_dominan, monolog_internal, 
                      # dialog_murni, non_dialog, deskriptif
```

### In Writer Agent (writer.py)
```python
narrative_instructions = {
    "non_dialog": "Write ONLY narration and description. NO DIALOGUE AT ALL. 
                   Describe actions, settings, thoughts, but never use quotation 
                   marks or character speech.",
    "deskriptif": "Write purely descriptive prose. Focus on describing scenes, 
                   actions, and atmosphere WITHOUT any dialogue or direct speech."
}
```

### Usage Example - IT Case Study

```python
initial_state = {
    "user_request": "Cerita tentang Docker untuk developer junior",
    "narrative_style": "non_dialog",  # Kunci untuk IT case study
    "target_age": "18+",
    "theme": "technology"
}
```

**Result**: Story tanpa dialog, fokus pada narasi teknis seperti:
- Budi mengalami masalah deployment
- Rina menjelaskan konsep Docker dengan analogi
- Proses troubleshooting dijelaskan secara deskriptif
- NO quotation marks, NO "kata Budi", NO dialog

## Testing

Run test untuk verify non-dialog style:
```bash
python test_narrative_nondialog.py
```

Test akan check:
- ✅ No dialog markers (`"`, `'`, `—`, `:`, `berkata`, `ujar`)
- ✅ Pure narrative description
- ✅ Technical concepts explained without dialogue

## Best Practices

### For IT/Technical Case Studies:
1. **Always use** `narrative_style: "non_dialog"`
2. Set `target_age: "18+"` untuk professional tone
3. Use `theme: "technology"` atau specific tech domain
4. Request specific technical concepts in user_request

### For Children Stories:
1. Use `narrative_style: "campuran"` (default)
2. Balance dialog dan narasi
3. Engaging characters dengan conversations

### For Drama/Play Scripts:
1. Use `narrative_style: "dialog_murni"`
2. Minimal stage directions
3. Story through conversations only

## Recent Fixes (December 8, 2025)

### ✅ Fixed: Terminal Output Overlapping
**Problem**: Image generator print statements overlapped with critic summary
```python
# Before (causing overlap)
print("\n🎨 IMAGE GENERATOR: Membuat ilustrasi cerita...")

# After (using logger)
import logging
logger = logging.getLogger(__name__)
logger.info("🎨 IMAGE GENERATOR: Membuat ilustrasi cerita...")
```

**Files Modified**: 
- `story_agent/agents/image_generator.py`: All print() → logger.info()/logger.warning()

**Impact**: Clean terminal output, no more text overlap during parallel execution

### ✅ Fixed: Image Preview Not Showing in Gradio
**Problem**: Image component had unsupported parameter `show_download_button`
```python
# Before (error)
image_preview = gr.Image(
    show_download_button=True  # Not supported in this Gradio version
)

# After (fixed)
image_preview = gr.Image(
    label="🎨 Story Illustration",
    type="filepath",
    height=200
)
```

**Files Modified**:
- `story_agent_app.py`: Removed unsupported parameter

**Impact**: Image preview now displays correctly in Gradio UI

### ✅ Fixed: Yield Signature Mismatch
**Problem**: Function yielded 3 values but consumer expected 4
```python
# Before (error)
yield history, canvas_text, status_html

# After (fixed)
yield history, canvas_text, status_html, None  # or image_path
```

**Files Modified**:
- `story_agent_app.py`: All yield statements now return 4-tuple

**Impact**: No more "not enough values to unpack" errors

## Known Issues

### ⚠️ Edit Tools May Create Duplicates
**Symptom**: During revision, paragraph content may appear twice or with wrong edits
**Example**: Title paragraph becomes content paragraph with note "(tadinya ini judul)"
**Status**: Under investigation
**Workaround**: Monitor revision logs, manual review of final output

**Related Files**:
- `story_agent/agents/revision_agent.py`: Paragraph editing logic
- `story_agent/story_canvas.py`: Canvas state management

## Related Documentation

- **Architecture**: [docs/architecture/system_overview.md](../architecture/system_overview.md)
- **Agentic workflow**: [docs/architecture/pengembangan_arsitektur_agentic_ai.md](../architecture/pengembangan_arsitektur_agentic_ai.md)
- **Documentation index**: [docs/index.md](../index.md)
