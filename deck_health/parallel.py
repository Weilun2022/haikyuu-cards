"""平行運算設定。程序數由環境變數 DH_WORKERS 決定（預設 2，與雲端環境相同）。
DH_WORKERS=2 時，切分方式與種子和舊版完全相同，舊結果可以重現；
大於 2 時把場數切成更多份、用不同種子，結果在統計上等價但數字不會逐位相同。"""
import os


def workers():
    try:
        return max(1, int(os.environ.get('DH_WORKERS', '2')))
    except ValueError:
        return 2


def chunks(n, seed_a, seed_b):
    """把 n 場切成數份，回傳 [(場數, 種子), ...]。"""
    w = workers()
    if w <= 2:
        return [(n // 2, seed_a), (n - n // 2, seed_b)]
    base, extra = divmod(n, w)
    out = []
    for i in range(w):
        k = base + (1 if i < extra else 0)
        if k: out.append((k, seed_a + 1009 * i))
    return out
