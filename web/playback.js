// Shared transport for playback, held keys and held pointer buttons.
export class TimelineTransport {
  constructor({step, onChange = () => {}, now = () => performance.now(),
    schedule = (callback, delay) => setTimeout(callback, delay), cancel = id => clearTimeout(id)}) {
    this.step = step;
    this.onChange = onChange;
    this.now = now;
    this.schedule = schedule;
    this.cancel = cancel;
    this.speed = 1;
    this.playing = false;
    this.direction = 0;
    this.playTimer = null;
    this.holdTimer = null;
  }

  setSpeed(value) {
    const speed = Number(value);
    if (![.5, 1, 2, 4, 8].includes(speed)) return;
    this.speed = speed;
    if (this.playing) {
      this.cancel(this.playTimer);
      this.queuePlayback();
    }
  }

  play() {
    if (this.playing) return;
    this.release();
    this.playing = true;
    this.onChange(true);
    this.queuePlayback();
  }

  queuePlayback() {
    this.playTimer = this.schedule(() => {
      if (!this.playing) return;
      if (!this.step(1)) return this.pause();
      this.queuePlayback();
    }, 1000 / this.speed);
  }

  pause() {
    this.cancel(this.playTimer);
    this.playTimer = null;
    if (this.playing) this.onChange(false);
    this.playing = false;
  }

  hold(direction) {
    if (this.direction === direction) return;
    this.pause();
    this.release();
    this.direction = direction;
    this.startedAt = this.now();
    if (!this.step(direction)) return this.release();
    this.holdTimer = this.schedule(() => this.repeat(), 400);
  }

  repeat() {
    if (!this.direction) return;
    if (!this.step(this.direction)) return this.release();
    const elapsed = this.now() - this.startedAt;
    const delay = elapsed < 1000 ? 220 : elapsed < 2000 ? 110 : 45;
    this.holdTimer = this.schedule(() => this.repeat(), delay);
  }

  release() {
    this.cancel(this.holdTimer);
    this.holdTimer = null;
    this.direction = 0;
  }

  stop() {
    this.pause();
    this.release();
  }
}
