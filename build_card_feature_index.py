# -*- coding: utf-8 -*-
# 離線腳本：對 images/ 底下每張卡圖跑 ORB 特徵擷取，輸出成給前端比對用的資產。
#
# 用整張卡面（不只裁切區域）算特徵：實測過「只用左側名字/費用欄」的版本，
# 反而更差——那塊區域大多是直式文字＋簡單邊框，卡跟卡之間長得太像，鑑別度不夠。
# 真正有鑑別度的是角色插畫的細節，即使插畫在反光嚴重的照片裡會被洗掉一部分，
# 沒被洗掉的部分＋插畫本身的豐富細節，整體比對效果還是比只看文字欄好。
#
# 輸出兩個檔案：
#   card_features_index.json  卡片中繼資料（card_no/name_zh/尺寸/在 bin 裡的 offset）
#   card_features.bin         純數值資料：每張卡依序存放 keypoints (float32 x,y 交錯)
#                              + descriptors (uint8, 每個 32 bytes)，offset 由 index.json 記錄
#
# 卡圖庫更新（新增/替換卡圖）後要重跑這支腳本。
#
# 注意：repo 路徑含中文字，cv2.imread 在 Windows 上對非 ASCII 路徑會直接失敗，
# 一律用 np.fromfile + cv2.imdecode 讀檔。

import json
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(ROOT, 'images')
CARDS_JSON = os.path.join(ROOT, 'cards_zh.json')
OUT_INDEX = os.path.join(ROOT, 'card_features_index.json')
OUT_BIN = os.path.join(ROOT, 'card_features.bin')

N_FEATURES = 500


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def load_card_lookup():
    with open(CARDS_JSON, encoding='utf-8') as f:
        data = json.load(f)
    lookup = {}
    for c in data['cards']:
        lookup[c['image_file']] = {
            'card_no': c.get('card_no'),
            'name_zh': c.get('name_zh'),
        }
    return lookup


def main():
    lookup = load_card_lookup()
    orb = cv2.ORB_create(nfeatures=N_FEATURES)

    image_files = sorted(
        f for f in os.listdir(IMAGES_DIR) if f.lower().endswith('.webp')
    )
    print(f'找到 {len(image_files)} 張卡圖，開始擷取 ORB 特徵…')

    index = {
        'version': 1,
        'orb': {'nfeatures': N_FEATURES},
        'cards': [],
    }
    bin_chunks = []
    byte_offset = 0
    no_keypoints = []

    for i, image_file in enumerate(image_files):
        path = os.path.join(IMAGES_DIR, image_file)
        img = imread_unicode(path)
        if img is None:
            print(f'  [警告] 讀取失敗，略過：{image_file}')
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        keypoints, descriptors = orb.detectAndCompute(gray, None)
        num_kp = len(keypoints) if keypoints else 0

        if num_kp == 0 or descriptors is None:
            no_keypoints.append(image_file)
            kp_bytes = b''
            desc_bytes = b''
            num_kp = 0
        else:
            xy = np.array([kp.pt for kp in keypoints], dtype=np.float32)
            kp_bytes = xy.tobytes()
            desc_bytes = descriptors.astype(np.uint8).tobytes()

        meta = lookup.get(image_file, {})
        index['cards'].append({
            'image_file': image_file,
            'card_no': meta.get('card_no'),
            'name_zh': meta.get('name_zh'),
            'width': w,
            'height': h,
            'num_kp': num_kp,
            'kp_offset': byte_offset,
            'desc_offset': byte_offset + len(kp_bytes),
        })
        bin_chunks.append(kp_bytes)
        bin_chunks.append(desc_bytes)
        byte_offset += len(kp_bytes) + len(desc_bytes)

        if (i + 1) % 100 == 0:
            print(f'  已處理 {i + 1}/{len(image_files)}')

    with open(OUT_BIN, 'wb') as f:
        for chunk in bin_chunks:
            f.write(chunk)

    with open(OUT_INDEX, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, separators=(',', ':'))

    total_kp = sum(c['num_kp'] for c in index['cards'])
    print(f'完成：{len(index["cards"])} 張卡，共 {total_kp} 個特徵點')
    print(f'  {OUT_INDEX}（{os.path.getsize(OUT_INDEX)/1024:.1f} KB）')
    print(f'  {OUT_BIN}（{os.path.getsize(OUT_BIN)/1024:.1f} KB）')
    if no_keypoints:
        print(f'  [警告] {len(no_keypoints)} 張卡沒抓到任何特徵點：{no_keypoints}')


if __name__ == '__main__':
    main()
