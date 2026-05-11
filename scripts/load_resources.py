"""
Script para cargar recursos (PDFs + videos de YouTube) a Supabase con embeddings.

Uso:
    python scripts/load_resources.py

Requisitos:
    - PDFs en resources/pdfs/
    - URLs de YouTube en resources/videos.txt (una por linea, # para comentarios)
    - Variables de entorno configuradas (.env)
"""

import os
import sys
import uuid
import time
import re

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fitz  # PyMuPDF
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

CHUNK_SIZE = 800  # words per chunk
CHUNK_OVERLAP = 100  # overlap words between chunks
EMBEDDING_MODEL = "gemini-embedding-001"

db = create_client(SUPABASE_URL, SUPABASE_KEY)
genai_client = genai.Client(api_key=GEMINI_API_KEY)


def generate_embedding(text: str) -> list[float]:
    """Generate embedding using Gemini gemini-embedding-001 with 768 dimensions."""
    from google.genai import types as genai_types
    response = genai_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text[:2000],  # limit to avoid token limits
        config=genai_types.EmbedContentConfig(output_dimensionality=768),
    )
    return response.embeddings[0].values


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
    return chunks


def extract_subject_from_filename(filename: str) -> str:
    """Try to guess subject from filename."""
    name = os.path.splitext(filename)[0]
    # Replace underscores and hyphens with spaces
    name = name.replace("_", " ").replace("-", " ")
    return name


def process_pdf(filepath: str, subject_override: str = None) -> list[dict]:
    """Extract text from PDF and split into chunks."""
    filename = os.path.basename(filepath)
    subject = subject_override or extract_subject_from_filename(filename)

    print(f"  Procesando PDF: {filename}", flush=True)
    doc = fitz.open(filepath)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    if not full_text.strip():
        print(f"    ADVERTENCIA: PDF vacio o no se pudo extraer texto: {filename}")
        return []

    chunks = chunk_text(full_text)
    print(f"    {len(chunks)} chunks generados")

    resources = []
    for i, chunk in enumerate(chunks):
        resources.append({
            "title": f"{subject} (parte {i + 1})",
            "subject": subject,
            "topics": [],
            "content": chunk,
            "resource_type": "pdf",
            "url": None,
            "source_file": filename,
        })
    return resources


