"""JSON-lines worker for the isolated PaddleOCR-VL environment."""
import json
import sys


RESULT_PREFIX = "__PPOCRLABEL_RESULT__"


def configure_utf8_streams():
    """Keep the parent JSON-lines protocol independent of the Windows code page."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, OSError):
            # Python 3.10 supports reconfigure; retain a safe fallback for wrappers.
            pass


def emit(payload):
    print(RESULT_PREFIX + json.dumps(payload, ensure_ascii=False), flush=True)


def as_plain(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value


def main():
    configure_utf8_streams()
    try:
        from paddleocr import PaddleOCRVL

        pipeline = PaddleOCRVL(
            pipeline_version="v1.6",
            device="gpu:0",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            format_block_content=False,
        )
    except Exception as exc:  # report setup failures through the parent protocol
        emit({"error": f"PaddleOCR-VL 初始化失败：{exc}"})
        return
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            entries = []
            for result in pipeline.predict(request["image_path"]):
                data = result.json
                data = data.get("res", data)
                for block in data.get("parsing_res_list", []):
                    text = str(block.get("block_content") or "").strip()
                    bbox = as_plain(block.get("block_bbox"))
                    if not text or not bbox or len(bbox) != 4:
                        continue
                    entries.append({"box": [float(value) for value in bbox], "text": text, "score": 0.0})
            emit({"entries": entries})
        except Exception as exc:  # keep the service alive for the next page
            emit({"error": f"PaddleOCR-VL 识别失败：{exc}"})


if __name__ == "__main__":
    main()
