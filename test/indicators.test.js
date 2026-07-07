import { test } from "node:test";
import assert from "node:assert/strict";
import { ema, sma, rsi, macd, bollinger, atr } from "../src/indicators.js";

test("SMA duz seride sabit kalir", () => {
  const out = sma(Array(20).fill(50), 5);
  assert.equal(out.length, 16);
  assert.ok(out.every((v) => Math.abs(v - 50) < 1e-12));
});

test("EMA duz seride sabit, artan seride fiyatin altinda kalir", () => {
  const flat = ema(Array(30).fill(100), 9);
  assert.ok(Math.abs(flat[flat.length - 1] - 100) < 1e-9);

  const rising = Array.from({ length: 50 }, (_, i) => 100 + i * 2);
  const e = ema(rising, 9);
  assert.ok(e[e.length - 1] < rising[rising.length - 1]);
  assert.ok(e[e.length - 1] > e[0]);
});

test("RSI sinir davranislari: hep yukselen=100, hep dusen ~0, sinirlar icinde", () => {
  const up = Array.from({ length: 40 }, (_, i) => 100 + i);
  assert.equal(rsi(up, 14).pop(), 100);

  const down = Array.from({ length: 40 }, (_, i) => 200 - i);
  assert.ok(rsi(down, 14).pop() < 1);

  const mixed = Array.from({ length: 100 }, (_, i) => 100 + Math.sin(i / 5) * 10);
  assert.ok(rsi(mixed, 14).every((v) => v >= 0 && v <= 100));
});

test("MACD: histogram = macd - signal", () => {
  const prices = Array.from({ length: 120 }, (_, i) => 100 + Math.sin(i / 8) * 15 + i * 0.1);
  const { macd: m, signal: s, histogram: h } = macd(prices, 12, 26, 9);
  assert.equal(m.length, s.length);
  assert.equal(h.length, s.length);
  for (let i = 0; i < h.length; i++) {
    assert.ok(Math.abs(h[i] - (m[i] - s[i])) < 1e-9);
  }
});

test("Bollinger: alt < orta < ust, duz seride bantlar sifir genislikte", () => {
  const prices = Array.from({ length: 60 }, (_, i) => 100 + Math.sin(i / 4) * 8);
  const { middle, upper, lower } = bollinger(prices, 20, 2);
  for (let i = 0; i < middle.length; i++) {
    assert.ok(lower[i] <= middle[i] && middle[i] <= upper[i]);
  }
  const flat = bollinger(Array(30).fill(100), 20, 2);
  assert.ok(Math.abs(flat.upper.pop() - flat.lower.pop()) < 1e-9);
});

test("ATR pozitif ve volatiliteyle buyur", () => {
  const calm = Array.from({ length: 40 }, (_, i) => ({ high: 101, low: 99, close: 100 }));
  const wild = Array.from({ length: 40 }, (_, i) => ({ high: 110, low: 90, close: 100 }));
  const a1 = atr(calm, 14).pop();
  const a2 = atr(wild, 14).pop();
  assert.ok(a1 > 0 && a2 > a1);
});
