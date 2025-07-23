self.addEventListener("install", (e) => {
  console.log("Service Worker: Installed");
});

self.addEventListener("activate", (e) => {
  console.log("Service Worker: Activated");
});

self.addEventListener("fetch", (e) => {
  // 네트워크 요청 캐싱 등 나중에 확장 가능
});