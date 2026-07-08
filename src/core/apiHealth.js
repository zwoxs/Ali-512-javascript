/**
 * API saglik izleyicisi - devre kesici (circuit breaker).
 * Art arda gelen API hatalarini sayar; esik asilinca "devre acilir" ve belirli
 * bir sure yeni islem denenmez. Boylece borsa/ag sorununda bot koru korune
 * emir gondermeye calismaz, sakinlesme suresi tanir. Basarili bir istek
 * sayaci sifirlar.
 */
export class ApiHealth {
  constructor(cfg, now = () => Date.now()) {
    this.maxErrors = cfg.apiMaxConsecutiveErrors;
    this.cooldownMs = cfg.apiCircuitCooldownMin * 60_000;
    this.now = now;
    this.consecutiveErrors = 0;
    this.openUntil = 0;
  }

  recordSuccess() {
    this.consecutiveErrors = 0;
  }

  /** @returns {boolean} bu hata devreyi yeni mi acti? */
  recordError() {
    this.consecutiveErrors++;
    if (this.consecutiveErrors >= this.maxErrors && this.now() >= this.openUntil) {
      this.openUntil = this.now() + this.cooldownMs;
      return true;
    }
    return false;
  }

  /** Devre acik mi (yeni islem engelli mi)? */
  isOpen() {
    return this.now() < this.openUntil;
  }

  /** Kalan sogurma saniyesi (izleme icin). */
  remainingSec() {
    return Math.max(0, Math.ceil((this.openUntil - this.now()) / 1000));
  }
}
