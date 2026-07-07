import { test } from "node:test";
import assert from "node:assert/strict";
import { aggregateCloses, isUptrend } from "../src/core/trendFilter.js";

const mk = (prices) => prices.map((p, i) => ({ close: p, closeTime: i }));

test("aggregateCloses: gruplarin son kapanisini alir, sondan hizalar", () => {
  // 10 mum, grup=4 -> 2 tam grup (mum 2-5 ve 6-9), kapanislar: 5. ve 9. indeks
  const candles = mk([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.deepEqual(aggregateCloses(candles, 4), [5, 9]);
  assert.deepEqual(aggregateCloses(mk([1, 2, 3]), 4), []);
});

test("isUptrend: yukselen seride true, dusen seride false", () => {
  const cfg = { htfMultiple: 2, htfEmaPeriod: 10 };
  const rising = mk(Array.from({ length: 100 }, (_, i) => 100 + i));
  const falling = mk(Array.from({ length: 100 }, (_, i) => 300 - i));
  assert.equal(isUptrend(rising, cfg), true);
  assert.equal(isUptrend(falling, cfg), false);
});

test("isUptrend: veri yetersizse filtre uygulanmaz (true)", () => {
  const cfg = { htfMultiple: 4, htfEmaPeriod: 50 };
  assert.equal(isUptrend(mk([1, 2, 3, 4, 5, 6, 7, 8]), cfg), true);
});
