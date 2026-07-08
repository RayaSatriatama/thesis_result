# Story Generation API

The Story Agent exposes a comprehensive API for generating educational stories with agentic workflows.

## Endpoints

### `POST /workflow/generate`

Initiates a full story generation workflow, including planning, writer selection, drafting, and critique. The response is an SSE (Server-Sent Events) stream.

**URL**: `/workflow/generate`
**Method**: `POST`
**Content-Type**: `application/json`

#### Request Body (`WorkflowRequest`)

| Field | Type | Description | Default |
|---|---|---|---|
| `prompt` | string | **Required**. The main story prompt or topic. | - |
| `target_age` | string | Target audience age (e.g., "7-9 tahun"). | "Anak-anak" |
| `language` | string | Language code ("id", "en"). | "id" |
| `story_length` | string | Desired length (e.g., "3 paragraf", "pendek"). | "sedang" |
| `active_writers` | list[str] | Force specific writers (e.g., `["text", "image"]`). | `None` (AI decides) |

**Example Request:**

```json
{
  "prompt": "Sebuah cerita tentang kancil yang belajar coding",
  "target_age": "8-10 tahun",
  "story_length": "3 paragraf",
  "language": "id"
}
```

#### Response (SSE Stream)

The API returns a stream of events. Each event follows the format:

```
event: [AGENT]::[ACTION]
data: {"key": "value", ...}
```

**Common Events:**

- `WORKFLOW::MULAI`: Workflow started.
- `PERENCANA::MERINCIKAN`: Planner has finished outlines.
- `PENULIS::SELESAI`: Writer has finished a draft.
- `GAMBAR::SELESAI`: Image generation complete (if enabled).
- `WORKFLOW::SELESAI`: Workflow complete with final story.

**Example Client (JavaScript):**

```javascript
const response = await fetch('/workflow/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ prompt: "Cerita coding" })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value);
  console.log(chunk); // Parse SSE events here
}
```
