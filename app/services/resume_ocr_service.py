"""
Resume OCR Service

Extracts text from resume files (PDF, DOCX, TXT, images).
Uses pdfplumber/python-docx for native text, GPT-4o-mini vision for OCR fallback.

Ported from Resumes/main.py TextExtractor class.
"""

import os
import io
import re
import base64
import logging
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

from openai import OpenAI, RateLimitError, APIError
from PIL import Image, ImageDraw, ImageFont

from app.config import settings

logger = logging.getLogger(__name__)

# OCR Configuration
OCR_SYSTEM_PROMPT = """You are an expert document OCR assistant.
Extract all text from the image exactly as shown, preserving structure.
For resumes, maintain section headers, bullet points, and formatting.
Output plain text only, no markdown."""

MAX_RETRIES = 3
PAGE_GAP_SECONDS = 0.5


class ResumeOCRService:
    """
    Text extraction from resume files with OCR fallback.
    
    Supports: PDF, DOCX, TXT, PNG, JPG
    Uses: pdfplumber, python-docx, GPT-4o-mini vision
    """

    def __init__(self, max_dim: int = 2048):
        """
        Initialize OCR service.
        
        Args:
            max_dim: Maximum image dimension for OCR
        """
        self.max_dim = max_dim
        self.ocr_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.ocr_model = settings.RESUME_OCR_MODEL

    def extract_text(self, file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from file, using OCR if native extraction fails.
        
        Args:
            file_path: Path to the resume file
            
        Returns:
            Tuple of (extracted_text, stats_dict)
        """
        start_time = time.time()
        file_path = Path(file_path)
        
        stats = {
            "method": None,  # native_pdf, native_docx, native_txt, openai_ocr
            "ocr_used": False,
            "duration_seconds": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "pages": 0,
            "error": None,
        }

        # Try native extraction first
        text, method = self._extract_native(file_path)
        
        # Map method names to database-friendly values
        method_mapping = {
            "pdfplumber": "native_pdf",
            "docx": "native_docx", 
            "txt": "native_txt",
            "image": "openai_ocr",
        }
        stats["method"] = method_mapping.get(method.split("-")[0], method)

        # Check if extraction was successful
        if text and len(text.strip()) >= 50 and self._looks_like_resume(text):
            logger.info(f"Native extraction successful: {stats['method']}")
            stats["duration_seconds"] = round(time.time() - start_time, 3)
            return text, stats

        # Fall back to OCR
        logger.info(f"Native extraction insufficient, trying OCR for {file_path.name}")
        text, ocr_stats = self._extract_with_ocr(file_path)
        
        stats["method"] = "openai_ocr"
        stats["ocr_used"] = True
        stats["input_tokens"] = ocr_stats.get("prompt_tokens", 0)
        stats["output_tokens"] = ocr_stats.get("completion_tokens", 0)
        stats["total_tokens"] = ocr_stats.get("total_tokens", 0)
        stats["pages"] = ocr_stats.get("pages", 0)
        
        # Calculate OCR cost (gpt-4o-mini vision pricing)
        stats["cost_usd"] = self._calculate_ocr_cost(
            stats["input_tokens"], 
            stats["output_tokens"],
            self.ocr_model
        )

        if not text:
            stats["error"] = "OCR failed or returned empty text"

        stats["duration_seconds"] = round(time.time() - start_time, 3)
        logger.info(f"OCR complete: {stats['pages']} pages, ${stats['cost_usd']:.4f}")
        return text, stats
    
    def _calculate_ocr_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate OCR cost based on model pricing."""
        # gpt-4o-mini vision pricing (per 1M tokens)
        pricing = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
        }
        rates = pricing.get(model, pricing["gpt-4o-mini"])
        cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
        return round(cost, 6)

    def _extract_native(self, file_path: Path) -> Tuple[str, str]:
        """Try native text extraction."""
        ext = file_path.suffix.lower()
        kind = self._detect_file_type(file_path)

        if kind == "pdf" or ext == ".pdf":
            text = self._extract_pdf(file_path)
            return text, "pdfplumber" if text else "pdfplumber-empty"

        if ext == ".docx" and kind == "zip":
            text = self._extract_docx(file_path)
            return text, "docx" if text else "docx-empty"

        if ext == ".txt":
            text = self._extract_txt(file_path)
            return text, "txt" if text else "txt-empty"

        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            return "", "image"

        return "", "unsupported"

    def _extract_pdf(self, file_path: Path) -> str:
        """Extract text from PDF using pdfplumber."""
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed")
            return ""

        try:
            texts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages[:200]:  # Limit pages
                    text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                    if text:
                        texts.append(text)
            return "\n".join(texts).strip()
        except Exception as e:
            logger.debug(f"pdfplumber failed: {e}")
            return ""

    def _extract_docx(self, file_path: Path) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            from docx import Document
        except ImportError:
            logger.warning("python-docx not installed")
            return ""

        try:
            doc = Document(file_path)
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paras).strip()
        except Exception as e:
            logger.debug(f"python-docx failed: {e}")
            return ""

    def _extract_txt(self, file_path: Path) -> str:
        """Extract text from plain text file."""
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            return ""

    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type from header bytes."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
        except Exception:
            return "unknown"

        if header.startswith(b"%PDF-"):
            return "pdf"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if header.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if header.startswith(b"PK\x03\x04"):
            return "zip"  # docx container
        if header.startswith(b"\xd0\xcf\x11\xe0"):
            return "doc"  # legacy doc
        return "unknown"

    def _looks_like_resume(self, text: str) -> bool:
        """Check if text contains typical resume content."""
        patterns = [
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",  # Email
            r"(\+?\d[\d\-\s]{7,}\d)",  # Phone
            r"\b(resume|curriculum\s*vitae|cv|experience|education|skills)\b",
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _extract_with_ocr(self, file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """Extract text using OCR (GPT-4o-mini vision)."""
        stats = {"pages": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Convert file to images
        images, error = self._file_to_images(file_path)
        if error or not images:
            return "", stats

        stats["pages"] = len(images)
        texts = []

        for i, img in enumerate(images):
            # Rate limiting
            if i > 0:
                time.sleep(PAGE_GAP_SECONDS)

            # Encode image
            buf = io.BytesIO()
            img = img.convert("RGB")
            img.thumbnail((self.max_dim, self.max_dim))
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            data_uri = f"data:image/png;base64,{b64}"

            # OCR via API
            for attempt in range(MAX_RETRIES):
                try:
                    resp = self.ocr_client.chat.completions.create(
                        model=self.ocr_model,
                        messages=[
                            {"role": "system", "content": OCR_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Transcribe page {i+1}/{len(images)}"},
                                    {"type": "image_url", "image_url": {"url": data_uri, "detail": "high"}},
                                ],
                            },
                        ],
                        temperature=0,
                        timeout=180.0,
                    )

                    content = (resp.choices[0].message.content or "").strip()
                    if content:
                        texts.append(content)

                    # Track usage
                    if hasattr(resp, "usage") and resp.usage:
                        stats["prompt_tokens"] += resp.usage.prompt_tokens or 0
                        stats["completion_tokens"] += resp.usage.completion_tokens or 0
                        stats["total_tokens"] += resp.usage.total_tokens or 0

                    break

                except RateLimitError:
                    time.sleep(2 ** attempt)
                except APIError as e:
                    if hasattr(e, "status_code") and 500 <= e.status_code < 600:
                        time.sleep(2 ** attempt)
                    else:
                        break
                except Exception as e:
                    logger.error(f"OCR error on page {i+1}: {e}")
                    break

        return "\n\n".join(texts), stats

    def _file_to_images(self, file_path: Path) -> Tuple[List[Image.Image], Optional[str]]:
        """Convert file to PIL Images for OCR."""
        ext = file_path.suffix.lower()
        kind = self._detect_file_type(file_path)

        # PDF - convert pages to images
        if kind == "pdf" or ext == ".pdf":
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(file_path, dpi=200, timeout=120)
                return images, None if images else "PDF produced zero pages"
            except Exception as e:
                return [], f"PDF conversion failed: {e}"

        # Direct image files
        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            try:
                with Image.open(file_path) as img:
                    return [img.convert("RGB").copy()], None
            except Exception as e:
                return [], f"Image open failed: {e}"

        # DOCX - extract text and convert to image
        if ext == ".docx":
            text = self._extract_docx(file_path)
            if len(text) >= 40:
                return self._text_to_images(text), None
            return [], "DOCX has no extractable text"

        # TXT - convert to image
        if ext == ".txt":
            text = self._extract_txt(file_path)
            if text:
                return self._text_to_images(text), None
            return [], "TXT is empty"

        return [], f"Unsupported file type: {ext}"

    def _text_to_images(self, text: str, max_chars: int = 2500) -> List[Image.Image]:
        """Convert long text to multiple images."""
        # Split into chunks
        chunks = []
        current, count = [], 0
        for line in text.splitlines():
            if count + len(line) + 1 > max_chars and current:
                chunks.append("\n".join(current))
                current, count = [], 0
            current.append(line)
            count += len(line) + 1
        if current:
            chunks.append("\n".join(current))

        # Convert each chunk to image
        images = []
        for chunk in chunks:
            img = self._render_text_to_image(chunk)
            images.append(img)
        return images

    def _render_text_to_image(self, text: str) -> Image.Image:
        """Render text to an image."""
        padding = 20
        font = self._get_font()
        lines = text.splitlines() or [""]

        # Calculate dimensions
        dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        line_heights = []
        max_width = 0
        for line in lines:
            bbox = dummy.textbbox((0, 0), line, font=font)
            max_width = max(max_width, bbox[2])
            line_heights.append(bbox[3] - bbox[1])

        width = max(200, max_width + 2 * padding)
        height = max(100, sum(line_heights) + len(lines) * 5 + 2 * padding)

        # Create image
        img = Image.new("RGB", (int(width), int(height)), "white")
        draw = ImageDraw.Draw(img)
        y = padding
        for i, line in enumerate(lines):
            draw.text((padding, y), line, font=font, fill="black")
            y += line_heights[i] + 5

        return img

    def _get_font(self) -> ImageFont.FreeTypeFont:
        """Get a font for text rendering."""
        for name in ["DejaVuSans.ttf", "arial.ttf"]:
            try:
                return ImageFont.truetype(name, 16)
            except Exception:
                continue
        return ImageFont.load_default()
