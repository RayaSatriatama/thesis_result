"""
NPC Agent Registry — maps LangGraph nodes to NPC identities and Indonesian dialogue messages.

Each NPC represents a backend agent as a story character with:
- ID and display name (Indonesian)
- Avatar key (for sprite lookup; uses colored circles as placeholder until sprites are extracted)
- Theme color (hex)
- Contextual Indonesian dialogue for start/end events

Usage:
    from apps.api.npc_registry import get_npc, build_npc_message

    npc = get_npc("planning")
    msg = build_npc_message("planning", "start", {})
"""

from typing import Dict, List

# ---------------------------------------------------------------------------
# NPC metadata table — keyed by LangGraph node name
# ---------------------------------------------------------------------------
_NPC_MAP: Dict[str, dict] = {
    "supervisor_node": {
        "id": "supervisor",
        "name": "Pak Pengawas",
        "avatar": "supervisor",
        "color": "#6366F1",
    },
    "planning": {
        "id": "planner",
        "name": "Bu Perencana",
        "avatar": "planner",
        "color": "#8B5CF6",
    },
    "planning_hitl_gate": {
        "id": "planner",
        "name": "Bu Perencana",
        "avatar": "planner",
        "color": "#8B5CF6",
    },
    "research": {
        "id": "researcher",
        "name": "Si Peneliti",
        "avatar": "researcher",
        "color": "#10B981",
    },
    "writer_text": {
        "id": "writer_text",
        "name": "Sang Penulis",
        "avatar": "writer_text",
        "color": "#F59E0B",
    },
    "writer_diagram": {
        "id": "writer_diagram",
        "name": "Data Visualizer",
        "avatar": "writer_diagram",
        "color": "#EC4899",
    },
    "writer_image": {
        "id": "writer_image",
        "name": "Ilustrator",
        "avatar": "writer_image",
        "color": "#EF4444",
    },
    "writer_director": {
        "id": "director",
        "name": "Sutradara",
        "avatar": "director",
        "color": "#3B82F6",
    },
    "critique": {
        "id": "critic",
        "name": "Kritikus",
        "avatar": "critic",
        "color": "#6B7280",
    },
    # System/infrastructure nodes — use neutral system NPC
    "merge_writers": {
        "id": "system",
        "name": "Sistem",
        "avatar": "system",
        "color": "#374151",
    },
    "merge_production": {
        "id": "system",
        "name": "Sistem",
        "avatar": "system",
        "color": "#374151",
    },
    "production_gate": {
        "id": "system",
        "name": "Sistem",
        "avatar": "system",
        "color": "#374151",
    },
    "revision_prep": {
        "id": "system",
        "name": "Sistem",
        "avatar": "system",
        "color": "#374151",
    },
    "hitl_gate": {
        "id": "system",
        "name": "Sistem",
        "avatar": "system",
        "color": "#374151",
    },
    "qa_response_node": {
        "id": "supervisor",
        "name": "Pak Pengawas",
        "avatar": "supervisor",
        "color": "#6366F1",
    },
    "finalize": {
        "id": "system",
        "name": "Sistem",
        "avatar": "system",
        "color": "#374151",
    },
    "ingest_sources": {
        "id": "system",
        "name": "Sistem",
        "avatar": "system",
        "color": "#374151",
    },
}

_DEFAULT_NPC: dict = {"id": "system", "name": "Sistem", "avatar": "system", "color": "#374151"}


def get_npc(node_name: str) -> dict:
    """Return a copy of NPC metadata for the given LangGraph node name."""
    return dict(_NPC_MAP.get(node_name, _DEFAULT_NPC))


def list_unique_npc_personas() -> List[dict]:
    """Deduplicated NPC rows by stable id (for Story Studio / meta API)."""
    seen: Dict[str, dict] = {}
    for meta in _NPC_MAP.values():
        aid = str(meta.get("id") or "npc")
        if aid in seen:
            continue
        seen[aid] = dict(meta)
    return list(seen.values())


