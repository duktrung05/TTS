"""Integration with real feature extraction, but a test double for model generation.

These fixtures contain synthetic tones, not speech; they do NOT measure ASR accuracy.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from asr_engine.app.audio import AudioData
from asr_engine.app.recognizer import WhisperRecognizer


def test_long_audio_features_are_not_truncated_and_final_segments_are_preserved():
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    extractor = transformers.WhisperFeatureExtractor()
    observations = {}

    class Processor:
        def __call__(self, samples, **kwargs):
            return extractor(samples, **kwargs)

        def decode(self, tokens, **kwargs):
            return {1: "đầu", 2: "cuối"}[int(tokens[0])]

        def batch_decode(self, sequences, **kwargs):
            return ["đầu cuối"]

    class ModelDouble:
        def generate(self, **kwargs):
            observations.update(kwargs)
            return {
                "sequences": torch.tensor([[1, 2]]),
                "segments": [[
                    {"start": 0.0, "end": 3.0, "tokens": torch.tensor([1])},
                    {"start": 32.0, "end": 35.0, "tokens": torch.tensor([2])},
                ]],
            }

    recognizer = WhisperRecognizer.__new__(WhisperRecognizer)
    recognizer.torch = torch
    recognizer.device = "cpu"
    recognizer.dtype = torch.float32
    recognizer.processor = Processor()
    recognizer.model = ModelDouble()
    recognizer.model_id = "test-double-not-a-pretrained-model"
    recognizer.requested_revision = "test"
    recognizer.resolved_revision = None
    recognizer.load_seconds = 0
    recognizer.threads = 1
    audio = AudioData(np.sin(np.arange(35 * 16_000, dtype=np.float32)) * 0.1, {"duration_seconds": 35.0})
    result = recognizer.transcribe(audio)
    assert observations["input_features"].shape[-1] > 3000
    assert observations["attention_mask"].shape[-1] > 3000
    assert observations["return_timestamps"] is True
    assert observations["return_segments"] is True
    assert observations["task"] == "transcribe"
    assert observations["language"] == "vi"
    assert result["segments"][-1]["start"] == 32
    assert result["text"] == "đầu cuối"


def test_native_whisper_generation_advances_beyond_30_seconds_without_downloads():
    """Exercise the actual generation API with tiny random weights and forced tokens.

    This proves window advancement/schema compatibility, never speech recognition.
    """
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    torch.set_num_threads(2)
    config = transformers.WhisperConfig(
        vocab_size=1600, num_mel_bins=80, d_model=8, encoder_layers=1,
        decoder_layers=1, encoder_attention_heads=1, decoder_attention_heads=1,
        encoder_ffn_dim=16, decoder_ffn_dim=16, max_source_positions=1500,
        max_target_positions=448, pad_token_id=0, bos_token_id=1,
        eos_token_id=2, decoder_start_token_id=1, suppress_tokens=[], begin_suppress_tokens=[],
    )
    model = transformers.WhisperForConditionalGeneration(config).eval()
    model.generation_config.no_timestamps_token_id = 8
    model.generation_config.lang_to_id = {"<|vi|>": 3}
    model.generation_config.task_to_id = {"transcribe": 4}
    model.generation_config.is_multilingual = True

    class ForcedTestTokens(transformers.LogitsProcessor):
        end_token = 1509

        def __call__(self, ids, scores):
            token = [9, 7, self.end_token, 2][(ids.shape[-1] - 3) % 4]
            scores.fill_(-float("inf"))
            scores[:, token] = 0
            return scores

    forced = ForcedTestTokens()

    def progress(position):
        remaining = int(position[0, 1] - position[0, 0])
        forced.end_token = 9 + min(1500, remaining // 2)

    with torch.inference_mode():
        result = model.generate(
            input_features=torch.zeros(1, 80, 3500),
            attention_mask=torch.ones(1, 3500, dtype=torch.long),
            language="vi", task="transcribe", return_timestamps=True, return_segments=True,
            condition_on_prev_tokens=False, max_new_tokens=440, do_sample=False,
            monitor_progress=progress, logits_processor=transformers.LogitsProcessorList([forced]),
        )
    times = [(float(x["start"]), float(x["end"])) for x in result["segments"][0]]
    assert times == [(0, 30), (30, 35)]
