import * as THREE from "three";

const PALETTES = {
  ocean: [0x075aff, 0x12edff, 0x7134ff, 0xff35b4, 0x00c985, 0x69ffcf],
  cosmic: [0x833cff, 0xf483ff, 0x443dff, 0x31bfff, 0xb14fff, 0xff87ca],
  ember: [0xff4c13, 0xffd066, 0xe62a60, 0xff993c, 0xff9434, 0xffe5a0],
};
const COLOR_KEYS = ["uIdleLow", "uIdleHigh", "uThinkLow", "uThinkHigh", "uSpeakLow", "uSpeakHigh"];
const COLOR_SETS = Object.values(PALETTES).map(colors => colors.map(hex => new THREE.Color(hex)));

// Orbital layers plus per-particle spring physics. Two draws: points and selective trails.
export class ParticleSwarm {
  constructor(maxCount = 10000) {
    this.maxCount = maxCount;
    this.count = Math.min(9000, maxCount);
    this.positions = new Float32Array(maxCount * 3);
    this.offsets = new Float32Array(maxCount * 3);
    this.velocities = new Float32Array(maxCount * 3);
    this.seeds = new Float32Array(maxCount * 3);
    for (let i = 0; i < this.seeds.length; i++) this.seeds[i] = Math.random();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(this.positions, 3).setUsage(THREE.DynamicDrawUsage));
    geometry.setAttribute("seed", new THREE.BufferAttribute(this.seeds, 3));
    geometry.setDrawRange(0, this.count);
    this.uniforms = {
      uThinking: { value: 0 }, uSpeaking: { value: 0 }, uAmplitude: { value: 0 },
      uBrightness: { value: 1.4 }, uCameraDistance: { value: 6.5 },
      uPixelRatio: { value: Math.min(devicePixelRatio, 2) },
      uIdleLow: { value: new THREE.Color() }, uIdleHigh: { value: new THREE.Color() },
      uThinkLow: { value: new THREE.Color() }, uThinkHigh: { value: new THREE.Color() },
      uSpeakLow: { value: new THREE.Color() }, uSpeakHigh: { value: new THREE.Color() },
    };
    const colorShader = `
      uniform float uThinking, uSpeaking, uAmplitude, uBrightness, uCameraDistance;
      uniform vec3 uIdleLow, uIdleHigh, uThinkLow, uThinkHigh, uSpeakLow, uSpeakHigh;
      vec3 palette(float blend) {
        vec3 idle = mix(uIdleLow, uIdleHigh, blend);
        vec3 thinking = mix(uThinkLow, uThinkHigh, blend);
        vec3 speaking = mix(uSpeakLow, uSpeakHigh, blend);
        return mix(mix(idle, thinking, uThinking), speaking, uSpeaking);
      }
    `;
    this.points = new THREE.Points(geometry, new THREE.ShaderMaterial({
      uniforms: this.uniforms, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        ${colorShader}
        uniform float uPixelRatio;
        attribute vec3 seed;
        varying vec3 vColor;
        varying float vAlpha, vSoftness;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          float depth = clamp((mv.z + uCameraDistance + 1.9) / 3.8, 0.0, 1.0);
          float layer = floor(seed.z * 3.0);
          gl_PointSize = clamp((4.0 + seed.x * 4.0 + layer * 0.4)
            * mix(0.8, 1.3, depth) * uPixelRatio * 4.0 / -mv.z, 1.0, 18.0);
          vColor = palette(seed.y);
          vAlpha = mix(0.4, 1.1, depth) * (0.8 + seed.x * 0.2)
                 * uBrightness * (1.0 + uAmplitude * 0.08);
          vSoftness = 1.0 - depth;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        varying float vAlpha, vSoftness;
        void main() {
          float r = length(gl_PointCoord - vec2(0.5)) * 2.0;
          if (r > 1.0) discard;
          float core = 1.0 - smoothstep(0.08, mix(0.45, 0.7, vSoftness), r);
          float halo = pow(1.0 - r, 1.7);
          gl_FragColor = vec4(vColor, (core * 0.75 + halo * 0.4) * vAlpha);
          #include <colorspace_fragment>
        }
      `,
    }));
    this.points.frustumCulled = false;

    this.trailCount = Math.min(140, maxCount);
    this.trailSteps = 5;
    const fast = [];
    for (let i = 0; i < maxCount; i++) if (this.seeds[i * 3 + 2] > 0.67) fast.push(i);
    this.trailIndices = new Uint32Array(this.trailCount);
    for (let i = 0; i < this.trailCount; i++) this.trailIndices[i] = fast[i % fast.length] ?? i;
    this.history = new Float32Array(this.trailCount * (this.trailSteps + 1) * 3);
    const trailVertices = this.trailCount * this.trailSteps * 2;
    this.trailPositions = new Float32Array(trailVertices * 3);
    const ages = new Float32Array(trailVertices);
    const shades = new Float32Array(trailVertices);
    for (let i = 0; i < this.trailCount; i++) {
      for (let s = 0; s < this.trailSteps; s++) {
        const v = (i * this.trailSteps + s) * 2;
        ages[v] = 1 - s / this.trailSteps;
        ages[v + 1] = 1 - (s + 1) / this.trailSteps;
        shades[v] = shades[v + 1] = this.seeds[this.trailIndices[i] * 3 + 1];
      }
    }
    const trailGeometry = new THREE.BufferGeometry();
    trailGeometry.setAttribute("position", new THREE.BufferAttribute(this.trailPositions, 3).setUsage(THREE.DynamicDrawUsage));
    trailGeometry.setAttribute("age", new THREE.BufferAttribute(ages, 1));
    trailGeometry.setAttribute("shade", new THREE.BufferAttribute(shades, 1));
    this.trails = new THREE.LineSegments(trailGeometry, new THREE.ShaderMaterial({
      uniforms: this.uniforms, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        ${colorShader}
        attribute float age, shade;
        varying vec3 vColor;
        varying float vAlpha;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          float depth = clamp((mv.z + uCameraDistance + 1.9) / 3.8, 0.0, 1.0);
          vColor = palette(shade);
          vAlpha = age * age * 0.28 * mix(0.3, 1.0, depth) * uBrightness;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        varying float vAlpha;
        void main() {
          gl_FragColor = vec4(vColor, vAlpha);
          #include <colorspace_fragment>
        }
      `,
    }));
    this.trails.frustumCulled = false;
    this.group = new THREE.Group();
    this.group.add(this.trails, this.points);
    this.pointer = new THREE.Vector2();
    this.pointerActive = false;
    this.pointerStrength = 0;
    this.interaction = 1.7;
    this.raycaster = new THREE.Raycaster();
    this.plane = new THREE.Plane();
    this.normal = new THREE.Vector3(0, 0, 1);
    this.origin = new THREE.Vector3();
    this.cursor = new THREE.Vector3();
    this.previousCursor = new THREE.Vector3();
    this.cursorVelocity = new THREE.Vector3();
    this.rawCursorVelocity = new THREE.Vector3();
    this.historyReady = false;
    this.historyAccumulator = 0;
    this.phraseAge = 20;
    this.phraseLift = 0;
    this.paletteTime = 0;
    this.updatePalette(0);
  }

  updatePalette(elapsed) {
    // Hold each palette for four seconds, then crossfade for two seconds.
    const position = elapsed / 6;
    const index = Math.floor(position) % COLOR_SETS.length;
    const mix = THREE.MathUtils.smoothstep(position % 1, 4 / 6, 1);
    COLOR_KEYS.forEach((key, i) => this.uniforms[key].value.copy(COLOR_SETS[index][i])
      .lerp(COLOR_SETS[(index + 1) % COLOR_SETS.length][i], mix));
  }

  setAppearance({ brightness, density, interaction, trails } = {}) {
    if (brightness !== undefined) this.uniforms.uBrightness.value = THREE.MathUtils.clamp(brightness, 0.5, 1.6);
    if (density !== undefined) {
      this.count = Math.min(this.maxCount, Math.max(1000, Math.round(density)));
      this.points.geometry.setDrawRange(0, this.count);
      this.offsets.fill(0);
      this.velocities.fill(0);
      this.historyReady = false;
    }
    if (interaction !== undefined) this.interaction = THREE.MathUtils.clamp(interaction, 0, 2);
    if (trails !== undefined) this.trails.visible = trails;
  }

  setPointer(x, y, active) {
    this.pointer.set(x, y);
    if (active && !this.pointerActive) this.cursorNeedsReset = true;
    this.pointerActive = active;
  }

  beginPhrase(text = "") {
    // One slow gesture per spoken phrase, not a response to each volume peak.
    this.phraseAge = 0;
    this.phraseLift = text.trim().endsWith("?") ? 0.045 : -0.025;
  }

  update(dt, time, state, rms, camera) {
    dt = Math.min(Math.max(dt, 0), 0.05);
    this.paletteTime += dt;
    this.updatePalette(this.paletteTime);
    const u = this.uniforms;
    const ease = (key, target, speed) => {
      u[key].value += (target - u[key].value) * (1 - Math.exp(-dt * speed));
    };
    ease("uThinking", state === "thinking" ? 1 : 0, 2.5);
    ease("uSpeaking", state === "speaking" ? 1 : 0, 2);
    ease("uAmplitude", state === "speaking" ? Math.min(rms * 6, 1) : 0, 1.1);
    this.phraseAge += dt;
    const phrase = Math.sin(Math.min(this.phraseAge / 1.8, 1) * Math.PI);
    const thinking = u.uThinking.value, speaking = u.uSpeaking.value, energy = u.uAmplitude.value;
    const gesture = speaking * (0.025 * Math.sin(time * 0.55) + this.phraseLift * phrase);
    if (camera) {
      camera.updateMatrixWorld();
      camera.getWorldDirection(this.normal);
      this.plane.setFromNormalAndCoplanarPoint(this.normal, this.origin);
      this.raycaster.setFromCamera(this.pointer, camera);
      if (this.pointerActive) this.raycaster.ray.intersectPlane(this.plane, this.cursor);
      if (this.cursorNeedsReset) {
        this.previousCursor.copy(this.cursor);
        this.cursorVelocity.set(0, 0, 0);
        this.cursorNeedsReset = false;
      }
      this.rawCursorVelocity.copy(this.cursor).sub(this.previousCursor).divideScalar(Math.max(dt, 0.001));
      this.rawCursorVelocity.clampLength(0, 5);
      this.cursorVelocity.lerp(this.rawCursorVelocity, 1 - Math.exp(-dt * 9));
      this.previousCursor.copy(this.cursor);
      u.uCameraDistance.value = camera.position.distanceTo(this.origin);
    }
    this.pointerStrength += ((this.pointerActive ? this.interaction : 0) - this.pointerStrength) * (1 - Math.exp(-dt * 5));
    const nx = this.normal.x, ny = this.normal.y, nz = this.normal.z;
    const tiltC = Math.cos(gesture), tiltS = Math.sin(gesture);
    const position = this.positions, offset = this.offsets, velocity = this.velocities;
    // Substeps keep the damped springs stable when rendering slows down.
    const steps = Math.max(1, Math.ceil(dt / 0.0167)), h = dt / steps;
    for (let i = 0; i < this.count; i++) {
      const k = i * 3;
      const a = this.seeds[k], b = this.seeds[k + 1], c = this.seeds[k + 2];
      const layer = Math.floor(c * 3);
      const speed = 0.11 + layer * 0.06 + (layer === 2 ? 0.04 : 0) + a * 0.07;
      const latitude = b * 2 - 1, ring = Math.sqrt(Math.max(0, 1 - latitude * latitude));
      const angle = a * Math.PI * 2 + time * speed;
      const organic = 1 + 0.085 * Math.sin(angle * 2 + latitude * 2.5 + time * 0.19)
                        + 0.045 * Math.cos(angle * 3 - latitude * 3 - time * 0.14);
      let radius = (0.65 + Math.pow(c, 0.4) * 1.15) * organic;
      radius *= (1 - thinking * 0.46) * (1 + speaking * 0.05);
      // Processing creates inward, staggered streams; speaking adds tangential flow.
      const spiral = angle + thinking * 0.32 * Math.sin(time * 0.7 + c * 8);
      let x = Math.cos(spiral) * ring * radius;
      let y = latitude * radius * 1.08 + Math.sin(angle * 2 + time * 0.28) * 0.09;
      const z = Math.sin(spiral) * ring * radius * 0.93;
      const flow = speaking * (0.035 + energy * 0.025) * Math.sin(time * 0.65 + latitude * 3);
      x += flow * latitude;
      y += speaking * phrase * 0.045 * ring;
      const px = x * tiltC - y * tiltS, py = x * tiltS + y * tiltC;
      const dx = px + offset[k] - this.cursor.x;
      const dy = py + offset[k + 1] - this.cursor.y;
      const dz = z + offset[k + 2] - this.cursor.z;
      const depth = dx * nx + dy * ny + dz * nz;
      const tx = dx - nx * depth, ty = dy - ny * depth, tz = dz - nz * depth;
      const spread = 0.48 + c * 0.4;
      const influence = Math.exp(-(tx * tx + ty * ty + tz * tz) / (spread * spread) - depth * depth / 2.25)
                      * this.pointerStrength * (0.7 + b * 0.6);
      const swirl = 1.5 + Math.sin(a * 8 + time * 0.6);
      const fx = (tx * 8 + (ny * tz - nz * ty) * swirl + this.cursorVelocity.x * 1.6) * influence;
      const fy = (ty * 8 + (nz * tx - nx * tz) * swirl + this.cursorVelocity.y * 1.6) * influence;
      const fz = (tz * 8 + (nx * ty - ny * tx) * swirl + this.cursorVelocity.z * 1.6) * influence;
      for (let step = 0; step < steps; step++) {
        velocity[k] += (fx - offset[k] * 19 - velocity[k] * 7) * h;
        velocity[k + 1] += (fy - offset[k + 1] * 19 - velocity[k + 1] * 7) * h;
        velocity[k + 2] += (fz - offset[k + 2] * 19 - velocity[k + 2] * 7) * h;
        offset[k] += velocity[k] * h;
        offset[k + 1] += velocity[k + 1] * h;
        offset[k + 2] += velocity[k + 2] * h;
      }
      position[k] = px + offset[k];
      position[k + 1] = py + offset[k + 1];
      position[k + 2] = z + offset[k + 2];
    }
    this.points.geometry.attributes.position.needsUpdate = true;
    this.updateTrails(dt);
  }

  updateTrails(dt) {
    if (!this.trails.visible) { this.historyReady = false; return; }
    this.historyAccumulator += dt;
    const sample = this.historyAccumulator >= 1 / 30;
    if (sample) this.historyAccumulator %= 1 / 30;
    for (let i = 0; i < this.trailCount; i++) {
      const source = (this.trailIndices[i] % this.count) * 3;
      const base = i * (this.trailSteps + 1) * 3;
      if (!this.historyReady) {
        for (let s = 0; s <= this.trailSteps; s++) {
          this.history.set(this.positions.subarray(source, source + 3), base + s * 3);
        }
      } else if (sample) {
        this.history.copyWithin(base + 3, base, base + this.trailSteps * 3);
        this.history.set(this.positions.subarray(source, source + 3), base);
      }
      for (let s = 0; s < this.trailSteps; s++) {
        const target = (i * this.trailSteps + s) * 6;
        for (let axis = 0; axis < 3; axis++) {
          this.trailPositions[target + axis] = s === 0 ? this.positions[source + axis] : this.history[base + s * 3 + axis];
          this.trailPositions[target + 3 + axis] = this.history[base + (s + 1) * 3 + axis];
        }
      }
    }
    this.historyReady = true;
    this.trails.geometry.attributes.position.needsUpdate = true;
  }
}