# ---------------------------------------------------------------------------
# Start messages (emitted on on_chain_start / MULAI events)
# ---------------------------------------------------------------------------
_START_MESSAGES: Dict[str, str] = {
    "supervisor_node":    "Biarkan saya baca permintaan ini dengan cermat dulu ya... saya ingin memastikan kita memilih pendekatan yang paling tepat.",
    "planning":           "Oke, izin mulai bekerja! Saya akan merancang struktur cerita, memilih karakter, dan menentukan alur yang paling sesuai dengan tujuan pembelajaran.",
    "planning_hitl_gate": "Hei, minta sebentar perhatiannya ya! Sebelum kita lanjut, ada baiknya Anda meninjau rencana ini dulu—siapa tahu ada yang perlu diubah.",
    "research":           "Sip, saya mulai menggali referensi! Akan saya cari informasi tentang tokoh, latar, dan nilai moral yang bisa memperkaya cerita ini.",
    "writer_text":        "Wah, saatnya berkreasi! Sudah ada rencana yang matang dan riset yang lengkap—tinggal saya tuangkan jadi cerita yang mengalir dan menyentuh hati.",
    "writer_diagram":     "Oke, saya akan mulai bikin diagram alur ceritanya! Ini penting supaya pembaca—terutama anak-anak—bisa memahami urutan kejadian dengan lebih mudah.",
    "writer_image":       "Waktunya melukis! Saya akan buat beberapa ilustrasi yang cerah dan penuh warna untuk menghidupkan cerita ini.",
    "writer_director":    "Action! Saatnya mengubah cerita jadi skrip yang bisa dimainkan. Saya akan bikin adegan-adegan dengan dialog yang natural dan mudah dipahami.",
    "merge_writers":      "Semua komponen sudah terkumpul. Sedang saya gabungkan teks, diagram, ilustrasi, dan skrip jadi satu paket cerita yang lengkap...",
    "merge_production":   "Menyatukan semua hasil produksi...",
    "production_gate":    "Sebentar, saya periksa kelengkapan semua komponen dulu sebelum lanjut.",
    "critique":           "Hmm, saatnya saya baca dengan kritis. Saya akan periksa koherensi naratif, kesesuaian pesan moral, dan apakah ceritanya sudah benar-benar cocok untuk target usia.",
    "revision_prep":      "Ada beberapa hal yang perlu diperbaiki. Saya siapkan daftar revisinya dulu.",
    "hitl_gate":          "Cerita sudah melewati semua tahap. Saya tunggu persetujuan Anda sebelum finalisasi ya.",
    "qa_response_node":   "Oh, ada pertanyaan! Biarkan saya pikirkan jawaban yang paling tepat dan informatif.",
    "finalize":           "Hampir selesai! Saya sedang merapikan semua bagian cerita untuk diserahkan dalam kondisi terbaik.",
    "ingest_sources":     "Sedang memuat sumber-sumber referensi tambahan yang relevan...",
}


