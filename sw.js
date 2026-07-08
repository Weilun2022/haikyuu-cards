// 靜態資源快取：cache-first，只處理 /images/ 與 /audio/ 底下的檔案
// 版本號 bump 時機：對應資源集有新增/替換/刪除時手動改這裡，activate 會清掉舊版本 cache
const IMAGE_CACHE_VERSION = 'v1';
const AUDIO_CACHE_VERSION = 'v1';
const IMAGE_CACHE = 'haikyuu-images-' + IMAGE_CACHE_VERSION;
const AUDIO_CACHE = 'haikyuu-audio-' + AUDIO_CACHE_VERSION;

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key =>
            (key.startsWith('haikyuu-images-') && key !== IMAGE_CACHE) ||
            (key.startsWith('haikyuu-audio-') && key !== AUDIO_CACHE)
          )
          .map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  const isImage = url.pathname.includes('/images/');
  const isAudio = url.pathname.includes('/audio/');
  if (!isImage && !isAudio) {
    return; // 非卡圖/語音請求：不攔截，正常走網路（cards_data.js / index.html 需要即時更新）
  }

  if (isImage) {
    event.respondWith(cacheFirst(IMAGE_CACHE, req, req));
    return;
  }

  // 音檔：瀏覽器讀取 <audio> 時一律會夾帶 Range 標頭（連第一次請求也是），
  // 但這裡的片段都很短（5~10秒）不需要支援拖曳搜尋，所以忽略 Range，
  // 一律用不含 Range 的請求向來源要「完整內容」來快取＋回應，
  // 用不含 Range 差異的 Request 當快取 key，避免每次都因為 Range 標頭不同而 cache miss
  const audioCacheKey = new Request(url.href, { method: 'GET' });
  event.respondWith(cacheFirst(AUDIO_CACHE, audioCacheKey, audioCacheKey));
});

async function cacheFirst(cacheName, cacheKey, fetchReq) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(cacheKey);
  if (cached) return cached;
  const resp = await fetch(fetchReq);
  if (resp.ok) cache.put(cacheKey, resp.clone());
  return resp;
}
