/**
 * Wire encryption for Bango: RSA-OAEP (SHA-256) + AES-256-GCM, same one-line format as
 * ``backend/rsa_envelope.py`` (envelope "1.…" parts).
 * Requires Web Crypto; use http://127.0.0.1, https, or localhost (secure context).
 */
(function (global) {
  "use strict";

  var PEM_PATH = "/static/keys/public.pem";
  var _publicKey = null;
  var _loadPromise = null;

  function pemToArrayBuffer(pem) {
    var b64 = pem
      .replace("-----BEGIN PUBLIC KEY-----", "")
      .replace("-----END PUBLIC KEY-----", "")
      .replace(/[\r\n\s]/g, "");
    var binary = atob(b64);
    var n = binary.length;
    var bytes = new Uint8Array(n);
    for (var i = 0; i < n; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  function b64e(buf) {
    var b = new Uint8Array(buf);
    var s = btoa(String.fromCharCode.apply(null, b));
    return s.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function getPublicKey() {
    if (_publicKey) {
      return Promise.resolve(_publicKey);
    }
    if (_loadPromise) {
      return _loadPromise;
    }
    _loadPromise = fetch(PEM_PATH, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) {
          throw new Error("pem");
        }
        return r.text();
      })
      .then(function (pem) {
        return window.crypto.subtle.importKey(
          "spki",
          pemToArrayBuffer(pem),
          { name: "RSA-OAEP", hash: { name: "SHA-256" } },
          false,
          ["encrypt"]
        );
      })
      .then(function (k) {
        _publicKey = k;
        return k;
      });
    return _loadPromise;
  }

  /**
   * @param {Record<string, string>} pii — fname, lname, phone, email, personal_id, full_name, cc, exp, cvv
   * @returns {Promise<string>} envelope line starting with "1."
   */
  function encryptPiiObject(pii) {
    if (!window.crypto || !window.crypto.subtle) {
      return Promise.reject(new Error("no-subtle"));
    }
    return getPublicKey().then(function (publicKey) {
      var te = new TextEncoder();
      var jsonStr = JSON.stringify(pii);
      var plain = te.encode(jsonStr);
      var aesKeyBytes = new Uint8Array(32);
      window.crypto.getRandomValues(aesKeyBytes);
      var nonce = new Uint8Array(12);
      window.crypto.getRandomValues(nonce);
      return window.crypto.subtle
        .importKey(
          "raw",
          aesKeyBytes,
          { name: "AES-GCM", length: 256 },
          false,
          ["encrypt"]
        )
        .then(function (aesKey) {
          return window.crypto.subtle
            .encrypt(
              { name: "AES-GCM", iv: nonce, tagLength: 128 },
              aesKey,
              plain
            )
            .then(function (ctBuf) {
              return window.crypto.subtle
                .encrypt({ name: "RSA-OAEP" }, publicKey, aesKeyBytes)
                .then(function (encKeyBuf) {
                  return "1." + b64e(encKeyBuf) + "." + b64e(nonce) + "." + b64e(ctBuf);
                });
            });
        });
    });
  }

  global.EduBangoCrypto = {
    encryptPiiObject: encryptPiiObject,
  };
})(typeof self !== "undefined" ? self : this);
