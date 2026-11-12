import * as THREE from "three";

const THEMES = {
  studio:{floor:0x17272c,panels:0x20343d,edge:0x83c6b1},
  gallery:{floor:0x39312d,panels:0x50413a,edge:0xe7bf92},
  night:{floor:0x121b30,panels:0x172644,edge:0x8d9fff},
};

export class CharacterStage {
  constructor() {
    this.group = new THREE.Group(); this.group.visible = false;
    this.floor = new THREE.Mesh(new THREE.CylinderGeometry(1.08,1.11,.035,64),
      new THREE.MeshStandardMaterial({roughness:.95,metalness:.1}));
    this.edge = new THREE.Mesh(new THREE.TorusGeometry(1.08,.005,6,96),
      new THREE.MeshBasicMaterial({transparent:true,opacity:.55}));
    this.edge.rotation.x = Math.PI/2;
    this.panels = [];
    for (let i=0;i<3;i++) {
      const panel = new THREE.Mesh(new THREE.BoxGeometry(.52,2.6,.06),new THREE.MeshStandardMaterial({roughness:.9}));
      panel.position.set((i-1)*.74,1.15,-1.05-Math.abs(i-1)*.12);
      panel.rotation.y = (i-1)*-.13;
      this.panels.push(panel);this.group.add(panel);
    }
    const canvas = document.createElement("canvas"); canvas.width=canvas.height=128;
    const context=canvas.getContext("2d");
    const gradient=context.createRadialGradient(64,64,5,64,64,64);
    gradient.addColorStop(0,"rgba(0,0,0,.6)");gradient.addColorStop(1,"rgba(0,0,0,0)");
    context.fillStyle=gradient;context.fillRect(0,0,128,128);
    this.contact = new THREE.Mesh(new THREE.PlaneGeometry(.9,.65),new THREE.MeshBasicMaterial({
      map:new THREE.CanvasTexture(canvas),transparent:true,depthWrite:false,opacity:.65}));
    this.contact.rotation.x=-Math.PI/2;
    this.group.add(this.floor,this.edge,this.contact);
    this.setTheme("studio");
  }
  place(bounds) {
    const center=bounds.getCenter(new THREE.Vector3());
    this.group.position.set(center.x,bounds.min.y-.018,0);
    this.contact.position.y=.02;this.edge.position.y=.018;
  }
  setTheme(name) {
    const theme=THEMES[name]||THEMES.studio;
    this.floor.material.color.setHex(theme.floor);
    this.panels.forEach(panel=>panel.material.color.setHex(theme.panels));
    this.edge.material.color.setHex(theme.edge);
  }
}
