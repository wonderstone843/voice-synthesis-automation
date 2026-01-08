#!/usr/bin/env python3
"""
Voice Synthesis Automation

Production-grade voice synthesis using ElevenLabs API.
Handles batch processing, long-form content, and multi-voice scripts.

Author: Joshua Penn
"""

import os
import re
import json
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

from elevenlabs import ElevenLabs

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AudioResult:
    """Result from voice synthesis."""
    path: Path
    duration: float
    characters: int
    cost: float
    voice: str


@dataclass
class VoiceConfig:
    """Voice configuration."""
    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0


class VoiceSynthError(Exception):
    """Voice synthesis error with context."""
    def __init__(self, message: str, is_rate_limit: bool = False, is_invalid_voice: bool = False, voice_id: str = None):
        super().__init__(message)
        self.is_rate_limit = is_rate_limit
        self.is_invalid_voice = is_invalid_voice
        self.voice_id = voice_id


class VoiceSynthesizer:
    """
    Production voice synthesizer with ElevenLabs.

    Features:
    - Batch processing with rate limiting
    - Long-form text with automatic chunking
    - Multi-voice script parsing
    - Cost tracking and optimization
    """

    # Voice presets
    VOICES = {
        "narrator": VoiceConfig(voice_id="pNInz6obpgDQGcFmaJgB", stability=0.7, similarity_boost=0.8),
        "dramatic": VoiceConfig(voice_id="ErXwobaYiN019PkySvjV", stability=0.5, style=0.3),
        "energetic": VoiceConfig(voice_id="VR6AewLTigWG4xSOukaG", stability=0.4, style=0.5),
        "calm": VoiceConfig(voice_id="21m00Tcm4TlvDq8ikWAM", stability=0.8, similarity_boost=0.9),
        "commentator": VoiceConfig(voice_id="TxGEqnHWrfWFTfGW9XjX", stability=0.6),
    }

    MAX_CHARS = 5000
    COST_PER_CHAR = 0.00003
    RATE_LIMIT_DELAY = 0.5

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with ElevenLabs API key."""
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY required")

        self.client = ElevenLabs(api_key=self.api_key)
        self.total_cost = 0.0
        self.total_chars = 0

    def generate(
        self,
        text: str,
        voice: str = "narrator",
        output_path: Optional[Path] = None,
        emotion: Optional[str] = None,
        mode: str = "production"
    ) -> AudioResult:
        """
        Generate speech from text.

        Args:
            text: Text to synthesize
            voice: Voice preset name or ElevenLabs voice ID
            output_path: Where to save audio
            emotion: Optional emotion modifier
            mode: "draft" (faster) or "production" (higher quality)

        Returns:
            AudioResult with file path and metadata
        """
        # Get voice config
        config = self.VOICES.get(voice, VoiceConfig(voice_id=voice))

        # Apply emotion
        if emotion:
            text = self._apply_emotion(text, emotion)

        # Handle long text
        if len(text) > self.MAX_CHARS:
            return self._generate_long(text, config, output_path, mode)

        return self._generate_single(text, config, output_path, mode)

    def generate_batch(
        self,
        segments: list[dict],
        output_dir: Path,
        max_concurrent: int = 3
    ) -> list[AudioResult]:
        """
        Generate multiple voice segments.

        Args:
            segments: List of {"text", "voice", "filename", "emotion"}
            output_dir: Directory for output files
            max_concurrent: Max parallel generations

        Returns:
            List of AudioResults
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for i, seg in enumerate(segments):
            text = seg.get("text", "")
            voice = seg.get("voice", "narrator")
            filename = seg.get("filename", f"segment_{i:03d}.mp3")
            emotion = seg.get("emotion")

            logger.info(f"Generating {i+1}/{len(segments)}: {filename}")

            try:
                result = self.generate(
                    text=text,
                    voice=voice,
                    output_path=output_dir / filename,
                    emotion=emotion
                )
                results.append(result)

                # Rate limiting
                import time
                time.sleep(self.RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"Failed {filename}: {e}")

        self._log_summary(results)
        return results

    def generate_from_script(
        self,
        script_path: Path,
        output_dir: Path,
        default_voice: str = "narrator"
    ) -> list[AudioResult]:
        """
        Generate audio from a script file with voice tags.

        Script format:
        [NARRATOR]
        Text for narrator...

        [CHARACTER_1]
        Text for character 1...

        Args:
            script_path: Path to script file
            output_dir: Directory for output files
            default_voice: Voice for untagged text

        Returns:
            List of AudioResults
        """
        script_path = Path(script_path)
        script = script_path.read_text()

        # Parse script into segments
        segments = self._parse_script(script, default_voice)

        logger.info(f"Parsed {len(segments)} segments from script")
        return self.generate_batch(segments, output_dir)

    def _generate_single(
        self,
        text: str,
        config: VoiceConfig,
        output_path: Optional[Path],
        mode: str
    ) -> AudioResult:
        """Generate single audio file."""

        model = "eleven_turbo_v2_5" if mode == "draft" else "eleven_multilingual_v2"

        try:
            audio = self.client.text_to_speech.convert(
                voice_id=config.voice_id,
                text=text,
                model_id=model,
                voice_settings={
                    "stability": config.stability,
                    "similarity_boost": config.similarity_boost,
                    "style": config.style,
                }
            )
        except Exception as e:
            if "rate" in str(e).lower():
                raise VoiceSynthError(str(e), is_rate_limit=True)
            elif "voice" in str(e).lower():
                raise VoiceSynthError(str(e), is_invalid_voice=True, voice_id=config.voice_id)
            raise

        # Save audio
        output_path = output_path or Path(f"output_{hash(text)}.mp3")
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        # Calculate stats
        duration = len(text) / 15  # ~15 chars/second
        cost = len(text) * self.COST_PER_CHAR

        self.total_cost += cost
        self.total_chars += len(text)

        return AudioResult(
            path=output_path,
            duration=duration,
            characters=len(text),
            cost=cost,
            voice=config.voice_id
        )

    def _generate_long(
        self,
        text: str,
        config: VoiceConfig,
        output_path: Optional[Path],
        mode: str
    ) -> AudioResult:
        """Generate long-form audio with chunking."""
        from pydub import AudioSegment
        import tempfile

        chunks = self._split_text(text)
        logger.info(f"Split into {len(chunks)} chunks")

        temp_files = []
        total_cost = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            for i, chunk in enumerate(chunks):
                chunk_path = Path(temp_dir) / f"chunk_{i:03d}.mp3"
                result = self._generate_single(chunk, config, chunk_path, mode)
                temp_files.append(chunk_path)
                total_cost += result.cost

                import time
                time.sleep(self.RATE_LIMIT_DELAY)

            # Concatenate
            combined = AudioSegment.empty()
            for tf in temp_files:
                segment = AudioSegment.from_mp3(tf)
                combined += segment

            output_path = output_path or Path("output_long.mp3")
            combined.export(output_path, format="mp3")

        return AudioResult(
            path=output_path,
            duration=len(combined) / 1000,
            characters=len(text),
            cost=total_cost,
            voice=config.voice_id
        )

    def _split_text(self, text: str) -> list[str]:
        """Split text at sentence boundaries."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) < self.MAX_CHARS:
                current += sentence + " "
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence + " "

        if current:
            chunks.append(current.strip())

        return chunks

    def _parse_script(self, script: str, default_voice: str) -> list[dict]:
        """Parse script with voice tags into segments."""
        segments = []
        current_voice = default_voice
        current_text = ""

        lines = script.strip().split("\n")

        for line in lines:
            # Check for voice tag
            tag_match = re.match(r'\[([A-Z_0-9]+)\]', line.strip())

            if tag_match:
                # Save previous segment
                if current_text.strip():
                    segments.append({
                        "text": current_text.strip(),
                        "voice": current_voice.lower(),
                        "filename": f"segment_{len(segments):03d}.mp3"
                    })
                    current_text = ""

                # Update voice
                current_voice = tag_match.group(1)
            else:
                current_text += line + " "

        # Save final segment
        if current_text.strip():
            segments.append({
                "text": current_text.strip(),
                "voice": current_voice.lower(),
                "filename": f"segment_{len(segments):03d}.mp3"
            })

        return segments

    def _apply_emotion(self, text: str, emotion: str) -> str:
        """Apply emotion modifier to text."""
        prefixes = {
            "excited": "[Speaking with excitement] ",
            "serious": "[In a serious tone] ",
            "sad": "[Speaking sadly] ",
            "angry": "[Speaking angrily] ",
            "energetic": "[With high energy] ",
        }
        return prefixes.get(emotion, "") + text

    def _log_summary(self, results: list[AudioResult]):
        """Log batch generation summary."""
        total_chars = sum(r.characters for r in results)
        total_cost = sum(r.cost for r in results)
        total_duration = sum(r.duration for r in results)

        logger.info(f"Batch complete: {len(results)} segments")
        logger.info(f"Total characters: {total_chars:,}")
        logger.info(f"Total duration: {total_duration:.1f}s")
        logger.info(f"Total cost: ${total_cost:.2f}")

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_characters": self.total_chars,
            "total_cost": self.total_cost,
            "cost_per_minute": self.total_cost / (self.total_chars / 15 / 60) if self.total_chars else 0
        }


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voice Synthesis Automation")
    parser.add_argument("--text", help="Text to synthesize")
    parser.add_argument("--script", help="Script file path")
    parser.add_argument("--segments", help="Segments JSON file")
    parser.add_argument("--voice", default="narrator", help="Voice preset")
    parser.add_argument("--output", default="output.mp3", help="Output file")
    parser.add_argument("--output-dir", default="./audio", help="Output directory")
    args = parser.parse_args()

    synth = VoiceSynthesizer()

    if args.text:
        result = synth.generate(args.text, args.voice, Path(args.output))
        print(f"Generated: {result.path} ({result.duration:.1f}s, ${result.cost:.4f})")

    elif args.script:
        results = synth.generate_from_script(Path(args.script), Path(args.output_dir))
        print(f"Generated {len(results)} segments")

    elif args.segments:
        with open(args.segments) as f:
            segments = json.load(f)
        results = synth.generate_batch(segments, Path(args.output_dir))
        print(f"Generated {len(results)} segments")

    else:
        parser.print_help()
