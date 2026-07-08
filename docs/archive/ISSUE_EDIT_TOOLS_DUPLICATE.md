# Issue Tracking: Edit Tools Creating Duplicate/Wrong Content

## Problem Statement

During story revision, the edit tools (RevisionAgent) sometimes create duplicate content or wrong edits. Specifically observed:

**Example from user report:**
```
Original paragraph (title):
"Ayam Bakar di Dalam Kotak"

After revision becomes content paragraph:
"Di tengah hiruk pikuk kantor startup teknologi yang modern dan penuh energi, 
Budi, seorang developer junior yang bersemangat, baru saja menekan tombol 
'commit' terakhirnya. Fitur alokasi sumber daya otomatis yang ia kerjakan 
selama dua minggu akhirnya selesai. Dengan dada sedikit membusung karena bangga, 
ia menghampiri meja Rina, mentor sekaligus developer senior di timnya. 
(tadinya ini judul)"
```

Notice the appended text `"(tadinya ini judul)"` - this should NOT be in the output.

## Root Cause Analysis

### 1. **Paragraph Type Detection Issue**
**File**: `story_agent/story_canvas.py` lines 247-265

```python
def _detect_paragraph_type(self, content: str) -> str:
    # Only checks for: dialogue, transition, description, narration
    # Does NOT check for: title, heading, metadata
```

**Issue**: When a title paragraph is edited, it's re-classified as "narration" or "description" because `_detect_paragraph_type()` doesn't have a "title" detection pattern.

### 2. **LLM Adding Explanatory Notes**
**File**: `story_agent/agents/revision_agent.py` lines 540-619

```python
async def _revise_paragraph(self, paragraph, issue: ParagraphIssue, ...):
    prompt = f"""Write ONLY the revised paragraph text, no explanations or markers.

REVISED PARAGRAPH:"""
```

**Issue**: Despite instruction "no explanations", LLM sometimes adds notes like "(tadinya ini judul)" or meta-commentary.

### 3. **Insufficient Response Cleaning**
**File**: `story_agent/agents/revision_agent.py` lines 620-640

```python
def _clean_response(self, text: str) -> str:
    """Clean LLM response of any wrapper text"""
    prefixes_to_remove = [
        "Here is the revised paragraph:",
        "REVISED PARAGRAPH:",
        "Revised:",
        "Here's the revision:",
        "Berikut paragraf yang direvisi:",
    ]
```

**Issue**: Only removes common prefixes, does NOT remove:
- Parenthetical notes like "(tadinya ini judul)"
- Meta-commentary in middle/end of text
- Markdown formatting beyond code blocks

### 4. **Issue Mapping to Wrong Paragraphs**
**File**: `story_agent/agents/revision_agent.py` lines 682-705

```python
@staticmethod
def _find_paragraph_for_issue(canvas: StoryCanvas, issue_text: str):
    """Try to find which paragraph an issue refers to. Uses keyword matching."""
    
    # Extract key item/concept from issue text
    item_match = re.search(r"Item '([^']+)'", issue_text)
    char_match = re.search(r"Karakter '([^']+)'", issue_text)
```

**Issue**: Uses simple keyword matching. If issue says "Item 'fitur alokasi sumber daya otomatis' digunakan..." it finds FIRST paragraph containing that text, which could be the title instead of the actual content paragraph.

## Reproduction Steps

1. Generate story with IT case study (non-dialog style)
2. Story gets title paragraph: "Ayam Bakar di Dalam Kotak"
3. Critic finds coherence issue: "Item 'fitur alokasi sumber daya otomatis' digunakan tanpa diperkenalkan"
4. RevisionAgent calls `_find_paragraph_for_issue()` with that issue
5. It matches paragraph 1 (title) because title also mentions the story concept
6. LLM is asked to revise the title to fix the item introduction issue
7. LLM converts title into a proper paragraph (which makes sense given the fix request)
8. LLM adds note "(tadinya ini judul)" to explain the transformation
9. Response cleaning doesn't catch the parenthetical note
10. Canvas applies edit, replaces title paragraph with content paragraph

## Evidence from Code

### A. Paragraph Type Not Preserved
In `story_canvas.py` line 300:
```python
self.paragraphs[para_idx].paragraph_type = self._detect_paragraph_type(edit.new_content)
```

After edit, paragraph type is RE-DETECTED from new content. If LLM turns a title into narrative content, type changes from "title" to "narration".

### B. Title Type Not Detected
In `story_canvas.py` line 247-265, `_detect_paragraph_type()` has no title detection logic:
```python
# Missing:
if len(content) < 50 and not content.endswith('.'):
    return "title"
```

### C. Index-Based Issue Mapping
In `revision_agent.py` line 702:
```python
for i, para in enumerate(canvas.paragraphs):
    if search_term.lower() in para.content.lower():
        return i, para.id  # Returns FIRST match
```

Returns first paragraph containing the term, which could be title/heading instead of actual content.

## Proposed Fixes

