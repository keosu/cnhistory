import {test} from 'node:test';
import assert from 'node:assert/strict';
import {TimelineTransport} from '../web/playback.js';

function fixture(limit = 1000) {
  let time = 0, serial = 0, year = 0;
  const queue = new Map();
  const transport = new TimelineTransport({
    now: () => time,
    schedule: (callback, delay) => {const id = ++serial;queue.set(id, {at:time + delay, callback});return id;},
    cancel: id => queue.delete(id),
    step: direction => {if (year + direction < 0 || year + direction > limit) return false;year += direction;return true;}
  });
  return {transport, get year() {return year;}, advance(duration) {
    const end = time + duration;
    while (true) {
      const next = [...queue.entries()].sort((a,b) => a[1].at - b[1].at)[0];
      if (!next || next[1].at > end) break;
      time = next[1].at;queue.delete(next[0]);next[1].callback();
    }
    time = end;
  }};
}

test('a tap advances once and release prevents repetition', () => {
  const f=fixture();f.transport.hold(1);f.advance(100);f.transport.release();f.advance(3000);
  assert.equal(f.year,1);
});

test('a sustained hold accelerates and stops immediately on release', () => {
  const f=fixture();f.transport.hold(1);f.advance(1000);const early=f.year;
  f.advance(1000);const middle=f.year-early;f.advance(1000);const late=f.year-early-middle;
  assert.ok(late>middle&&middle>=early);
  f.transport.release();const final=f.year;f.advance(5000);assert.equal(f.year,final);
});

test('repeated keydown does not reset the hold acceleration', () => {
  const a=fixture(),b=fixture();a.transport.hold(1);b.transport.hold(1);
  for(let i=0;i<30;i++){a.advance(100);b.advance(100);b.transport.hold(1);}
  assert.equal(a.year,b.year);
});

test('speed changes take effect during playback without duplicate timers', () => {
  const f=fixture();f.transport.play();f.transport.play();f.advance(1000);assert.equal(f.year,1);
  f.transport.setSpeed(4);f.advance(1000);assert.equal(f.year,5);
  f.transport.pause();f.advance(2000);assert.equal(f.year,5);
  f.transport.setSpeed(.5);f.transport.play();f.advance(2000);assert.equal(f.year,6);
});

test('bounds and focus-loss stop both playback and held stepping', () => {
  const f=fixture(3);f.transport.setSpeed(8);f.transport.play();f.advance(1000);
  assert.equal(f.year,3);assert.equal(f.transport.playing,false);
  f.transport.hold(-1);f.advance(500);f.transport.stop();const final=f.year;f.advance(5000);assert.equal(f.year,final);
});