def extract_video_id(url: str) -> str | None:
    """Extract video ID from YouTube URL."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_playlist_video_ids(url: str) -> list[str]:
    """Extract video IDs from a YouTube playlist URL."""
    try:
        from pytube import Playlist
        playlist = Playlist(url)
        ids = []
        for video_url in playlist.video_urls:
            vid = extract_video_id(video_url)
            if vid:
                ids.append(vid)
        return ids
    except Exception as e:
        print(f"    Error extrayendo playlist (intentando con regex): {e}")
        # Fallback: try to extract playlist ID and use youtube_transcript_api
        match = re.search(r'list=([a-zA-Z0-9_-]+)', url)
        if match:
            print(f"    Playlist ID: {match.group(1)} - necesitas pytube para extraer videos")
        return []


def process_video(url: str, context: str = "") -> list[dict]:
    """Get YouTube transcript and create resource chunks."""
    video_id = extract_video_id(url)
    if not video_id:
        print(f"    No se pudo extraer video ID de: {url}")
        return []

    print(f"  Procesando video: {video_id}")
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try Spanish first, then English, then any
        try:
            transcript = transcript_list.find_transcript(['es'])
        except Exception:
            try:
                transcript = transcript_list.find_transcript(['en'])
            except Exception:
                transcript = transcript_list.find_generated_transcript(['es', 'en'])

        entries = transcript.fetch()
        full_text = " ".join(
            entry.get("text", entry) if isinstance(entry, dict) else str(entry)
            for entry in entries
        )

        if not full_text.strip():
            print(f"    Transcripcion vacia para {video_id}")
            return []

        chunks = chunk_text(full_text)
        print(f"    {len(chunks)} chunks generados")

        subject = context if context else "General"
        resources = []
        for i, chunk in enumerate(chunks):
            resources.append({
                "title": f"Video: {subject} (parte {i + 1})",
                "subject": subject,
                "topics": [],
                "content": chunk,
                "resource_type": "video",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "source_file": None,
            })
        return resources

    except Exception as e:
        print(f"    Error obteniendo transcripcion de {video_id}: {e}")
        return []


def upload_resources(resources: list[dict]):
    """Generate embeddings and upload to Supabase."""
    total = len(resources)
    uploaded = 0
    errors = 0

    for i, res in enumerate(resources):
        try:
            print(f"  [{i + 1}/{total}] Embedding: {res['title'][:50]}...", flush=True)
            embedding = generate_embedding(res["content"])

            payload = {
                "id": str(uuid.uuid4()),
                "title": res["title"],
                "subject": res["subject"],
                "topics": res["topics"],
                "content": res["content"][:5000],  # limit content size
                "embedding": embedding,
                "resource_type": res["resource_type"],
                "url": res["url"],
            }

            db.table("resources").upsert(payload).execute()
            uploaded += 1

            # Rate limiting for Gemini free tier
            time.sleep(4)  # ~15 req/min safe margin

        except Exception as e:
            err_str = str(e)
            print(f"    ERROR: {err_str[:100]}", flush=True)
            errors += 1
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                print("    Rate limited, esperando 60s...", flush=True)
                time.sleep(60)

    return uploaded, errors


def main():
    print("=" * 60)
    print("StudyBot - Carga de recursos")
    print("=" * 60)

    all_resources = []

    # 1. Process PDFs (supports subdirectories as subject names)
    pdf_dir = os.path.join(os.path.dirname(__file__), "..", "resources", "pdfs")
    if os.path.exists(pdf_dir):
        pdf_files = []
        # Walk through subdirectories
        for root, dirs, files in os.walk(pdf_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    filepath = os.path.join(root, f)
                    # Use subfolder name as subject if in a subdirectory
                    rel_path = os.path.relpath(root, pdf_dir)
                    subject = rel_path if rel_path != "." else None
                    pdf_files.append((filepath, subject))

        print(f"\n📄 Encontrados {len(pdf_files)} PDFs")
        for filepath, subject in sorted(pdf_files):
            resources = process_pdf(filepath, subject)
            all_resources.extend(resources)
    else:
        print("\n⚠️  No se encontro carpeta resources/pdfs/")

    # 2. Process YouTube videos from CSV
    csv_file = os.path.join(os.path.dirname(__file__), "..", "resources", "tutoriales_apoyo.csv")
    videos_file = os.path.join(os.path.dirname(__file__), "..", "resources", "videos.txt")

    if os.path.exists(csv_file):
        import csv
        print(f"\n🎥 Procesando videos desde CSV", flush=True)
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                category = row.get("Categoria", "General").strip()
                url = row.get("URL", "").strip()
                if not url:
                    continue
                if "playlist" in url.lower() or "list=" in url:
                    print(f"  Playlist detectada ({category}): {url}", flush=True)
                    video_ids = get_playlist_video_ids(url)
                    for vid in video_ids:
                        vid_url = f"https://www.youtube.com/watch?v={vid}"
                        resources = process_video(vid_url, category)
                        all_resources.extend(resources)
                else:
                    resources = process_video(url, category)
                    all_resources.extend(resources)
    elif os.path.exists(videos_file):
        print(f"\n🎥 Procesando videos de YouTube")
        current_context = ""
        with open(videos_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    current_context = line[1:].strip()
                    print(f"\n  Seccion: {current_context}")
                    continue

                if "playlist" in line.lower():
                    print(f"  Playlist detectada: {line}")
                    video_ids = get_playlist_video_ids(line)
                    for vid in video_ids:
                        url = f"https://www.youtube.com/watch?v={vid}"
                        resources = process_video(url, current_context)
                        all_resources.extend(resources)
                else:
                    resources = process_video(line, current_context)
                    all_resources.extend(resources)
    else:
        print("\n⚠️  No se encontro resources/videos.txt")

    # 3. Upload everything
    if not all_resources:
        print("\n❌ No se encontraron recursos para cargar")
        return

    print(f"\n📤 Subiendo {len(all_resources)} chunks a Supabase...")
    uploaded, errors = upload_resources(all_resources)

    print(f"\n{'=' * 60}")
    print(f"✅ Completado: {uploaded} chunks subidos, {errors} errores")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
