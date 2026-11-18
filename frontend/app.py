from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from asr_engine.app.errors import ASRError
from asr_engine.app.pipeline import transcribe_file


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data/fleurs_vi_clean/audio/validation/000000_1594.txt"
SAMPLES = {
    "MP3": ROOT / "data/media_smoke/sample.mp3",
    "MP4": ROOT / "data/media_smoke/sample.mp4",
    "WAV": REFERENCE.with_suffix(".wav"),
}
MIME = {".mp3": "audio/mpeg", ".mp4": "video/mp4", ".wav": "audio/wav"}


def main():
    st.set_page_config(page_title="Chép lời tiếng Việt", page_icon="🎙️")
    st.title("Chép lời tiếng Việt")
    st.caption("WAV, MP3 hoặc MP4 có âm thanh · Tối đa 5 phút và 100 MiB mỗi tệp")
    available = [name for name, path in SAMPLES.items() if path.is_file()]
    choices = ["Dùng mẫu", "Tải tệp lên"] if available else ["Tải tệp lên"]
    mode = st.radio("Nguồn âm thanh", choices, horizontal=True)
    sample = None
    uploaded = None
    if mode == "Dùng mẫu":
        sample = SAMPLES[st.selectbox("Bản đọc FLEURS · 15 giây", available)]
        suffix = sample.suffix
        media = sample.read_bytes()
        identity = ("sample", str(sample))
    else:
        uploaded = st.file_uploader("Chọn tệp trên máy", type=["wav", "mp3", "mp4"])
        if uploaded is None:
            st.session_state.pop("result", None)
            return
        if uploaded.size > 100 * 1024**2:
            st.error("Tệp vượt giới hạn 100 MiB. Hãy chọn tệp nhỏ hơn.")
            return
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in MIME:
            st.error("Hãy chọn tệp WAV, MP3 hoặc MP4.")
            return
        media = uploaded.getvalue()
        identity = ("upload", uploaded.file_id)

    if suffix == ".mp4":
        st.video(media, format=MIME[suffix])
    else:
        st.audio(media, format=MIME[suffix])

    if st.button("Nhận dạng", type="primary"):
        st.session_state.pop("result", None)
        try:
            with st.spinner("Đang chép lời…"), TemporaryDirectory() as temporary:
                source = sample
                if source is None:
                    source = Path(temporary) / ("upload" + suffix)
                    source.write_bytes(media)
                result, folder = transcribe_file(
                    source, ROOT / "outputs/demo",
                    model_id=str(ROOT / "models/PhoWhisper-small-clean"),
                    local_files_only=True, max_duration=300,
                )
                st.session_state.result = identity, result, folder
        except (ASRError, OSError) as exc:
            st.error(str(exc))

    saved = st.session_state.get("result")
    if saved and saved[0] == identity:
        _, result, folder = saved
        st.subheader("Bản chép lời")
        st.text(result["text"] or "Không nhận được lời nói.")
        st.caption(f'Âm thanh {result["duration_seconds"]:.1f} giây · Xử lý {result["timings"]["total_seconds"]:.1f} giây')
        st.download_button("Tải bản TXT", (folder / "transcript.txt").read_bytes(),
                           file_name="ban-chep-loi.txt", mime="text/plain")
        if sample and REFERENCE.is_file():
            with st.expander("Đối chiếu với lời đọc gốc"):
                st.text(REFERENCE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
