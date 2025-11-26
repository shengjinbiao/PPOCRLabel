from paddleocr import PPStructureV3

engine = PPStructureV3(
    layout_detection_model_dir=r"C:\Users\sheng\.paddlex\official_models\PP-DocLayout_plus-L",
    use_region_detection=True,
)

res = engine.predict(r"D:\PPOCRLabel\p034.png")
print("raw result:", res)
for idx, r in enumerate(res):
    if isinstance(r, dict):
        print(f"item {idx} keys:", list(r.keys()))
        print("type:", r.get("type"))
        print("res:", r.get("res"))
    else:
        print(f"item {idx}:", r)
