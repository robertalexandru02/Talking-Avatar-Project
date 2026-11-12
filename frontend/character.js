import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

export const CHARACTER_URL = "assets/character.vrm";
const SHAPES = {
  REST: {},
  A: { jawOpen: .52 },
  O: { jawOpen: .34, mouthFunnel: .48 },
  SCHWA: { jawOpen: .25, mouthFunnel: .1 },
  E: { jawOpen: .23, mouthStretchLeft: .27, mouthStretchRight: .27 },
  I: { jawOpen: .12, mouthStretchLeft: .3, mouthStretchRight: .3 },
  U: { jawOpen: .1, mouthPucker: .68 },
  SHCH: { jawOpen: .13, mouthFunnel: .26, mouthPucker: .16 },
  TH: { jawOpen: .12, tongueOut: .12 },
  A_O: { jawOpen: .48, mouthFunnel: .22 },
  E_I: { jawOpen: .18, mouthStretchLeft: .25, mouthStretchRight: .25 },
  BMP: { mouthClose: .65, mouthPressLeft: .18, mouthPressRight: .18 },
  FV: { jawOpen: .06, mouthShrugLower: .45 },
  W_OO: { jawOpen: .1, mouthPucker: .65 },
  LDTNS: { jawOpen: .15, mouthStretchLeft: .12, mouthStretchRight: .12 },
};

export function activeSpeechPose(clips, time) {
  for (const clip of clips) {
    if (time < clip.start || time >= clip.end) continue;
    if (!clip.visemes.length) return null;
    const ms = (time - clip.start) * 1000;
    const index = clip.visemes.findIndex(v => ms >= v.t && ms < v.t + v.d);
    if (index < 0) return "REST";
    const current = clip.visemes[index], next = clip.visemes[index + 1];
    // Prepare the next articulation slightly before its onset. Preserve lip
    // closures and pauses rather than blending vowels across actual silence.
    const window = current.v === "BMP" ? 12 : Math.min(32, current.d * .35);
    const mix = next && current.v !== "REST" && next.v !== "REST" && next.t <= current.t + current.d + 2
      ? THREE.MathUtils.clamp(1 - (current.t + current.d - ms) / window, 0, 1) * .45 : 0;
    return {v: current.v, next: next?.v, mix};
  }
  return "REST";
}

export function activeViseme(clips, time) {
  for (const clip of clips) {
    if (time < clip.start || time >= clip.end) continue;
    if (!clip.visemes.length) return null;
    const ms = (time - clip.start) * 1000;
    return clip.visemes.find(v => ms >= v.t && ms < v.t + v.d)?.v || "REST";
  }
  return "REST";
}

// This VIVERSE export is VRM 0.0 with standard glTF PBR materials. Read its
// humanoid metadata directly; facial weights use its actual ARKit morph targets.
export class CharacterAvatar {
  constructor() {
    this.group = new THREE.Group();
    this.group.visible = false;
    this.current = {};
    this.bones = {};
    this.rest = {};
    this.eyeForward = {};
    this.look = new THREE.Vector2();
    this.lookTarget = new THREE.Vector2();
    this.headLook = new THREE.Vector2();
    this.idleGaze = new THREE.Vector2();
    this.nextGlance = 3;
    this.posture = new THREE.Vector3();
    this.postureTarget = new THREE.Vector3(.02, -.025, .022);
    this.nextPosture = 4;
    this.presence = 0;
    this.preferences = {clothes:"#ffffff",hair:"#ffffff",glasses:true,framing:"portrait",theme:"studio"};
    this.inspection = {skeleton:false,wireframe:false,manual:false,shape:"jawOpen",weight:0};
    this.materialBases = new Map();
    this.pointerActive = false;
    this.raycaster = new THREE.Raycaster();
    this.gazePlane = new THREE.Plane();
    this.gazePoint = new THREE.Vector3();
    this.nextBlink = 2.5;
    this.blinkStart = -1;
    const key = new THREE.DirectionalLight(0xfff2e5, 1.65);
    key.position.set(2, 3, 3);
    const fill = new THREE.DirectionalLight(0xd5e5ff, 1.15);
    fill.position.set(-2, 2, 2);
    const rim = new THREE.DirectionalLight(0x9bc1dc, .95);
    rim.position.set(0, 2, -2);
    this.group.add(new THREE.HemisphereLight(0xf2f6ff, 0x35334b, 1.05), key, fill, rim);
    this.lights = {key,fill,rim};
  }

