window.ASCEND_RUNTIME_CONFIG = window.ASCEND_RUNTIME_CONFIG || {};

if (!Object.prototype.hasOwnProperty.call(window.ASCEND_RUNTIME_CONFIG, "apiUrl")) {
  const isLocalHost = ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname);
  window.ASCEND_RUNTIME_CONFIG.apiUrl =
    isLocalHost ? "" : window.location.origin;
}

if (!window.ASCEND_RUNTIME_CONFIG.environmentLabel) {
  const isLocalHost = ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname);
  window.ASCEND_RUNTIME_CONFIG.environmentLabel = isLocalHost ? "Local UI -> AWS DEV API" : "AWS DEV";
}

if (!Object.prototype.hasOwnProperty.call(window.ASCEND_RUNTIME_CONFIG, "showEnvironmentBadge")) {
  window.ASCEND_RUNTIME_CONFIG.showEnvironmentBadge = ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname);
}
