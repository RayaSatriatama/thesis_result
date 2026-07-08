"""
Story Canvas - Paragraph-level story management with version control
Provides targeted editing, diff visualization, and revision history

Sistem Canvas untuk manajemen cerita berbasis paragraf dengan kontrol versi
"""

import difflib
import uuid
import copy
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from loguru import logger


class EditType(Enum):
    """Jenis operasi edit"""
    REPLACE = "replace"
    INSERT = "insert"
    DELETE = "delete"
    MERGE = "merge"


@dataclass
class Paragraph:
    """Represents a single paragraph in the story"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    version: int = 0  # Which revision created/modified this
    paragraph_type: str = "narration"  # narration, dialogue, description, transition
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Paragraph':
        return cls(**data)


@dataclass
class EditOperation:
    """Represents a single edit operation on the canvas"""
    operation: EditType
    target_id: str  # Paragraph ID to edit
    target_index: int = -1  # Paragraph index (for display)
    new_content: str = ""
    reason: str = ""  # Why this edit (from critic feedback)
    
    def to_dict(self) -> dict:
        return {
            "operation": self.operation.value,
            "target_id": self.target_id,
            "target_index": self.target_index,
            "new_content": self.new_content,
            "reason": self.reason
        }


@dataclass
class ParagraphIssue:
    """Issue identified in a specific paragraph by critic"""
    paragraph_index: int
    paragraph_id: str
    issue_type: str  # coherence, style, educational, narrative, character, item, structure, sentiment
    description: str
    suggested_fix: str
    severity: str = "medium"  # low, medium, high, critical, major, minor
    location: str = ""  # Additional location info (e.g., "Paragraph 3")
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ParagraphIssue':
        return cls(**data)


@dataclass
class StructuredCritique:
    """
    Structured critique output from critic agent.
    Supports both paragraph-level issues and general feedback.
    """
    overall_score: float
    paragraph_issues: List[ParagraphIssue]
    general_feedback: str
    decision: str  # APPROVE or REVISE
    
    # Extended fields for detailed critique
    educational_score: float = 0.0
    coherence_score: float = 0.0
    educational_strengths: List[str] = field(default_factory=list)
    educational_weaknesses: List[str] = field(default_factory=list)
    revision_targets: List[Dict] = field(default_factory=list)
    summary_feedback: str = ""
    
    def get_flagged_paragraphs(self) -> List[Tuple[int, str, ParagraphIssue]]:
        """Return list of (index, id, issue) for paragraphs needing revision"""
        return [(issue.paragraph_index, issue.paragraph_id, issue) 
                for issue in self.paragraph_issues]
    
    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "paragraph_issues": [i.to_dict() for i in self.paragraph_issues],
            "general_feedback": self.general_feedback,
            "decision": self.decision,
            "educational_score": self.educational_score,
            "coherence_score": self.coherence_score,
            "educational_strengths": self.educational_strengths,
            "educational_weaknesses": self.educational_weaknesses,
            "revision_targets": self.revision_targets,
            "summary_feedback": self.summary_feedback
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StructuredCritique':
        """Deserialize from dict (e.g., from state)"""
        paragraph_issues = [
            ParagraphIssue.from_dict(i) for i in data.get("paragraph_issues", [])
        ]
        return cls(
            overall_score=data.get("overall_score", 5.0),
            paragraph_issues=paragraph_issues,
            general_feedback=data.get("general_feedback", ""),
            decision=data.get("decision", "REVISE"),
            educational_score=data.get("educational_score", 0.0),
            coherence_score=data.get("coherence_score", 0.0),
            educational_strengths=data.get("educational_strengths", []),
            educational_weaknesses=data.get("educational_weaknesses", []),
            revision_targets=data.get("revision_targets", []),
            summary_feedback=data.get("summary_feedback", "")
        )


@dataclass
class RevisionSnapshot:
    """Snapshot of canvas at a specific version"""
    version: int
    paragraphs: List[dict]  # Serialized paragraphs
    timestamp: str
    feedback: str
    edits_applied: List[dict]  # Serialized edit operations
    score: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)


class StoryCanvas:
    """
    Central canvas for managing story content with version control.
    
    Features:
    - Paragraph-level editing (not full rewrite)
    - Revision history with diff tracking
    - Targeted edit operations
    - Parallel edit support
    """
    
    def __init__(self):
        self.paragraphs: List[Paragraph] = []
        self.history: List[RevisionSnapshot] = []
        self.current_version: int = 0
        self.session_id: str = str(uuid.uuid4())[:12]
        self.title: str = ""
    
    def initialize_from_text(self, text: str, title: str = "") -> int:
        """
        Initialize canvas from a full story text.
        Splits by double newlines into paragraphs.
        Automatically removes duplicate/near-duplicate paragraphs.
        
        Returns: Number of paragraphs created
        """
        # Clean and split text
        text = text.strip()
        raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        # Create paragraph objects
        self.paragraphs = []
        for content in raw_paragraphs:
            # Detect paragraph type
            para_type = self._detect_paragraph_type(content)
            self.paragraphs.append(Paragraph(
                content=content,
                version=0,
                paragraph_type=para_type
            ))
        
        # Remove duplicate paragraphs
        removed_count = self._deduplicate_paragraphs()
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} duplicate paragraph(s)")
        
        # Save initial snapshot
        self._save_snapshot("Initial draft (Draf awal)", [], score=0.0)
        
        if title:
            self.title = title
            
        logger.info(f"Canvas initialized: {len(self.paragraphs)} paragraphs. Title: {self.title}")
        return len(self.paragraphs)
    
    def _deduplicate_paragraphs(self, similarity_threshold: float = 0.75) -> int:
        """
        Remove duplicate or near-duplicate consecutive paragraphs.
        
        Args:
            similarity_threshold: Paragraphs with similarity >= this will be deduplicated
            
        Returns: Number of paragraphs removed
        """
        if len(self.paragraphs) < 2:
            return 0
        
        removed_count = 0
        i = 0
        
        while i < len(self.paragraphs) - 1:
            current = self.paragraphs[i].content
            next_para = self.paragraphs[i + 1].content
            
            # Calculate similarity
            similarity = self._calculate_similarity(current, next_para) / 100.0
            
            if similarity >= similarity_threshold:
                # Keep the longer paragraph (more complete)
                if len(next_para) > len(current):
                    # Remove current, keep next
                    del self.paragraphs[i]
                    removed_count += 1
                    # Don't increment i, check new paragraph at same position
                else:
                    # Remove next, keep current
                    del self.paragraphs[i + 1]
                    removed_count += 1
                    # Don't increment i, check against new next paragraph
            else:
                i += 1
        
        return removed_count
    
    def _detect_paragraph_type(self, content: str) -> str:
        """Detect paragraph type based on content patterns"""
        # Check for scene transitions FIRST (highest priority)
        transition_markers = ['***', '---', '===', '* * *']
        if any(marker in content for marker in transition_markers):
            return "transition"
        
        # Check for title/heading (short, no period at end, < 60 chars)
        stripped = content.rstrip()
        if len(stripped) < 60 and not stripped.endswith(('.', '!', '?', ',', ';')):
            # Further check: no dialogue markers and no multiple sentences
            if '"' not in content and '—' not in content and content.count('.') < 2:
                return "title"
        
        # Check for dialogue markers
        if '"' in content or '"' in content or '"' in content:
            # Count dialogue vs narration
            dialogue_chars = content.count('"') + content.count('"') + content.count('"')
            if dialogue_chars > 4:
                return "dialogue"
        
        # Check for descriptions (typically starts with setting words)
        # But only if it has descriptive keywords AND is substantial content
        desc_starters = ['di ', 'pada ', 'suasana ', 'langit ', 'ruangan ', 'tempat ']
        desc_keywords = ['luas', 'terang', 'besar', 'tinggi', 'indah', 'cantik', 'megah', 'modern']
        
        if any(content.lower().startswith(s) for s in desc_starters):
            # Check if it has descriptive keywords (scene setting)
            has_desc_keywords = any(keyword in content.lower() for keyword in desc_keywords)
            # Check if it's substantial and not too action-heavy
            is_substantial = len(content) > 80
            has_actions = any(verb in content.lower() for verb in ['sedang', 'mengerjakan', 'melakukan', 'membuat'])
            
            if is_substantial and has_desc_keywords and not has_actions:
                return "description"
        
        return "narration"
    
    def apply_edits(self, edits: List[EditOperation], feedback: str, score: float = 0.0) -> Dict:
        """
        Apply edit operations to the canvas.
        
        Args:
            edits: List of EditOperations to apply
            feedback: The critique feedback that triggered these edits
            score: Quality score after this revision
            
        Returns:
            Dict with version number and changes applied
        """
        self.current_version += 1
        changes_applied = []
        
        # Sort edits by target_index (reverse for delete stability)
        # Use target_index directly instead of ID lookup for reliability
        sorted_edits = sorted(edits, key=lambda e: e.target_index if e.target_index >= 0 else 0, reverse=True)
        
        for edit in sorted_edits:
            # Use target_index directly if available, fallback to ID lookup
            if edit.target_index >= 0 and edit.target_index < len(self.paragraphs):
                para_idx = edit.target_index
            else:
                para_idx = self._find_paragraph_index(edit.target_id)
            
            if para_idx is None or para_idx >= len(self.paragraphs):
                logger.warning(f"Paragraph index {edit.target_index} not found, skipping edit")
                continue
            
            if edit.operation == EditType.REPLACE:
                old_content = self.paragraphs[para_idx].content
                old_type = self.paragraphs[para_idx].paragraph_type
                
                self.paragraphs[para_idx].content = edit.new_content
                self.paragraphs[para_idx].version = self.current_version
                self.paragraphs[para_idx].paragraph_type = self._detect_paragraph_type(edit.new_content)
                
                # Calculate change stats
                diff_ratio = self._calculate_similarity(old_content, edit.new_content)
                
                changes_applied.append({
                    "type": "replace",
                    "index": para_idx,
                    "paragraph_id": edit.target_id,
                    "old_content": old_content,
                    "new_content": edit.new_content,
                    "reason": edit.reason,
                    "similarity": diff_ratio
                })
                
            elif edit.operation == EditType.INSERT:
                new_para = Paragraph(
                    content=edit.new_content,
                    version=self.current_version,
                    paragraph_type=self._detect_paragraph_type(edit.new_content)
                )
                self.paragraphs.insert(para_idx + 1, new_para)
                
                changes_applied.append({
                    "type": "insert",
                    "index": para_idx + 1,
                    "paragraph_id": new_para.id,
                    "new_content": edit.new_content,
                    "reason": edit.reason
                })
                
            elif edit.operation == EditType.DELETE:
                deleted_content = self.paragraphs[para_idx].content
                del self.paragraphs[para_idx]
                
                changes_applied.append({
                    "type": "delete",
                    "index": para_idx,
                    "paragraph_id": edit.target_id,
                    "deleted_content": deleted_content,
                    "reason": edit.reason
                })
        
        # Save snapshot
        self._save_snapshot(feedback, changes_applied, score)
        
        # Print summary
        self._print_edit_summary(changes_applied)
        
        return {
            "version": self.current_version,
            "changes": changes_applied,
            "paragraph_count": len(self.paragraphs)
        }
    
    def _find_paragraph_index(self, para_id: str) -> Optional[int]:
        """Find paragraph index by ID"""
        for i, para in enumerate(self.paragraphs):
            if para.id == para_id:
                return i
        return None
    
    def _calculate_similarity(self, old: str, new: str) -> float:
        """Calculate text similarity ratio"""
        return difflib.SequenceMatcher(None, old, new).ratio() * 100
    
    def _save_snapshot(self, feedback: str, edits: List[dict], score: float):
        """Save current state as a revision snapshot"""
        snapshot = RevisionSnapshot(
            version=self.current_version,
            paragraphs=[p.to_dict() for p in self.paragraphs],
            timestamp=datetime.now().isoformat(),
            feedback=feedback,
            edits_applied=edits,
            score=score
        )
        self.history.append(snapshot)
    
    def _print_edit_summary(self, changes: List[dict]):
        """Print summary of applied edits"""
        if not changes:
            logger.info("No changes applied")
            return
            
        logger.info(f"CANVAS UPDATE - Version {self.current_version}:")
        logger.debug("─" * 50)
        
        for change in changes:
            if change["type"] == "replace":
                sim = change.get("similarity", 0)
                logger.info(f"Paragraph {change['index']+1} replaced ({sim:.1f}% similar)")
                logger.debug(f"Reason: {change['reason'][:60]}...")
            elif change["type"] == "insert":
                logger.info(f"Paragraph inserted after {change['index']}")
                logger.debug(f"Reason: {change['reason'][:60]}...")
            elif change["type"] == "delete":
                logger.info(f"Paragraph {change['index']+1} deleted")
                logger.debug(f"Reason: {change['reason'][:60]}...")
        
        logger.debug("─" * 50)
    
    def get_current_text(self, deduplicate: bool = False) -> str:
        """
        Reconstruct full story from paragraphs.
        
        Args:
            deduplicate: If True, remove duplicate paragraphs before returning (default: False)
        """
        if deduplicate and len(self.paragraphs) >= 2:
            removed = self._deduplicate_paragraphs()
            if removed > 0:
                logger.warning(f"Deduplicated {removed} paragraph(s) during text reconstruction")
        
        return "\n\n".join(p.content for p in self.paragraphs)
    
    def get_paragraph(self, index: int) -> Optional[Paragraph]:
        """Get paragraph by index"""
        if 0 <= index < len(self.paragraphs):
            return self.paragraphs[index]
        return None
    
    def get_paragraph_by_id(self, para_id: str) -> Optional[Paragraph]:
        """Get paragraph by ID"""
        for para in self.paragraphs:
            if para.id == para_id:
                return para
        return None
    
    def get_diff_text(self, version_a: int = None, version_b: int = None) -> str:
        """
        Generate readable diff between two versions.
        Default: compare previous version to current
        """
        if version_a is None:
            version_a = max(0, self.current_version - 1)
        if version_b is None:
            version_b = self.current_version
        
        # Get snapshots
        snap_a = self._get_snapshot(version_a)
        snap_b = self._get_snapshot(version_b)
        
        if not snap_a or not snap_b:
            return "Version not found"
        
        # Reconstruct texts
        text_a = "\n\n".join(p["content"] for p in snap_a.paragraphs)
        text_b = "\n\n".join(p["content"] for p in snap_b.paragraphs)
        
        # Generate diff
        diff_lines = list(difflib.unified_diff(
            text_a.splitlines(keepends=True),
            text_b.splitlines(keepends=True),
            fromfile=f"Version {version_a}",
            tofile=f"Version {version_b}",
            lineterm=""
        ))
        
        return "".join(diff_lines)
    
    def get_paragraph_diff(self, para_index: int, version_a: int = None, version_b: int = None) -> Dict:
        """
        Get diff for a specific paragraph between versions.
        Returns word-level changes.
        """
        if version_a is None:
            version_a = max(0, self.current_version - 1)
        if version_b is None:
            version_b = self.current_version
        
        snap_a = self._get_snapshot(version_a)
        snap_b = self._get_snapshot(version_b)
        
        if not snap_a or not snap_b:
            return {"error": "Version not found"}
        
        # Get paragraph content at each version
        content_a = snap_a.paragraphs[para_index]["content"] if para_index < len(snap_a.paragraphs) else ""
        content_b = snap_b.paragraphs[para_index]["content"] if para_index < len(snap_b.paragraphs) else ""
        
        # Word-level diff
        words_a = content_a.split()
        words_b = content_b.split()
        
        matcher = difflib.SequenceMatcher(None, words_a, words_b)
        
        changes = {
            "added": [],
            "removed": [],
            "similarity": matcher.ratio() * 100
        }
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                changes["added"].extend(words_b[j1:j2])
            elif tag == "delete":
                changes["removed"].extend(words_a[i1:i2])
            elif tag == "replace":
                changes["removed"].extend(words_a[i1:i2])
                changes["added"].extend(words_b[j1:j2])
        
        return changes
    
    def _get_snapshot(self, version: int) -> Optional[RevisionSnapshot]:
        """Get snapshot by version number"""
        for snap in self.history:
            if snap.version == version:
                return snap
        return None
    
    def get_revision_history_summary(self) -> List[Dict]:
        """Get summary of all revisions for display"""
        summaries = []
        
        for snap in self.history:
            edit_count = len(snap.edits_applied)
            edit_types = {}
            
            for edit in snap.edits_applied:
                t = edit.get("type", "unknown")
                edit_types[t] = edit_types.get(t, 0) + 1
            
            summaries.append({
                "version": snap.version,
                "timestamp": snap.timestamp,
                "feedback_preview": snap.feedback[:100] + "..." if len(snap.feedback) > 100 else snap.feedback,
                "edit_count": edit_count,
                "edit_types": edit_types,
                "score": snap.score,
                "paragraph_count": len(snap.paragraphs)
            })
        
        return summaries
    
    def get_paragraphs_with_metadata(self) -> List[Dict]:
        """Get all paragraphs with metadata for display"""
        return [
            {
                "index": i,
                "id": p.id,
                "content": p.content,
                "content_preview": p.content[:100] + "..." if len(p.content) > 100 else p.content,
                "type": p.paragraph_type,
                "version": p.version,
                "word_count": len(p.content.split())
            }
            for i, p in enumerate(self.paragraphs)
        ]
    
    def to_dict(self) -> dict:
        """Serialize canvas to dict for state storage"""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "current_version": self.current_version,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "history": [h.to_dict() for h in self.history]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StoryCanvas':
        """Deserialize canvas from dict"""
        canvas = cls()
        canvas.session_id = data.get("session_id", str(uuid.uuid4())[:12])
        canvas.title = data.get("title", "")
        canvas.current_version = data.get("current_version", 0)
        canvas.paragraphs = [Paragraph.from_dict(p) for p in data.get("paragraphs", [])]
        
        # Reconstruct history
        for h in data.get("history", []):
            canvas.history.append(RevisionSnapshot(
                version=h["version"],
                paragraphs=h["paragraphs"],
                timestamp=h["timestamp"],
                feedback=h["feedback"],
                edits_applied=h["edits_applied"],
                score=h.get("score", 0.0)
            ))
        
        return canvas


# Helper function to create edit operations
def create_edit(operation: str, target_id: str, new_content: str = "", reason: str = "", target_index: int = -1) -> EditOperation:
    """Helper to create EditOperation"""
    return EditOperation(
        operation=EditType(operation),
        target_id=target_id,
        target_index=target_index,
        new_content=new_content,
        reason=reason
    )


if __name__ == "__main__":
    # Test canvas
    test_story = """Di sebuah kantor startup bernama DigitalMaju, Budi bekerja sebagai QA Tester.

Budi sangat teliti dalam pekerjaannya. Setiap hari ia mengecek aplikasi satu per satu.

"Ini sangat membosankan," keluh Budi pada Rina, seniornya.

Rina tersenyum. "Bagaimana kalau kita buat robot pencicip?"

***

Budi belajar automation testing dengan semangat baru."""
    
    canvas = StoryCanvas()
    canvas.initialize_from_text(test_story)
    
    logger.info("=== Paragraphs ===")
    for p in canvas.get_paragraphs_with_metadata():
        logger.info(f"[{p['index']}] {p['type']}: {p['content_preview']}")
    
    # Test edit
    para_id = canvas.paragraphs[1].id
    edit = create_edit("replace", para_id, 
                       "Budi sangat teliti dan perfeksionis. Ia mengecek setiap detail dengan cermat.",
                       "Improve character description")
    
    canvas.apply_edits([edit], "Test revision", score=7.5)
    
    logger.info("=== After Edit ===")
    logger.info(canvas.get_current_text())