  load() {
    if (!this.loading) this.loading = this.loadModel().catch(error => {
      this.loading = null;
      throw error;
    });
    return this.loading;
  }

  async loadModel() {
    const gltf = await new GLTFLoader().loadAsync(CHARACTER_URL);
    const metadata = gltf.parser.json.extensions?.VRM;
    if (!metadata?.humanoid) throw new Error("Export VRM 0.0 VIVERSE necesar.");
    const meshes = [];
    this.accessories = [];
    gltf.scene.traverse(o => {
      if (o.isMesh && o.morphTargetDictionary) meshes.push(o);
      if (o.isMesh) for (const material of Array.isArray(o.material) ? o.material : [o.material]) {
        if (!material.isMeshStandardMaterial) continue;
        if (/glasses|head|hair/i.test(material.name)) material.roughness = Math.max(material.roughness, .72);
        if (/glasses/i.test(material.name)) material.metalness = Math.min(material.metalness, .05);
        if (!this.materialBases.has(material)) this.materialBases.set(material,material.color.clone());
        if (/glasses/i.test(material.name)) this.accessories.push(o);
      }
    });
    if (!meshes.some(m => "jawOpen" in m.morphTargetDictionary)) {
      throw new Error("Lipsesc formele ARKit ale gurii.");
    }
    this.meshes = meshes;
    this.root = gltf.scene;
    this.humanBoneCount = metadata.humanoid.humanBones.length;
    this.faceMesh = meshes.find(mesh => "jawOpen" in mesh.morphTargetDictionary);
    this.facialNames = Object.keys(this.faceMesh.morphTargetDictionary).filter(name=>!name.startsWith("FacialFeatures"));
    // VRM 0 faces -Z; the application portrait camera is on +Z.
    this.root.rotation.y = Math.PI;
    for (const human of metadata.humanoid.humanBones) {
      if (!["head", "neck", "leftEye", "rightEye", "spine", "chest", "leftUpperArm", "rightUpperArm",
        "leftLowerArm", "rightLowerArm", "leftHand", "rightHand"].includes(human.bone)) continue;
      const node = await gltf.parser.getDependency("node", human.node);
      this.bones[human.bone] = node;
      this.rest[human.bone] = node.quaternion.clone();
    }
    if (!this.bones.head || !this.bones.neck) throw new Error("Lipsesc oasele capului.");
    // Relax the source T-pose using world-space rotations, preserving skin bind matrices.
    this.root.updateMatrixWorld(true);
    for (const side of ["left", "right"]) {
      const arm = this.bones[`${side}UpperArm`];
      if (!arm) continue;
      const parent = arm.parent.getWorldQuaternion(new THREE.Quaternion());
      const turn = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1),
        THREE.MathUtils.degToRad(side === "left" ? -80 : 80));
      arm.quaternion.premultiply(parent.clone().invert().multiply(turn).multiply(parent));
    }
    this.group.add(this.root);
    this.root.updateMatrixWorld(true);
    const rootRotation = this.root.getWorldQuaternion(new THREE.Quaternion());
    // A fixed, slightly softened elbow pose avoids locked straight arms.
    // Only the torso's breathing and posture carry the arms after loading.
    for (const side of ["left", "right"]) {
      const elbow = this.bones[`${side}LowerArm`];
      if (!elbow) continue;
      const axis = new THREE.Vector3(1, 0, 0).applyQuaternion(rootRotation)
        .applyQuaternion(elbow.parent.getWorldQuaternion(new THREE.Quaternion()).invert());
      elbow.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(axis, side === "left" ? .07 : .1));
    }
    this.root.updateMatrixWorld(true);
    for (const side of ["left", "right"]) {
      for (const part of ["UpperArm", "LowerArm", "Hand"]) {
        const name = `${side}${part}`, bone = this.bones[name];
        if (!bone) continue;
        this.rest[name] = bone.quaternion.clone();
      }
      const eye = this.bones[`${side}Eye`];
      if (eye) this.eyeForward[side] = new THREE.Vector3(0, 0, -1).applyQuaternion(rootRotation)
        .applyQuaternion(eye.getWorldQuaternion(new THREE.Quaternion()).invert());
    }
    this.bounds = new THREE.Box3().setFromObject(this.root);
    this.headPosition = this.bones.head.getWorldPosition(new THREE.Vector3());
    this.facePosition = this.bones.leftEye && this.bones.rightEye
      ? this.bones.leftEye.getWorldPosition(new THREE.Vector3()).add(
        this.bones.rightEye.getWorldPosition(new THREE.Vector3())).multiplyScalar(.5)
      : this.headPosition.clone().add(new THREE.Vector3(0, this.bounds.getSize(new THREE.Vector3()).y * .04, 0));
    this.skeletonHelper = new THREE.SkeletonHelper(this.root);
    this.skeletonHelper.material.color.setHex(0x9effcc);
    this.skeletonHelper.material.depthTest = false;
    this.skeletonHelper.material.transparent = true;
    this.skeletonHelper.material.opacity = .85;
    this.skeletonHelper.renderOrder = 10;
    this.group.add(this.skeletonHelper);
    this.loaded = true;
    this.setAppearance(this.preferences);
    this.setInspection(this.inspection);
    return this;
  }

  frameCamera(camera, controls) {
    const height = this.bounds.getSize(new THREE.Vector3()).y;
    const head = this.headPosition;
    const full = this.preferences.framing === "full";
    const target = full ? this.bounds.getCenter(new THREE.Vector3())
      : new THREE.Vector3(head.x, head.y - height * .075, head.z);
    camera.fov = 32;
    camera.near = .01;
    camera.updateProjectionMatrix();
    const portraitHeight = height * (full ? 1.12 : .43);
    const tangent=Math.tan(THREE.MathUtils.degToRad(16));
    const distance = Math.max(portraitHeight/(2*tangent),full ? this.bounds.getSize(new THREE.Vector3()).x/(2*tangent*camera.aspect) : 0)*1.1;
    controls.target.copy(target);
    camera.position.set(target.x, target.y + height * .015, target.z + distance);
    controls.minDistance = height * .43 / (2 * tangent) * 1.1 * .5;
    controls.maxDistance = distance * 4;
    this.cameraFocus = {wide:target.clone(), face:this.facePosition.clone(),
      distance:camera.position.distanceTo(target), close:controls.minDistance};
    controls.update();
  }

  updateCameraFocus(camera, controls) {
    if (!this.cameraFocus) return;
    const focus = this.cameraFocus;
    const distance = camera.position.distanceTo(controls.target);
    const amount = 1 - THREE.MathUtils.smoothstep(distance, focus.close, focus.distance);
    const target = focus.wide.clone().lerp(focus.face, amount);
    const shift = target.sub(controls.target);
    // Translate camera and orbit centre together, preserving the viewing angle.
    // This keeps the full-body framing at rest and approaches the face on zoom.
    camera.position.add(shift);
    controls.target.add(shift);
  }

  setLook(x, y, active) {
    this.pointerActive = active;
    this.lookTarget.set(active ? THREE.MathUtils.clamp(x, -1, 1) : 0,
      active ? THREE.MathUtils.clamp(y, -1, 1) : 0);
  }

  setPointer(pointer, camera, active) {
    if (!active || !this.loaded) { this.setLook(0, 0, false); return; }
    this.root.updateMatrixWorld(true);
    const head = this.bones.head.getWorldPosition(new THREE.Vector3());
    const normal = camera.getWorldDirection(new THREE.Vector3());
    this.gazePlane.setFromNormalAndCoplanarPoint(normal, head);
    this.raycaster.setFromCamera(pointer, camera);
    if (!this.raycaster.ray.intersectPlane(this.gazePlane, this.gazePoint)) return;
    // Convert the cursor displacement to the character's space so orbiting
    // the camera does not reverse where the eyes turn.
    const delta = this.gazePoint.clone().sub(head).applyQuaternion(
      this.root.getWorldQuaternion(new THREE.Quaternion()).invert());
    this.setLook(-delta.x / .6, delta.y / .5, true);
  }

  setMorph(name, value) {
    for (const mesh of this.meshes) {
      const index = mesh.morphTargetDictionary[name];
      if (index !== undefined) mesh.morphTargetInfluences[index] = value;
    }
  }

  getMorph(name) {
    if (!this.faceMesh) return 0;
    const index=this.faceMesh.morphTargetDictionary[name];
    return index===undefined ? 0 : this.faceMesh.morphTargetInfluences[index];
  }

  setAppearance(patch) {
    this.preferences={...this.preferences,...patch};
    if (!this.loaded) return;
    const {clothes,hair,glasses,theme}=this.preferences;
    for (const [material,base] of this.materialBases) {
      const tint=/Template/i.test(material.name) ? clothes : /Hair/i.test(material.name) ? hair : null;
      material.color.copy(base);
      if (tint && /^#[0-9a-f]{6}$/i.test(tint)) material.color.multiply(new THREE.Color(tint));
    }
    this.accessories.forEach(mesh=>{mesh.visible=glasses;});
    const lighting={studio:[0xfff2e5,0xd5e5ff,0x9bc1dc],gallery:[0xffdfbd,0xfff2df,0xe0ad83],night:[0xe1e8ff,0x9ac6ff,0xa99fff]}[theme] || [0xfff2e5,0xd5e5ff,0x9bc1dc];
    [this.lights.key,this.lights.fill,this.lights.rim].forEach((light,i)=>light.color.setHex(lighting[i]));
  }

  setInspection(patch) {
    const previous=this.inspection;
    this.inspection={...previous,...patch};
    if (!this.loaded) return;
    if (previous.manual !== this.inspection.manual || previous.shape !== this.inspection.shape) {
      this.facialNames.forEach(name=>this.setMorph(name,0));this.current={};
    }
    this.skeletonHelper.visible=this.inspection.skeleton;
    for (const material of this.materialBases.keys()) material.wireframe=this.inspection.wireframe;
  }

  beginPhrase(text, time) {
    this.phraseAt = time;
    this.question = /\?\s*$/.test(text);
  }

  updatePresence(dt, time, state) {
    // Shift the upper body, keeping the hips, legs and feet anchored. A slowly
    // changing target avoids a looping side-to-side sway or volume-driven bob.
    if (time >= this.nextPosture) {
      this.postureTarget.set((Math.random() - .5) * .065,
        (Math.random() - .5) * .085, (Math.random() - .5) * .065);
      this.nextPosture = time + 4.5 + Math.random() * 3;
    }
    this.posture.lerp(this.postureTarget, 1 - Math.exp(-dt * .65));
    this.presence = THREE.MathUtils.lerp(this.presence, state === "speaking" ? 1 : 0, 1 - Math.exp(-dt * 2));
    const breath = Math.sin(time * 1.28) + Math.sin(time * .43 + .8) * .18;
    const p = this.posture;
    if (this.bones.spine) this.bones.spine.quaternion.copy(this.rest.spine).multiply(new THREE.Quaternion()
      .setFromEuler(new THREE.Euler(p.x + breath * .003, p.y, p.z, "YXZ")));
    if (this.bones.chest) this.bones.chest.quaternion.copy(this.rest.chest).multiply(new THREE.Quaternion()
      .setFromEuler(new THREE.Euler(breath * .012 - p.x * .25,
        -p.y * .2 + Math.sin(time * .9) * .004 * this.presence, -p.z * .3, "YXZ")));
  }

  updateEyes() {
    if (this.inspection.manual) {
      for (const side of ["left","right"]) this.bones[`${side}Eye`]?.quaternion.copy(this.rest[`${side}Eye`]);
      return;
    }
    this.root.updateMatrixWorld(true);
    const rootRotation = this.root.getWorldQuaternion(new THREE.Quaternion());
    const direction = new THREE.Vector3(-this.look.x * .38, this.look.y * .26, -1)
      .normalize().applyQuaternion(rootRotation);
    for (const side of ["left", "right"]) {
      const eye = this.bones[`${side}Eye`];
      if (!eye || !this.eyeForward[side]) continue;
      const parent = eye.parent.getWorldQuaternion(new THREE.Quaternion());
      const restWorld = parent.clone().multiply(this.rest[`${side}Eye`]);
      const forward = this.eyeForward[side].clone().applyQuaternion(restWorld);
      const turn = new THREE.Quaternion().setFromUnitVectors(forward, direction);
      const angle = new THREE.Quaternion().angleTo(turn);
      if (angle > .38) turn.slerp(new THREE.Quaternion(), 1 - .38 / angle);
      eye.quaternion.copy(parent.invert().multiply(turn).multiply(restWorld));
    }
  }

  update(dt, time, state, rms, viseme = "REST") {
    if (!this.loaded) return;
    const pose = typeof viseme === "object" && viseme !== null ? viseme : {v: viseme, mix: 0};
    // Faster closures keep B/M/P readable; opening still has a soft transition.
    const factor = 1 - Math.exp(-Math.min(dt, .05) * (pose.v === "BMP" ? 38 : 27));
    const gain = THREE.MathUtils.clamp(.8 + rms * 2, .8, 1.05);
    const target = viseme === null && state === "speaking"
      ? { jawOpen: Math.min(rms * 3, .4) } : {...(SHAPES[pose.v] || {})};
    if (pose.mix > 0) {
      const next = SHAPES[pose.next] || {};
      for (const name of new Set([...Object.keys(target), ...Object.keys(next)])) {
        target[name] = THREE.MathUtils.lerp(target[name] || 0, next[name] || 0, pose.mix);
      }
    }
    for (const name of new Set([...Object.keys(this.current), ...Object.keys(target)])) {
      this.current[name] = THREE.MathUtils.lerp(this.current[name] || 0, (target[name] || 0) * gain, factor);
      this.setMorph(name, this.current[name]);
    }
    if (this.blinkStart < 0 && time >= this.nextBlink) {
      this.blinkStart = time;
      this.blinkDuration = .20 + Math.random() * .05;
    }
    let blink = 0;
    if (this.blinkStart >= 0) {
      const elapsed = time - this.blinkStart;
      if (elapsed >= this.blinkDuration) {
        this.blinkStart = -1;
        const doubleBlink = !this.lastBlinkWasDouble && Math.random() < .1;
        this.lastBlinkWasDouble = doubleBlink;
        this.nextBlink = time + (doubleBlink ? .13 : 2.6 + Math.random() * 3.8);
      }
      else if (elapsed < .075) blink = Math.sin(elapsed / .075 * Math.PI / 2);
      else blink = Math.cos((elapsed - .075) / (this.blinkDuration - .075) * Math.PI / 2);
    }
    this.setMorph("eyeBlinkLeft", blink);
    this.setMorph("eyeBlinkRight", blink);
    const age = time - (this.phraseAt ?? -10);
    const emphasis = state === "speaking" && age >= 0 && age < 1.4 ? Math.sin(age / 1.4 * Math.PI) : 0;
    this.brow = THREE.MathUtils.lerp(this.brow || 0, state === "thinking" ? .065 : emphasis * .035, 1 - Math.exp(-dt * 3));
    this.setMorph("browInnerUp", this.brow);
    this.setMorph("browOuterUpLeft", .02 + emphasis * .035);
    this.setMorph("browOuterUpRight", .015 + emphasis * .025);
    const rounded = Math.max(this.current.mouthPucker || 0, this.current.mouthFunnel || 0);
    this.setMorph("mouthSmileLeft", .12 * (1 - rounded));
    this.setMorph("mouthSmileRight", .11 * (1 - rounded));
    if (!this.pointerActive && time >= this.nextGlance) {
      this.idleGaze.set((Math.random() - .5) * .2, (Math.random() - .5) * .1);
      this.glanceUntil = time + .5 + Math.random() * .4;
      this.nextGlance = time + 3.5 + Math.random() * 4;
    }
    if (this.pointerActive || time > (this.glanceUntil || 0)) this.idleGaze.set(0, 0);
    this.look.lerp(this.lookTarget.clone().add(this.idleGaze), 1 - Math.exp(-dt * 13));
    this.headLook.lerp(this.lookTarget, 1 - Math.exp(-dt * 2.8));
    this.updatePresence(dt, time, state);
    const yaw = this.headLook.x * .025 + Math.sin(time * .4) * .012 - this.posture.y * .35;
    const gesture = state === "speaking" && age >= 0 && age < 1.2
      ? Math.sin(age / 1.2 * Math.PI) * .022 : 0;
    const pitch = -this.headLook.y * .018 + Math.sin(time * .32) * .013 - this.posture.x * .3 + (this.question ? -gesture * .4 : gesture);
    for (const name of ["head", "neck"]) {
      const scale = name === "head" ? .75 : .25;
      this.bones[name].quaternion.copy(this.rest[name]).multiply(new THREE.Quaternion()
        .setFromEuler(new THREE.Euler(pitch * scale, yaw * scale,
          Math.sin(time * .28) * .014 - this.posture.z * .4 + (this.question ? gesture * .6 : 0), "YXZ")));
    }
    // Rotate the actual eyeball joints, instead of moving the entire head or
    // relying on facial shapes whose effect can be subtle on this export.
    this.updateEyes();
    this.lastViseme = typeof viseme === "object" && viseme !== null ? viseme.v : viseme || "audio";
    if (this.inspection.manual) {
      this.facialNames.forEach(name=>this.setMorph(name,0));
      this.setMorph(this.inspection.shape,THREE.MathUtils.clamp(this.inspection.weight,0,1));
    }
  }
}
