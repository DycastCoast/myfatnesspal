// Barcode scanning.
// 1. Browsers with a built-in BarcodeDetector (Chrome on Android) use it: fast, no download.
// 2. Everything else (iPhone Safari) loads the html5-qrcode library on demand.
// Either way the result goes into the barcode box and the form submits itself.

(function () {
  const LIBRARY = 'https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js';
  const btn = document.getElementById('scan-btn');
  const box = document.getElementById('scanner');
  const video = document.getElementById('scan-video');
  const reader = document.getElementById('scan-reader');
  const msg = document.getElementById('scan-msg');
  const stopBtn = document.getElementById('scan-stop');
  const codeInput = document.getElementById('code');
  const form = document.getElementById('barcode-form');
  let stopCurrent = null;

  function found(code) {
    if (stopCurrent) stopCurrent();
    codeInput.value = code;
    msg.textContent = 'Found ' + code + '…';
    form.submit();
  }

  function fail(text) {
    msg.textContent = text + ' You can type the number below instead.';
  }

  async function nativeScan() {
    video.hidden = false;
    reader.hidden = true;
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    video.srcObject = stream;
    await video.play();
    let running = true;
    stopCurrent = function () { running = false; stream.getTracks().forEach(function (t) { t.stop(); }); };
    const detector = new BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e'] });
    (async function tick() {
      if (!running) return;
      try {
        const codes = await detector.detect(video);
        if (codes.length) return found(codes[0].rawValue);
      } catch (e) { /* frame not ready yet: keep going */ }
      requestAnimationFrame(tick);
    })();
  }

  function loadLibrary() {
    return new Promise(function (resolve, reject) {
      if (window.Html5Qrcode) return resolve();
      const s = document.createElement('script');
      s.src = LIBRARY;
      s.onload = resolve;
      s.onerror = function () { reject(new Error('Could not load the scanner.')); };
      document.head.appendChild(s);
    });
  }

  async function libraryScan() {
    video.hidden = true;
    reader.hidden = false;
    msg.textContent = 'Starting camera…';
    await loadLibrary();
    const F = window.Html5QrcodeSupportedFormats;
    const scanner = new window.Html5Qrcode('scan-reader', {
      formatsToSupport: [F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E],
      verbose: false
    });
    stopCurrent = function () { scanner.stop().catch(function () {}); };
    await scanner.start(
      { facingMode: 'environment' },
      { fps: 12, qrbox: { width: 260, height: 130 } },
      function (text) { found(text); },
      function () { /* no barcode in this frame */ }
    );
    msg.textContent = 'Point the camera at a barcode.';
  }

  btn.addEventListener('click', async function () {
    box.classList.add('on');
    btn.hidden = true;
    msg.textContent = 'Starting camera…';
    try {
      let native = false;
      if ('BarcodeDetector' in window) {
        const formats = await BarcodeDetector.getSupportedFormats();
        native = formats.indexOf('ean_13') !== -1;
      }
      if (native) {
        await nativeScan();
        msg.textContent = 'Point the camera at a barcode.';
      } else {
        await libraryScan();
      }
    } catch (e) {
      fail(e && e.name === 'NotAllowedError' ? 'Camera access was blocked.' : 'Camera could not start.');
    }
  });

  stopBtn.addEventListener('click', function () {
    if (stopCurrent) stopCurrent();
    box.classList.remove('on');
    btn.hidden = false;
  });
})();
