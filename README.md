# Voice Synthesis Automation

Production-grade voice synthesis pipeline using ElevenLabs API. Batch process 15+ voice segments per project with automatic chunking, rate limiting, and cost optimization.

## Features

- **Batch Processing**: Generate multiple voice segments in parallel
- **Long-Form Support**: Automatic chunking for scripts of any length
- **Multi-Voice**: Different voices for different characters/narrators
- **Emotion Control**: Apply tone and emotion modifiers
- **Cost Tracking**: Monitor API usage and costs in real-time
- **Rate Limiting**: Smart throttling to avoid API limits

## Quick Start

```python
from voice_synth import VoiceSynthesizer

synth = VoiceSynthesizer()

# Single generation
audio = synth.generate(
    text="Welcome to the future of AI-generated content.",
    voice="narrator",
    output_path="intro.mp3"
)

# Batch generation from script
segments = synth.generate_from_script(
    script_path="episode_script.txt",
    output_dir="./audio",
    default_voice="narrator"
)
```

## Installation

```bash
git clone https://github.com/wonderstone843/voice-synthesis-automation.git
cd voice-synthesis-automation
pip install -r requirements.txt

# Add your ElevenLabs API key
echo "ELEVENLABS_API_KEY=your-key-here" > .env
```

## Usage

### Command Line

```bash
# Single text
python voice_synth.py --text "Hello world" --voice narrator --output hello.mp3

# From script file
python voice_synth.py --script episode.txt --output-dir ./audio

# Batch with multiple voices
python voice_synth.py --segments segments.json --output-dir ./audio
```

### Script Format

```text
[NARRATOR]
The year is 2087. Humanity stands at a crossroads.

[CHARACTER_1]
We have to act now. There's no more time.

[NARRATOR]
But not everyone agreed with this assessment.

[CHARACTER_2]
Patience. We've waited this long. What's another decade?
```

### Segments JSON Format

```json
[
  {
    "text": "Welcome to the show.",
    "voice": "narrator",
    "filename": "intro.mp3"
  },
  {
    "text": "Let's dive into today's topic.",
    "voice": "host",
    "filename": "transition.mp3",
    "emotion": "energetic"
  }
]
```

## Voice Presets

| Preset | Description | Best For |
|--------|-------------|----------|
| `narrator` | Clear, authoritative | Documentaries, explainers |
| `dramatic` | Intense, emotional | Action, drama |
| `energetic` | Upbeat, fast-paced | Sports, gaming |
| `calm` | Soothing, measured | Meditation, ASMR |
| `commentator` | Dynamic, reactive | Live events, sports |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    INPUT                             │
│  Script / Text / Segments JSON                      │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                 SCRIPT PARSER                        │
│  Splits by voice tags, extracts segments            │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                TEXT CHUNKER                          │
│  Splits long text at sentence boundaries            │
│  Max 5000 chars per API call                        │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              ELEVENLABS API                          │
│  Rate-limited requests with retry logic             │
│  Parallel processing with semaphore                 │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              AUDIO PROCESSOR                         │
│  Concatenate chunks, normalize audio                │
│  Export MP3/WAV                                     │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                   OUTPUT                             │
│  Individual segments + combined audio               │
└─────────────────────────────────────────────────────┘
```

## Cost Optimization

ElevenLabs charges per character. This pipeline optimizes costs by:

1. **Deduplication**: Caches identical text generations
2. **Efficient Chunking**: Minimizes API calls
3. **Model Selection**: Uses turbo model for drafts, HD for final

```python
# Draft mode (faster, cheaper)
synth.generate(text, mode="draft")

# Production mode (higher quality)
synth.generate(text, mode="production")
```

## Production Stats

- **15+ voice segments** per project
- **44 video productions** completed
- **80% cost reduction** vs manual voice-over
- **9,400+ audience** built on AI-generated content

## API Reference

### VoiceSynthesizer

```python
class VoiceSynthesizer:
    def generate(
        text: str,
        voice: str = "narrator",
        output_path: Path = None,
        emotion: str = None,
        mode: str = "production"
    ) -> AudioResult

    def generate_batch(
        segments: list[dict],
        output_dir: Path,
        max_concurrent: int = 3
    ) -> list[AudioResult]

    def generate_from_script(
        script_path: Path,
        output_dir: Path,
        default_voice: str = "narrator"
    ) -> list[AudioResult]
```

### AudioResult

```python
@dataclass
class AudioResult:
    path: Path
    duration: float  # seconds
    characters: int
    cost: float
    voice: str
```

## Error Handling

```python
from voice_synth import VoiceSynthesizer, VoiceSynthError

synth = VoiceSynthesizer()

try:
    result = synth.generate("Hello world")
except VoiceSynthError as e:
    if e.is_rate_limit:
        # Automatically retried, but still failed
        print("Rate limit exceeded, try again later")
    elif e.is_invalid_voice:
        print(f"Voice not found: {e.voice_id}")
    else:
        raise
```

## Author

**Joshua Penn**
Oracle Cloud Infrastructure Generative AI Professional

Building production AI pipelines that ship.

## License

MIT