def _build_end_message(node_name: str, event_data: dict) -> str:
    """Build a contextual end-of-node message using output data already in event_data."""
    if node_name == "supervisor_node":
        next_step = event_data.get("next_step", "")
        _labels = {
            "planning":        "Bu Perencana",
            "research":        "Si Peneliti",
            "writer_text":     "Sang Penulis",
            "writer_director": "Sutradara",
            "critique":        "Kritikus",
            "finalize":        "tahap finalisasi",
        }
        label = _labels.get(next_step, next_step or "tim berikutnya")
        return f"Sudah jelas! Ini permintaan yang menarik. Saya serahkan ke {label} untuk ditangani lebih lanjut."

    if node_name == "qa_response_node":
        return "Semoga jawaban itu membantu! Kalau ada pertanyaan lain, jangan ragu untuk bertanya ya."

    if node_name == "planning":
        writers = event_data.get("active_writers", [])
        chars = event_data.get("characters", 0)
        character_names = event_data.get("character_names", [])
        moral = event_data.get("moral_message", "")
        draft_title = event_data.get("draft_title", "")
        writer_name_map = {
            "writer_text":     "Sang Penulis",
            "writer_diagram":  "Data Visualizer",
            "writer_image":    "Ilustrator",
            "writer_director": "Sutradara",
        }
        title_note = f' Judulnya: "{draft_title}".' if draft_title else ""
        moral_note = f' Pesan moral: "{moral}".' if moral else ""
        if character_names:
            names_str = ", ".join(str(n) for n in character_names)
            if writers:
                labels = [writer_name_map.get(str(w), str(w)) for w in writers[:4]]
                return f"Rencana cerita sudah matang!{title_note} Karakter utama: {names_str}.{moral_note} Saya putuskan untuk melibatkan {', '.join(labels)}. Mari mulai!"
            return f"Rencana selesai!{title_note} Karakter: {names_str}.{moral_note} Alur cerita sudah terdefinisi dengan jelas."
        if writers:
            labels = [writer_name_map.get(str(w), str(w)) for w in writers[:4]]
            char_note = f" dengan {chars} karakter utama" if chars else ""
            return f"Rencana cerita sudah matang{char_note}!{title_note}{moral_note} Saya putuskan untuk melibatkan {', '.join(labels)}. Mari kita mulai!"
        if chars:
            return f"Rencana selesai! Ada {chars} karakter utama yang sudah ditentukan beserta alur ceritanya.{title_note}{moral_note}"
        return "Rencana cerita sudah matang dan siap dieksekusi!"

    if node_name == "planning_hitl_gate":
        return "Saya sudah menuangkan ide terbaik saya ke dalam rencana ini. Silakan dicek—masukan Anda sangat berarti sebelum kita lanjut!"

    if node_name == "research":
        chars = event_data.get("chars", 0)
        source_count = event_data.get("source_count", 0)
        if chars or source_count:
            words = chars // 5 if chars else 0
            word_note = f"sekitar {words} kata catatan" if words else "catatan riset"
            source_note = f" dari {source_count} sumber" if source_count else ""
            return f"Riset selesai! Saya berhasil mengumpulkan {word_note}{source_note}—mulai dari latar belakang tokoh, konteks budaya, hingga nilai-nilai yang bisa diangkat. Semuanya siap untuk tim penulis!"
        return "Riset selesai! Semua informasi yang relevan sudah terkumpul dan siap digunakan."

    if node_name == "writer_text":
        words = event_data.get("words", 0)
        draft_title = event_data.get("draft_title", "")
        is_revision = event_data.get("is_revision", False)
        title_note = f' "{draft_title}"' if draft_title else ""
        draft_label = "hasil revisi" if is_revision else "draf pertama"
        if words:
            return f"Selesai! {draft_label.capitalize()}{title_note} sudah jadi—{words} kata yang (semoga) mengalir dengan lancar. Ada pembukaan yang menarik, konflik yang tegang, dan resolusi yang memuaskan. Giliran tim lain sekarang!"
        return f"{'Revisi' if is_revision else 'Draf'} cerita sudah jadi!{' Judul: ' + draft_title if draft_title else ''} Semoga alurnya mengalir dengan baik."

    if node_name == "writer_diagram":
        if event_data.get("has_diagram"):
            diagram_type = event_data.get("diagram_type", "")
            diagram_title = event_data.get("diagram_title", "")
            type_note = f" ({diagram_type})" if diagram_type else ""
            title_note = f': "{diagram_title}"' if diagram_title else ""
            return f"Diagram{title_note} selesai dibuat{type_note}! Alurnya mudah dipahami—tidak terlalu ramai tapi cukup informatif untuk membantu pembaca mengikuti jalan cerita."
        return "Setelah saya cermati, cerita ini sudah cukup jelas tanpa diagram tambahan. Tidak perlu dipaksakan!"

    if node_name == "writer_image":
        count = event_data.get("image_count", 0)
        if count:
            return f"Selesai! {count} ilustrasi sudah jadi—warna-warnanya cerah dan dibuat khusus agar cocok untuk anak-anak. Semoga bisa membuat cerita semakin hidup!"
        return "Proses ilustrasi selesai."

    if node_name == "writer_director":
        count = event_data.get("scene_count", 0)
        if count:
            return f"Skrip selesai dengan {count} adegan! Dialog-dialognya sudah saya sesuaikan supaya terasa natural, lucu, dan tetap mendidik. Siap untuk dipentaskan!"
        return "Skrip dialog sudah selesai—semua dialog terasa natural dan sesuai karakter."

    if node_name == "critique":
        score = event_data.get("quality_score", 0)
        decision = event_data.get("decision", "")
        edu_score = event_data.get("edu_score", 0)
        coherence_score = event_data.get("coherence_score", 0)
        issues_count = event_data.get("coherence_issues_count", 0)
        _decision_labels = {
            "approve": "layak dilanjutkan",
            "revise":  "butuh sedikit perbaikan",
            "reject":  "perlu ditulis ulang dari awal",
        }
        decision_label = _decision_labels.get(decision, "evaluasi selesai")
        issues_note = f" Ada {issues_count} catatan koherensi yang perlu diperhatikan." if issues_count else " Koherensi narasi terlihat solid."
        if edu_score and coherence_score:
            return (
                f"Evaluasi selesai! Skor keseluruhan: {score}/5 "
                f"(edukasi: {edu_score:.1f}/5, koherensi: {coherence_score:.1f}/10) — "
                f"cerita ini {decision_label}.{issues_note}"
            )
        if score:
            return f"Evaluasi selesai! Skor: {score}/5 — cerita ini {decision_label}. Narasi mengalir, pesan moral jelas, dan karakter konsisten. Pekerjaan yang bagus dari tim!"
        return f"Evaluasi selesai — cerita ini {decision_label}."

    if node_name == "merge_writers":
        return "Semua komponen berhasil disatukan! Teks, diagram, ilustrasi, dan skrip kini sudah menjadi satu paket cerita yang lengkap."

    if node_name == "finalize":
        elapsed = event_data.get("elapsed_time", 0)
        if elapsed:
            return f"Cerita final sudah siap dan rapi! Dibutuhkan {elapsed} detik untuk menghasilkan satu cerita lengkap dengan semua pelengkapnya. Selamat menikmati!"
        return "Cerita final sudah siap dan rapi untuk diserahkan!"

    if node_name == "hitl_gate":
        return "Cerita sudah melalui semua tahap produksi. Saya tunggu lampu hijau dari Anda sebelum kita finalisasi ya."

    return "Tugas selesai."


def build_npc_message(node_name: str, event_type: str, event_data: dict) -> str:
    """
    Build an Indonesian dialogue message for the given NPC agent event.

    Args:
        node_name:  LangGraph node name (e.g. "supervisor_node", "planning").
        event_type: ``"start"`` (on_chain_start / MULAI) or ``"end"`` (on_chain_end).
        event_data: The event payload dict — used by end messages to inject dynamic values
                    such as word counts, scores, and scene counts.

    Returns:
        Indonesian dialogue string from the NPC's perspective.
    """
    if event_type == "start":
        return _START_MESSAGES.get(node_name, "Saya mulai bekerja...")
    return _build_end_message(node_name, event_data)
