from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, use_gpu=True)  # 开启角度分类 & GPU
result = ocr.ocr("PPOCRLabel/data/paddle.png", cls=True)  # 识别 test.jpg 图片的文本
print(result)

