// 牌組雲端同步專用 Firebase 專案（haikyuu-cards-cloud）
// 與 game.html 的 BYO Firebase（使用者自貼 hv_firebase_config）完全獨立，互不共用。
// apiKey 不是密碼，公開在前端是正常做法，安全性由 Firestore Security Rules 把關。
export const firebaseConfig = {
  apiKey: "AIzaSyBY8lPv_x01gBKZbpvQ6J8xznLNzeJFYb4",
  authDomain: "haikyuu-cards-cloud.firebaseapp.com",
  projectId: "haikyuu-cards-cloud",
  storageBucket: "haikyuu-cards-cloud.firebasestorage.app",
  messagingSenderId: "244673961202",
  appId: "1:244673961202:web:fdf0bdb3cb8fc2dec3046b"
};
