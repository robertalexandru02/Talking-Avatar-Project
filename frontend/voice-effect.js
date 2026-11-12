// Local metallic texture. The carrier modulates speech, never the output directly.
export class VoiceEffect {
  constructor(context, destination, mode = "natural") {
    this.context = context;
    this.input = context.createGain();
    this.dry = context.createGain();
    this.wet = context.createGain();
    const high = context.createBiquadFilter();
    high.type = "highpass";
    high.frequency.value = 120;
    const low = context.createBiquadFilter();
    low.type = "lowpass";
    low.frequency.value = 4300;
    const presence = context.createBiquadFilter();
    presence.type = "peaking";
    presence.frequency.value = 1400;
    presence.Q.value = 0.8;
    presence.gain.value = 3;
    const modulated = context.createGain();
    modulated.gain.value = 0;
    this.carrier = context.createOscillator();
    this.carrier.type = "sine";
    this.carrier.frequency.value = 42;
    this.carrier.connect(modulated.gain);
    const compressor = context.createDynamicsCompressor();
    compressor.threshold.value = -12;
    compressor.knee.value = 12;
    compressor.ratio.value = 4;
    compressor.attack.value = 0.005;
    compressor.release.value = 0.12;

    this.input.connect(this.dry).connect(destination);
    this.input.connect(high).connect(low).connect(presence).connect(modulated);
    modulated.connect(compressor).connect(this.wet).connect(destination);
    this.dry.gain.value = mode === "robot" ? 0.62 : 1;
    this.wet.gain.value = mode === "robot" ? 0.32 : 0;
    this.carrier.start();
  }

  setMode(mode) {
    const now = this.context.currentTime;
    const robot = mode === "robot";
    for (const [node, target] of [[this.dry, robot ? 0.62 : 1], [this.wet, robot ? 0.32 : 0]]) {
      node.gain.cancelScheduledValues(now);
      node.gain.setTargetAtTime(target, now, 0.025);
    }
  }
}
