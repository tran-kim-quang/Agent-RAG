import time

from backend.process_raw_data.correct_service.correct_service import (
    LocalVietnameseOcrCorrector,
    PassthroughOcrCorrector,
)


class FakeLocalCorrector(LocalVietnameseOcrCorrector):
    def __init__(self, *, fail_load: bool = False, idle_seconds: int | float = 60) -> None:
        super().__init__(model_name="test-model", device="cpu", idle_seconds=idle_seconds)
        self.fail_load = fail_load

    def _load_bundle(self) -> dict:
        if self.fail_load:
            raise RuntimeError("model unavailable")
        self._bundle = {"loaded": True}
        return self._bundle

    def _run_inference(self, text: str, bundle: dict) -> str:
        assert bundle["loaded"] is True
        return f"corrected:{text}"


def test_passthrough_corrector_only_normalizes_outer_whitespace() -> None:
    assert PassthroughOcrCorrector().correct("  raw OCR text  ") == "raw OCR text"


def test_local_corrector_runs_inference_and_can_release_model() -> None:
    corrector = FakeLocalCorrector()

    assert corrector.correct("  van ban OCR  ") == "corrected:van ban OCR"
    assert corrector._bundle is not None

    corrector.unload()

    assert corrector._bundle is None


def test_local_corrector_falls_back_to_original_text_when_model_fails() -> None:
    corrector = FakeLocalCorrector(fail_load=True)

    assert corrector.correct("  van ban OCR  ") == "van ban OCR"
    corrector.unload()


def test_local_corrector_releases_model_after_idle_timeout() -> None:
    corrector = FakeLocalCorrector(idle_seconds=0.01)

    corrector.correct("van ban OCR")
    deadline = time.monotonic() + 1
    while corrector._bundle is not None and time.monotonic() < deadline:
        time.sleep(0.01)

    assert corrector._bundle is None