### Fix 1: Improve Paragraph Type Detection
**File**: `story_agent/story_canvas.py`

```python
def _detect_paragraph_type(self, content: str) -> str:
    """Detect paragraph type based on content patterns"""
    
    # Check for title/heading (short, no period at end, < 50 chars)
    if len(content) < 50 and not content.rstrip().endswith(('.', '!', '?', ',')):
        # Further check: no dialogue markers
        if '"' not in content and '—' not in content:
            return "title"
    
    # Check for dialogue markers
    if '"' in content or '"' in content or '"' in content:
        dialogue_chars = content.count('"') + content.count('"') + content.count('"')
        if dialogue_chars > 4:
            return "dialogue"
    
    # ... rest of existing logic
```

### Fix 2: Enhanced Response Cleaning
**File**: `story_agent/agents/revision_agent.py`

```python
def _clean_response(self, text: str) -> str:
    """Clean LLM response of any wrapper text and meta-commentary"""
    
    # Existing prefix removal...
    
    # Remove parenthetical notes (likely meta-commentary)
    import re
    # Remove patterns like: (tadinya ini judul), (previously was X), etc.
    text = re.sub(r'\s*\([^)]*(?:tadinya|previously|was|originally)[^)]*\)', '', text, flags=re.IGNORECASE)
    
    # Remove markdown emphasis markers if present
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
    
    # Remove trailing metadata lines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines that look like metadata/notes
        if line.strip().startswith(('Note:', 'Catatan:', '---', '***')):
            continue
        if '(tadinya' in line.lower() or '(previously' in line.lower():
            # Remove just the parenthetical part
            line = re.sub(r'\s*\([^)]*(?:tadinya|previously)[^)]*\)', '', line, flags=re.IGNORECASE)
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()
```

### Fix 3: Skip Title Paragraphs from Revision
**File**: `story_agent/agents/revision_agent.py`

```python
@staticmethod
def _find_paragraph_for_issue(canvas: StoryCanvas, issue_text: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Try to find which paragraph an issue refers to.
    SKIP title paragraphs to avoid inappropriate edits.
    """
    # ... existing search logic ...
    
    if search_term:
        # Find first NON-TITLE paragraph mentioning this term
        for i, para in enumerate(canvas.paragraphs):
            # Skip titles and headings
            if para.paragraph_type in ["title", "heading"]:
                continue
            
            if search_term.lower() in para.content.lower():
                return i, para.id
    
    return None, None
```

### Fix 4: Preserve Paragraph Type on Edit
**File**: `story_agent/story_canvas.py`

```python
if edit.operation == EditType.REPLACE:
    old_content = self.paragraphs[para_idx].content
    old_type = self.paragraphs[para_idx].paragraph_type
    
    self.paragraphs[para_idx].content = edit.new_content
    self.paragraphs[para_idx].version = self.current_version
    
    # Only re-detect type if old type was generic "narration"
    # Otherwise preserve original semantic type (title, heading, etc.)
    if old_type in ["narration", "description"]:
        self.paragraphs[para_idx].paragraph_type = self._detect_paragraph_type(edit.new_content)
    else:
        # Preserve special types like title, heading
        self.paragraphs[para_idx].paragraph_type = old_type
```

## Testing Plan

1. **Test Case 1: Title Preservation**
   - Create story with title paragraph
   - Trigger revision that mentions concept from title
   - Verify title paragraph is NOT edited
   - Verify title remains a title

2. **Test Case 2: Response Cleaning**
   - Mock LLM response with "(tadinya ini judul)" note
   - Run through `_clean_response()`
   - Verify note is removed

3. **Test Case 3: Type Detection**
   - Test `_detect_paragraph_type()` with various inputs:
     - "Ayam Bakar di Dalam Kotak" → "title"
     - "Di tengah hiruk pikuk..." → "narration"
     - Short sentence ending with period → "narration"

4. **Test Case 4: Issue Mapping**
   - Canvas with: [title, content1, content2]
   - Issue mentions keyword in title AND content2
   - Verify `_find_paragraph_for_issue()` returns content2, not title

## Priority

**HIGH** - This affects story quality and user trust in the revision system.

## Related Files

- `story_agent/story_canvas.py` - Canvas edit application and type detection
- `story_agent/agents/revision_agent.py` - Revision logic and response cleaning
- `story_agent/state.py` - Paragraph data model

## Status

- [x] Issue identified and documented
- [ ] Fix 1: Paragraph type detection improved
- [ ] Fix 2: Response cleaning enhanced
- [ ] Fix 3: Title skip logic added
- [ ] Fix 4: Type preservation on edit
- [ ] Tests created
- [ ] Fixes verified with real story generation

## Notes

This issue is more prevalent with:
- IT case studies (technical content with many specific terms)
- Non-dialog narrative style (where paragraphs are longer and context-heavy)
- Stories with clear title/section structure

The issue is LESS prevalent with:
- Children's stories (simpler, shorter paragraphs)
- Dialog-heavy stories (issues map to dialogue exchanges easily)
- Stories without explicit titles
