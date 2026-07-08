// 卡圖快取：cache-first，只處理 /images/ 底下的圖檔
// 版本號 bump 時機：卡圖集有新增/替換/刪除時手動改這裡，activate 會清掉舊版本 cache
const CACHE_VERSION = 'v1';
const IMAGE_CACHE = 'haikyuu-images-' + CACHE_VERSION;

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key.startsWith('haikyuu-images-') && key !== IMAGE_CACHE)
          .map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin || !url.pathname.includes('/images/')) {
    return; // 非卡圖請求：不攔截，正常走網路（cards_data.js / index.html 需要即時更新）
  }

  event.respondWith(
    caches.open(IMAGE_CACHE).then(async cache => {
      const cached = await cache.match(req);
      if (cached) return cached;
      const resp = await fetch(req);
      if (resp.ok) cache.put(req, resp.clone());
      return resp;
    })
  );
});
