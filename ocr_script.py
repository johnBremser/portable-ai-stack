import os
if not os.path.exists('temp_image.jpg'):
    print('Error: temp_image.jpg not found')
    exit(1)

import subprocess
result = subprocess.run([
    'python3', '-c', '''
import cv2
import numpy as np
from paddleocr import PaddleOCR

# Load the image
img = cv2.imread("temp_image.jpg")

# Initialize OCR
ocr = PaddleOCR(use_angle_cls=True, lang="pt", show_log=False)
result = ocr.ocr(img, cls=True)

# Extract text from result
texts = []
if result[0]:
    for line in result[0]:
        texts.append(line[1][0])

if texts:
    print("\\n".join(texts))
else:
    print("No text found")
'''
], capture_output=True, text=True)

print(result.stdout)
if result.returncode != 0:
    print("Error:", result.stderr)
